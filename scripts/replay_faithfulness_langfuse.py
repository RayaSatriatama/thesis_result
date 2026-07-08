#!/usr/bin/env python3
"""
Re-run RAGAS + FABLES on existing Langfuse traces using saved story + contexts (no story regeneration).

1. Backs up Eval_Data/Traces and Eval_Data/Observations (unless --skip-backup).
2. Loads observations from Eval_Data/Observations/*.jsonl (or --fetch-live per trace).
3. Optionally DELETE old RAGAS/FABLES observations via Langfuse public API.
4. Runs RagasEvaluator: default is **FABLES-only** **in-place** replay: ``generation-update`` /
   ``span-update`` on the **canonical** (earliest by export time) ``fables_faithfulness`` span plus
   ``fables_extract_claims`` and ``fables_verify_all_claims`` — no new observation ids, no leaf deletes.
   Use ``--fables-recreate-leaves`` with ``--delete-old`` for the **legacy** path (delete those leaves
   then ``generation-create`` again). Use ``--replace-fables-block`` with ``--delete-old`` to remove
   the whole FABLES block under ``ragas_evaluation`` and recreate it (new span + ids).
   On stock Langfuse, observation ``start_time`` may stay wrong after update — use
   ``--replace-fables-block --delete-old`` to fix broken timeline durations.
   Optional ``--full-ragas-replay`` restores the old all-metrics behavior.
5. After a successful run, upserts **trace-level** metadata (name, input, output) via
   ``trace-create`` ingestion so the trace shows e.g. **StoryGenerationWorkflow** again
   (from ``Eval_Data/Traces/*.jsonl`` or ``GET /api/public/traces/{id}`` when ``--fetch-live``).
   The upsert uses a **fresh ingestion timestamp** so the UI does not keep showing the last
   eval generation as trace input/output.

**Metadata-only repair:** ``--restore-trace-metadata-only --trace-id <id>`` re-sends trace I/O from
local JSONL without running RAGAS (no OPENROUTER needed).

Requires: OPENROUTER_API_KEY, LANGFUSE_* (see ObservabilityConfig), ragas, .env loaded (except for ``--restore-trace-metadata-only``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

# Load .env before settings
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from settings import LLMProviderConfig, ObservabilityConfig  # noqa: E402

from scripts.lib.replay_faithfulness_io import (  # noqa: E402
    build_replay_row,
    glob_observation_jsonl,
    glob_trace_jsonl,
    load_observations_jsonl_files,
    load_trace_ids_from_csv,
    slim_trace_row_for_restore,
    load_trace_row_for_id,
)

DEFAULT_WORKFLOW_TRACE_NAME = "StoryGenerationWorkflow"


def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "json") and callable(obj.json) and hasattr(obj, "dict"):
        return json.loads(obj.json())
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    return obj


def _build_langfuse_sdk():
    from langfuse import Langfuse

    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
    host = (ObservabilityConfig.LANGFUSE_HOST or "").strip()
    if not pk or not sk or not host:
        raise SystemExit("LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST required.")
    return Langfuse(public_key=pk, secret_key=sk, host=host.rstrip("/"))


def fetch_observations_for_trace(client: Any, trace_id: str, obs_limit: int) -> List[Dict[str, Any]]:
    page = 1
    rows: List[Dict[str, Any]] = []
    while True:
        resp = client.api.observations.get_many(
            trace_id=trace_id,
            limit=obs_limit,
            page=page,
        )
        data = getattr(resp, "data", None) or []
        for obs in data:
            rows.append(_to_jsonable(obs))
        meta = resp.meta
        if page >= meta.total_pages:
            break
        page += 1
    return rows


FABLES_REPLAY_SCORE_NAMES = frozenset({"fables_faithfulness", "ragas_standard_faithfulness"})


def run_restore_trace_metadata_only(args: argparse.Namespace) -> None:
    """Re-send trace-create from JSONL only (no RAGAS, no deletes). Fixes list I/O after replay."""
    if not args.trace_id:
        raise SystemExit("--trace-id required with --restore-trace-metadata-only")
    eval_data = ROOT / "Eval_Data"
    traces_dir = Path(args.traces_dir) if args.traces_dir else eval_data / "Traces"
    trace_paths = (
        [Path(p) for p in args.traces_jsonl] if args.traces_jsonl else glob_trace_jsonl(traces_dir)
    )
    langfuse = None
    if not args.dry_run:
        from workflows.story_agent.integrations.langfuse_client import get_langfuse  # noqa: E402

        langfuse = get_langfuse()
        if not langfuse.enabled:
            raise SystemExit("Langfuse is disabled or unavailable (check LANGFUSE_* and install).")

    for tid in args.trace_id:
        local = load_trace_row_for_id(trace_paths, tid)
        if local:
            row = slim_trace_row_for_restore(local)
            src = "local"
        elif args.fetch_live:
            api_row = fetch_trace_metadata_http(tid)
            if not api_row:
                print(f"[WARN] no API trace row for {tid[:12]}… — skip")
                continue
            row = slim_trace_row_for_restore(api_row)
            src = "api"
        else:
            print(
                f"[WARN] no trace JSONL row for {tid[:12]}… — skip "
                f"(add Eval_Data/Traces export or use --fetch-live)",
            )
            continue
        if args.dry_run:
            print(f"[dry-run] restore trace {tid[:12]}… from {src} name={row.get('name')!r}")
            continue
        assert langfuse is not None
        err = restore_workflow_trace_metadata(langfuse, tid, row)
        if err:
            print(f"[ERROR] {tid[:12]}… {err}")
        else:
            print(f"[OK] trace metadata restored {tid[:12]}… from {src} name={row.get('name')!r}")
        langfuse.flush()


def fetch_trace_metadata_http(trace_id: str) -> Optional[Dict[str, Any]]:
    """GET /api/public/traces/{traceId} — top-level name, input, output for trace upsert."""
    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
    host = (ObservabilityConfig.LANGFUSE_HOST or "").strip().rstrip("/")
    if not pk or not sk or not host:
        return None
    url = f"{host}/api/public/traces/{trace_id}"
    try:
        r = httpx.get(url, auth=(pk, sk), timeout=60.0)
        if r.status_code != 200:
            return None
        data = r.json()
        if not isinstance(data, dict):
            return None
        # Drop large nested payloads; keep trace-level fields for ingestion.
        slim = {
            k: data.get(k)
            for k in (
                "id",
                "name",
                "input",
                "output",
                "timestamp",
                "environment",
                "userId",
                "sessionId",
                "tags",
                "public",
                "metadata",
                "release",
                "version",
            )
            if k in data
        }
        return slim
    except Exception:
        return None


def restore_workflow_trace_metadata(
    langfuse: Any,
    trace_id: str,
    trace_row: Dict[str, Any],
    *,
    default_name: str = DEFAULT_WORKFLOW_TRACE_NAME,
) -> Optional[str]:
    """Upsert trace row so UI shows workflow name + story I/O, not a nested metric name."""
    name = (trace_row.get("name") or "").strip() or default_name
    inp = trace_row.get("input")
    out = trace_row.get("output")
    env = trace_row.get("environment")
    # Use a fresh ingestion timestamp (do not reuse export ``timestamp``): Langfuse orders
    # trace updates by event time; an old timestamp lets newer observations “win” the trace
    # list input/output (e.g. FABLES eval JSON instead of the story prompt / final_story).
    return langfuse.ingestion_trace_upsert(
        trace_id=trace_id,
        name=name,
        input=inp,
        output=out,
        timestamp=None,
        environment=str(env) if env else "default",
        user_id=trace_row.get("userId"),
        session_id=trace_row.get("sessionId"),
        tags=trace_row.get("tags") if isinstance(trace_row.get("tags"), list) else None,
        public=trace_row.get("public") if isinstance(trace_row.get("public"), bool) else None,
        metadata=trace_row.get("metadata") if isinstance(trace_row.get("metadata"), dict) else None,
    )


def delete_observation_http(observation_id: str) -> tuple[bool, str]:
    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
    host = (ObservabilityConfig.LANGFUSE_HOST or "").strip().rstrip("/")
    url = f"{host}/api/public/observations/{observation_id}"
    try:
        r = httpx.delete(url, auth=(pk, sk), timeout=60.0)
        if r.status_code in (200, 202, 204):
            return True, ""
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return False, str(e)


def delete_scores_by_names_for_trace(trace_id: str, names: Set[str]) -> int:
    """Remove Langfuse scores on this trace with given names (replace, not duplicate)."""
    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
    host = (ObservabilityConfig.LANGFUSE_HOST or "").strip().rstrip("/")
    removed = 0
    page = 1
    try:
        with httpx.Client(timeout=60.0) as client:
            while True:
                r = client.get(
                    f"{host}/api/public/v2/scores",
                    auth=(pk, sk),
                    params={"traceId": trace_id, "page": page, "limit": 100},
                )
                if r.status_code != 200:
                    print(f"[WARN] list scores: HTTP {r.status_code}: {r.text[:200]}")
                    break
                body = r.json()
                rows = body.get("data") if isinstance(body, dict) else None
                if not rows:
                    break
                meta = body.get("meta") or {}
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("name") or "") not in names:
                        continue
                    sid = row.get("id")
                    if not sid:
                        continue
                    dr = client.delete(
                        f"{host}/api/public/scores/{sid}",
                        auth=(pk, sk),
                    )
                    if dr.status_code in (200, 202, 204):
                        removed += 1
                    else:
                        print(f"[WARN] delete score {sid}: HTTP {dr.status_code}")
                total_pages = int(meta.get("totalPages") or 1)
                if page >= total_pages:
                    break
                page += 1
    except Exception as e:
        print(f"[WARN] delete_scores_by_names_for_trace: {e}")
    return removed


def build_ragas_evaluator(langfuse_wrapper: Any):
    from openai import AsyncOpenAI
    from ragas.embeddings import OpenAIEmbeddings
    from ragas.llms import llm_factory

    from workflows.story_agent.agents.critic.eval_ragas import RAGAS_AVAILABLE, RagasEvaluator

    if not RAGAS_AVAILABLE:
        raise SystemExit("ragas is not installed.")

    or_api_key = LLMProviderConfig.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")
    or_base_url = LLMProviderConfig.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1"
    ragas_model_name = os.environ.get("LLM_MODEL", "google/gemini-2.5-flash")
    ragas_embed = os.environ.get("RAGAS_EMBED_MODEL", "google/gemini-embedding-001")

    if not or_api_key:
        raise SystemExit("OPENROUTER_API_KEY / LLMProviderConfig.OPENROUTER_API_KEY required.")

    _or_llm_client = AsyncOpenAI(
        api_key=or_api_key,
        base_url=or_base_url,
        default_headers={
            "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", ""),
            "X-Title": "RAGAS faithfulness replay",
        },
    )
    _or_embed_client = AsyncOpenAI(api_key=or_api_key, base_url=or_base_url)
    ragas_llm = llm_factory(
        ragas_model_name, provider="openai", client=_or_llm_client, max_tokens=8192
    )
    ragas_embeddings = OpenAIEmbeddings(client=_or_embed_client, model=ragas_embed)

    return RagasEvaluator(
        ragas_llm=ragas_llm,
        embeddings=ragas_embeddings,
        openai_client=_or_llm_client,
        model_name=ragas_model_name,
        langfuse=langfuse_wrapper,
    )


async def replay_one_trace(
    evaluator: Any,
    langfuse: Any,
    trace_id: str,
    question: str,
    answer: str,
    contexts: List[str],
    parent_span_id: Optional[str],
    dry_run: bool,
    *,
    full_ragas_replay: bool,
    fables_recreate_span: bool = False,
    fables_update_in_place: bool = False,
    fables_in_place_ids: Optional[Dict[str, str]] = None,
    fables_export_timeline: Optional[Dict[str, Dict[str, str]]] = None,
    trace_restore_row: Optional[Dict[str, Any]] = None,
    no_restore_trace: bool = False,
) -> Dict[str, Any]:
    if dry_run:
        src = (
            "local_export"
            if trace_restore_row and trace_restore_row.get("_source") == "local"
            else (
                "api"
                if trace_restore_row and trace_restore_row.get("_source") == "api"
                else "none"
            )
        )
        return {
            "trace_id": trace_id,
            "dry_run": True,
            "full_ragas_replay": full_ragas_replay,
            "fables_recreate_span": fables_recreate_span,
            "fables_update_in_place": fables_update_in_place,
            "fables_in_place_ids": fables_in_place_ids,
            "fables_export_timeline": fables_export_timeline,
            "parent_span_id": parent_span_id,
            "trace_restore_planned": not no_restore_trace and trace_restore_row is not None,
            "trace_restore_source": src,
            "trace_restore_name": (trace_restore_row or {}).get("name") or DEFAULT_WORKFLOW_TRACE_NAME,
        }

    langfuse.set_faithfulness_replay_trace(trace_id, parent_span_id)
    try:
        scores = await evaluator.run(
            question=question,
            answer=answer,
            contexts=contexts,
            trace_id=trace_id,
            fables_replay_only=not full_ragas_replay,
            fables_recreate_span=fables_recreate_span and not fables_update_in_place,
            fables_in_place_ids=fables_in_place_ids if fables_update_in_place else None,
            fables_export_timeline=fables_export_timeline,
        )
        langfuse.flush()
        out: Dict[str, Any] = {"trace_id": trace_id, "scores": scores, "ok": True}
        if not no_restore_trace and trace_restore_row:
            row = slim_trace_row_for_restore(
                {k: v for k, v in trace_restore_row.items() if k != "_source"}
            )
            terr = restore_workflow_trace_metadata(langfuse, trace_id, row)
            out["trace_restore"] = {"ok": terr is None, "error": terr}
            if terr:
                print(f"[WARN] trace metadata restore: {terr}")
            else:
                nm = row.get("name") or DEFAULT_WORKFLOW_TRACE_NAME
                print(f"[INFO] trace metadata restored: name={nm!r}")
            langfuse.flush()
        return out
    finally:
        langfuse.clear_faithfulness_replay_trace()


async def async_main(args: argparse.Namespace) -> None:
    eval_data = ROOT / "Eval_Data"
    obs_dir = Path(args.observations_dir) if args.observations_dir else eval_data / "Observations"
    traces_dir = Path(args.traces_dir) if args.traces_dir else eval_data / "Traces"
    trace_paths = (
        [Path(p) for p in args.traces_jsonl] if args.traces_jsonl else glob_trace_jsonl(traces_dir)
    )

    if not args.skip_backup:
        import subprocess

        backup_script = ROOT / "scripts" / "backup_eval_data.py"
        subprocess.run(
            [sys.executable, str(backup_script)],
            check=True,
            cwd=str(ROOT),
        )

    jsonl_paths = [Path(p) for p in args.obs_jsonl] if args.obs_jsonl else glob_observation_jsonl(obs_dir)
    if not jsonl_paths:
        raise SystemExit(f"No JSONL files under {obs_dir}")

    by_trace = load_observations_jsonl_files(jsonl_paths)

    want_lower: Optional[Set[str]] = None
    if args.trace_id:
        want_lower = {t.lower() for t in args.trace_id}

    csv_path: Optional[Path] = None
    csv_ids_sorted: Optional[List[str]] = None
    csv_lower: Optional[Set[str]] = None
    if args.traces_csv:
        csv_path = Path(args.traces_csv)
        ids_set = load_trace_ids_from_csv(csv_path)
        csv_lower = {i.lower() for i in ids_set}
        csv_ids_sorted = sorted(ids_set)

    trace_ids: List[str]
    if csv_path is not None and args.fetch_live:
        # Every CSV id is processed; local JSONL only pre-seeds obs when present (API fills the rest).
        trace_ids = []
        for tid in csv_ids_sorted or []:
            if want_lower is not None and tid.lower() not in want_lower:
                continue
            trace_ids.append(tid)
        new_by_trace: Dict[str, List[Dict[str, Any]]] = {}
        for tid in trace_ids:
            obs_local: Optional[List[Dict[str, Any]]] = None
            for k, v in by_trace.items():
                if k.lower() == tid.lower():
                    obs_local = v
                    break
            new_by_trace[tid] = list(obs_local) if obs_local is not None else []
        by_trace = new_by_trace
    else:
        if want_lower is not None:
            by_trace = {k: v for k, v in by_trace.items() if k.lower() in want_lower}
        if csv_lower is not None:
            by_trace = {k: v for k, v in by_trace.items() if k.lower() in csv_lower}
        trace_ids = list(by_trace.keys())

    if args.limit:
        trace_ids = trace_ids[: args.limit]

    lf_sdk = None
    if args.fables_recreate_leaves and args.fables_update_in_place:
        raise SystemExit("Pilih salah satu: --fables-recreate-leaves atau --fables-update-in-place")

    if args.fables_update_in_place:
        print(
            "[INFO] --fables-update-in-place: default FABLES mode is already in-place; flag is optional. "
            "Langfuse may keep immutable observation start_time on merge — see docs/replay_faithfulness_langfuse.md."
        )

    if args.fetch_live or args.delete_old:
        lf_sdk = _build_langfuse_sdk()

    if args.fetch_live:
        for tid in trace_ids:
            by_trace[tid] = fetch_observations_for_trace(lf_sdk, tid, args.obs_limit)

    from workflows.story_agent.integrations.langfuse_client import get_langfuse  # noqa: E402

    langfuse_wrapper = get_langfuse()
    if not langfuse_wrapper.enabled:
        raise SystemExit("Langfuse is disabled or unavailable (check LANGFUSE_* and install).")

    evaluator = build_ragas_evaluator(langfuse_wrapper)

    results: List[Dict[str, Any]] = []
    for tid in trace_ids:
        obs_list = by_trace.get(tid) or []
        row = build_replay_row(
            obs_list,
            full_ragas_replay=args.full_ragas_replay,
            replace_fables_block=args.replace_fables_block,
            fables_recreate_leaves=args.fables_recreate_leaves,
            fables_timeline_from_export=not args.fables_timeline_wall_clock,
        )
        if not row:
            if args.fables_recreate_leaves and not args.full_ragas_replay:
                err = (
                    "missing fables_verify_all_claims payload / question, or no fables_faithfulness "
                    "span with extract+verify children for --fables-recreate-leaves"
                )
            elif args.replace_fables_block and not args.full_ragas_replay:
                err = (
                    "missing fables_verify_all_claims payload / question, or no ragas_evaluation "
                    "span for --replace-fables-block"
                )
            else:
                err = (
                    "missing fables_verify_all_claims payload / question, or no fables_faithfulness "
                    "span with extract+verify for default in-place replay — try --full-ragas-replay, "
                    "--replace-fables-block, or --fetch-live if export ids are stale"
                )
            results.append({"trace_id": tid, "ok": False, "error": err})
            continue

        local_trace = load_trace_row_for_id(trace_paths, tid)
        if local_trace:
            trace_restore_payload: Optional[Dict[str, Any]] = {**local_trace, "_source": "local"}
        elif args.fetch_live:
            api_trace = fetch_trace_metadata_http(tid)
            trace_restore_payload = {**api_trace, "_source": "api"} if api_trace else None
        else:
            trace_restore_payload = None
        if trace_restore_payload is None and not args.no_restore_trace and not args.dry_run:
            print(
                f"[INFO] no trace export row for {tid[:12]}… — skip trace rename "
                f"(add Eval_Data/Traces export or use --fetch-live)"
            )

        if (
            args.replace_fables_block
            and not args.delete_old
            and not args.dry_run
            and not args.full_ragas_replay
        ):
            print(
                "[WARN] --replace-fables-block without --delete-old leaves old FABLES observations; "
                "use --delete-old to remove them before replay."
            )

        if args.delete_old and lf_sdk is not None and not args.dry_run:
            oids_to_del = row.get("observation_ids_to_remove") or []
            if not oids_to_del and not row.get("full_ragas_replay"):
                print(
                    f"[INFO] --delete-old: no observation DELETEs for {tid[:12]}… in this mode "
                    "(default FABLES is in-place; use --fables-recreate-leaves or --replace-fables-block "
                    "to schedule leaf/block removal). FABLES score dedupe still runs below when applicable."
                )
            if not args.full_ragas_replay:
                n = delete_scores_by_names_for_trace(tid, FABLES_REPLAY_SCORE_NAMES)
                if n:
                    print(f"[INFO] removed {n} duplicate FABLES scores on trace {tid[:12]}…")
            for oid in oids_to_del:
                ok, err = delete_observation_http(oid)
                if not ok:
                    print(f"[WARN] delete {oid}: {err}")
                time.sleep(args.delete_sleep_s)

        out = await replay_one_trace(
            evaluator,
            langfuse_wrapper,
            tid,
            row["question"],
            row["answer"],
            row["contexts"],
            row.get("parent_span_id"),
            args.dry_run,
            full_ragas_replay=bool(row.get("full_ragas_replay")),
            fables_recreate_span=bool(row.get("fables_recreate_span")),
            fables_update_in_place=bool(row.get("fables_update_in_place")),
            fables_in_place_ids=row.get("fables_in_place_ids"),
            fables_export_timeline=row.get("fables_export_timeline"),
            trace_restore_row=trace_restore_payload,
            no_restore_trace=args.no_restore_trace,
        )
        results.append(out)
        print(json.dumps(out, default=str)[:500])

    summary_path = Path(args.write_summary) if args.write_summary else None
    if summary_path:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(f"Wrote summary: {summary_path}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-backup", action="store_true", help="Do not copy Eval_Data to backups/")
    p.add_argument("--dry-run", action="store_true", help="Only validate payloads; no Langfuse writes")
    p.add_argument("--fetch-live", action="store_true", help="Replace observations per trace from Langfuse API")
    p.add_argument("--observations-dir", type=str, default=None, help="Folder with *.jsonl (default Eval_Data/Observations)")
    p.add_argument(
        "--traces-dir",
        type=str,
        default=None,
        help="Folder with traces *.jsonl for trace-level name/input/output restore (default Eval_Data/Traces)",
    )
    p.add_argument(
        "--traces-jsonl",
        nargs="*",
        default=None,
        help="Explicit traces JSONL files (default: all *.jsonl in traces dir)",
    )
    p.add_argument(
        "--no-restore-trace",
        action="store_true",
        help="Do not upsert trace name/input/output (skip StoryGenerationWorkflow restore)",
    )
    p.add_argument(
        "--obs-jsonl",
        nargs="*",
        default=None,
        help="Explicit JSONL files (default: all *.jsonl in observations dir)",
    )
    p.add_argument("--traces-csv", type=str, default=None, help="Restrict to trace ids present in this CSV (id column)")
    p.add_argument("--trace-id", nargs="*", default=None, help="Only these trace IDs")
    p.add_argument("--limit", type=int, default=0, help="Max traces to process (0 = all)")
    p.add_argument("--delete-old", action="store_true", help="DELETE old RAGAS/FABLES observations before replay")
    p.add_argument(
        "--full-ragas-replay",
        action="store_true",
        help="Re-run Answer Relevancy + Context Relevance + FABLES; parent=critic_agent; "
        "deletes full OBS_NAMES_TO_REPLACE set. Default: FABLES-only under existing fables_faithfulness SPAN.",
    )
    p.add_argument(
        "--replace-fables-block",
        action="store_true",
        help="FABLES-only: parent_span_id=ragas_evaluation; with --delete-old removes "
        "fables_faithfulness + fables_extract_claims + fables_verify_all_claims under that RAGAS span, "
        "then creates a new fables_faithfulness span (new FABLES pipeline). Incompatible with meaning of "
        "--full-ragas-replay (full mode wins if both set).",
    )
    p.add_argument(
        "--fables-recreate-leaves",
        action="store_true",
        help="FABLES-only (legacy): delete fables_extract_claims + fables_verify_all_claims under the "
        "chosen fables_faithfulness span (--delete-old) then create new generations. Default without this "
        "flag is in-place updates on the earliest (canonical) extract+verify ids.",
    )
    p.add_argument(
        "--fables-update-in-place",
        action="store_true",
        help="Optional no-op: default FABLES replay is already in-place. Use --fetch-live if JSONL ids "
        "are stale. Mutually exclusive with --fables-recreate-leaves.",
    )
    p.add_argument(
        "--fables-timeline-wall-clock",
        action="store_true",
        help="Use wall clock for FABLES observation start/end during replay instead of "
        "timestamps from the observation export (default: reuse export timeline).",
    )
    p.add_argument("--no-delete-old", action="store_true", help="Skip deletion (default if neither delete flag)")
    p.add_argument("--delete-sleep-s", type=float, default=0.15, help="Pause between DELETE calls")
    p.add_argument("--obs-limit", type=int, default=100, help="Page size for --fetch-live")
    p.add_argument("--write-summary", type=str, default=None, help="Write JSON summary path")
    p.add_argument(
        "--restore-trace-metadata-only",
        action="store_true",
        help="Only upsert trace name/input/output from Traces/*.jsonl (no RAGAS, no deletes). "
        "Use after replay when the list view still shows eval JSON; prefer local export over --fetch-live.",
    )
    args = p.parse_args()
    if args.no_delete_old:
        args.delete_old = False
    if args.restore_trace_metadata_only:
        run_restore_trace_metadata_only(args)
        return
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
