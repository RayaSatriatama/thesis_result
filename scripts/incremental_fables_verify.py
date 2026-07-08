#!/usr/bin/env python3
"""Incremental FABLES verification for traces with more than 10 claims.

Workflow:
1. Backup local Eval_Data (Traces + Observations) via scripts/backup_eval_data.py.
2. Optionally fetch live observations from Langfuse so observation ids match the server.
3. Identify traces with claims_extracted > total_existing_verdicts.
4. Verify the remaining claims in chunks of 10, creating new generations named
   ``fables_verify_all_claims_2``, ``fables_verify_all_claims_3``, etc.
5. Anchor every new generation's startTime/endTime to the latest existing
   ``fables_verify_all_claims*`` endTime (instant event at the end of the original
   verification window) so trace duration in Langfuse UI does not change.
6. Patch the output of three SPANs in place (fables_faithfulness, ragas_evaluation,
   critic_agent) with new FABLES totals - non-FABLES fields are preserved exactly,
   and span timestamps are reused from the export so server-side immutable startTime
   stays untouched and endTime is sent identical (no duration change).
7. Snapshot existing trace-level scores before overwriting them; write the
   before/after_planned diff to output/incremental_runs/<trace_id>_<UTC>.json.
8. Write trace-level scores using the proper FABLES formulas:
       fables_faithfulness          = faithful / max(faithful + unfaithful, 1)
       ragas_standard_faithfulness  = faithful / max(total, 1)

Pilot mode: pass ``--trace-id <id>`` (and ideally ``--dry-run`` first). Batch mode:
pass ``--auto-discover`` to pick every trace whose verdicts < extracted claims.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

load_dotenv(ROOT / ".env")

from settings import LLMProviderConfig, ObservabilityConfig  # noqa: E402
from workflows.story_agent.agents.critic.eval_ragas import RagasEvaluator  # noqa: E402
from workflows.story_agent.integrations.langfuse_client import get_langfuse  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("incremental_fables")

CHUNK_SIZE = 10
PRIMARY_GEN_NAME = "fables_verify_all_claims"
GEN_NAME_RE = re.compile(rf"^{PRIMARY_GEN_NAME}(?:_(\d+))?$")
FABLES_NUMERIC_KEYS = (
    "fables_faithfulness",
    "ragas_standard_faithfulness",
    "fables_claims_total",
    "fables_claims_faithful",
    "fables_claims_unfaithful",
    "fables_claims_cant_verify",
    "fables_claims_partial_support",
)
SPAN_NAMES_TO_PATCH = ("fables_faithfulness", "ragas_evaluation", "critic_agent")

# Preferred key order for nested score maps shown in Langfuse UI.
_SCORE_ORDER_PREFIX = (
    "answer_relevancy",
    "context_relevance",
    "fables_faithfulness",
    "ragas_standard_faithfulness",
    "fables_claims_total",
    "fables_claims_faithful",
    "fables_claims_unfaithful",
    "fables_claims_partial_support",
    "fables_claims_cant_verify",
)


# -------------------------------------------------------------------------
# JSON / observation utilities
# -------------------------------------------------------------------------


def _coerce_json(val: Any) -> Any:
    """Decode JSON string into Python object; return original value otherwise."""
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return val
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return val
    return val


def _utc_iso_ms_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _to_iso_z(val: Any) -> str:
    """Normalize Langfuse time fields from export/API into ISO-8601 string with Z."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, datetime):
        dt = val.astimezone(timezone.utc) if val.tzinfo else val.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return str(val).strip()


def _glob_observation_files(obs_dir: Path) -> List[Path]:
    paths = sorted(obs_dir.glob("*.jsonl"))
    if not paths:
        raise SystemExit(f"No JSONL files found under {obs_dir}")
    return paths


def _load_observations_for_trace(jsonl_paths: List[Path], trace_id: str) -> List[Dict[str, Any]]:
    """Load all observations matching trace_id from local JSONL exports."""
    rows: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for path in jsonl_paths:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obs = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obs.get("traceId") != trace_id:
                    continue
                oid = obs.get("id")
                if oid and oid in seen_ids:
                    continue
                if oid:
                    seen_ids.add(oid)
                rows.append(obs)
    return rows


def _build_langfuse_sdk():
    """Build Langfuse SDK client for live API access (fetch observations / scores)."""
    from langfuse import Langfuse

    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
    host = (ObservabilityConfig.LANGFUSE_HOST or "").strip()
    if not pk or not sk or not host:
        raise SystemExit("LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST required.")
    return Langfuse(public_key=pk, secret_key=sk, host=host.rstrip("/"))


def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    # Pydantic v1 compatibility (some Langfuse SDK response models).
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return _to_jsonable(obj.dict())
        except Exception:
            pass
    if hasattr(obj, "json") and callable(getattr(obj, "json")):
        try:
            return _to_jsonable(json.loads(obj.json()))
        except Exception:
            pass
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    return obj


def _fetch_observations_live(client: Any, trace_id: str, page_size: int = 100) -> List[Dict[str, Any]]:
    page = 1
    rows: List[Dict[str, Any]] = []
    while True:
        resp = client.api.observations.get_many(trace_id=trace_id, limit=page_size, page=page)
        data = getattr(resp, "data", None) or []
        for obs in data:
            rows.append(_to_jsonable(obs))
        meta = resp.meta
        if page >= meta.total_pages:
            break
        page += 1
    return rows


# -------------------------------------------------------------------------
# Claim / context / verdicts extraction
# -------------------------------------------------------------------------


def _extract_claims_from_obs(obs_list: List[Dict[str, Any]]) -> List[str]:
    """Read full claim list from fables_extract_claims.output.claims (logged before MAX_CLAIMS cap)."""
    extract = next(
        (
            o
            for o in obs_list
            if o.get("name") == "fables_extract_claims" and o.get("type") == "GENERATION"
        ),
        None,
    )
    if not extract:
        raise ValueError("fables_extract_claims observation missing - cannot determine claim list")
    output = _coerce_json(extract.get("output"))
    if not isinstance(output, dict):
        raise ValueError("fables_extract_claims.output is not a dict")
    claims = output.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("fables_extract_claims.output.claims is empty or missing")
    return [str(c) for c in claims]


def _extract_context_from_obs(obs_list: List[Dict[str, Any]]) -> List[str]:
    """Find contexts list from FABLES verify obs first, else ragas_context_relevance, else fables_faithfulness."""
    candidates = [
        ("fables_verify_all_claims", "GENERATION"),
        ("ragas_context_relevance", "GENERATION"),
        ("fables_faithfulness", "SPAN"),
        ("ragas_answer_relevancy", "GENERATION"),
    ]
    for name, obs_type in candidates:
        for obs in obs_list:
            if obs.get("name") != name or obs.get("type") != obs_type:
                continue
            payload = _coerce_json(obs.get("input"))
            if not isinstance(payload, dict):
                continue
            ctxs = payload.get("contexts")
            if isinstance(ctxs, list) and ctxs:
                cleaned = [str(c) for c in ctxs if c is not None and str(c).strip()]
                if cleaned:
                    logger.info(f"context source: {name} ({obs_type}), {len(cleaned)} chunk(s)")
                    return cleaned
    raise ValueError(
        "No contexts found in fables_verify_all_claims / ragas_context_relevance / "
        "fables_faithfulness / ragas_answer_relevancy. Try --fetch-live so the input "
        "payload includes the contexts list."
    )


def _parse_generation_index(name: str) -> Optional[int]:
    """Return the suffix index of a fables_verify_all_claims[_N] generation; 1 means primary."""
    m = GEN_NAME_RE.match(name or "")
    if not m:
        return None
    suffix = m.group(1)
    return int(suffix) if suffix else 1


def _collect_existing_verify_generations(
    obs_list: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Return (sorted_obs, all_verdicts, max_index).

    sorted_obs: existing fables_verify_all_claims[_N] generations sorted by suffix index ascending.
    all_verdicts: concatenated verdicts from all those generations.
    max_index: highest suffix index seen (1 means only the primary exists).
    """
    matches: List[Tuple[int, Dict[str, Any]]] = []
    for obs in obs_list:
        if obs.get("type") != "GENERATION":
            continue
        idx = _parse_generation_index(obs.get("name") or "")
        if idx is None:
            continue
        matches.append((idx, obs))
    matches.sort(key=lambda x: x[0])

    verdicts: List[Dict[str, Any]] = []
    for _, obs in matches:
        out = _coerce_json(obs.get("output"))
        if isinstance(out, dict):
            chunk = out.get("verdicts")
            if isinstance(chunk, list):
                verdicts.extend(chunk)
        elif isinstance(out, list):
            verdicts.extend(out)

    max_idx = max((idx for idx, _ in matches), default=0)
    return [m[1] for m in matches], verdicts, max_idx


def _find_span_obs(obs_list: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    spans = [o for o in obs_list if o.get("name") == name and o.get("type") == "SPAN"]
    if not spans:
        return None
    spans.sort(key=lambda o: o.get("startTime") or "")
    return spans[0]


# -------------------------------------------------------------------------
# Score handling
# -------------------------------------------------------------------------


def _fetch_existing_scores(trace_id: str, names: Iterable[str]) -> Dict[str, Any]:
    """GET /api/public/v2/scores?traceId=<id> returning {name: {value, comment, ...}} for selected names."""
    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
    host = (ObservabilityConfig.LANGFUSE_HOST or "").strip().rstrip("/")
    if not pk or not sk or not host:
        return {}
    out: Dict[str, Any] = {}
    page = 1
    targets = set(names)
    try:
        with httpx.Client(timeout=60.0) as client:
            while True:
                resp = client.get(
                    f"{host}/api/public/v2/scores",
                    auth=(pk, sk),
                    params={"traceId": trace_id, "page": page, "limit": 100},
                )
                if resp.status_code != 200:
                    logger.warning(f"GET scores HTTP {resp.status_code}: {resp.text[:200]}")
                    break
                body = resp.json()
                rows = body.get("data") if isinstance(body, dict) else None
                if not rows:
                    break
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    nm = str(row.get("name") or "")
                    if nm in targets:
                        out.setdefault(nm, []).append(
                            {
                                "value": row.get("value"),
                                "comment": row.get("comment"),
                                "id": row.get("id"),
                                "timestamp": row.get("timestamp"),
                            }
                        )
                meta = body.get("meta") or {}
                total_pages = int(meta.get("totalPages") or 1)
                if page >= total_pages:
                    break
                page += 1
    except Exception as e:
        logger.warning(f"_fetch_existing_scores: {e}")
    return out


def _delete_scores_by_names_for_trace(trace_id: str, names: Iterable[str]) -> int:
    """Delete all scores on this trace with given names (prevents duplicates)."""
    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
    host = (ObservabilityConfig.LANGFUSE_HOST or "").strip().rstrip("/")
    if not pk or not sk or not host:
        return 0
    targets = {str(n) for n in names}
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
                    logger.warning(f"list scores HTTP {r.status_code}: {r.text[:200]}")
                    break
                body = r.json()
                rows = body.get("data") if isinstance(body, dict) else None
                if not rows:
                    break
                meta = body.get("meta") or {}
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("name") or "") not in targets:
                        continue
                    sid = row.get("id")
                    if not sid:
                        continue
                    dr = client.delete(f"{host}/api/public/scores/{sid}", auth=(pk, sk))
                    if dr.status_code in (200, 202, 204):
                        removed += 1
                total_pages = int(meta.get("totalPages") or 1)
                if page >= total_pages:
                    break
                page += 1
    except Exception as e:
        logger.warning(f"_delete_scores_by_names_for_trace: {e}")
    return removed


def _compute_fables_summary(verdicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute FABLES totals + ratios from a list of verdict dicts."""
    faithful = unfaithful = partial = cant_verify = 0
    for v in verdicts:
        if isinstance(v, dict):
            label = str(v.get("verdict", "")).upper()
        else:
            label = str(v).upper()
        if label == "FAITHFUL":
            faithful += 1
        elif label == "UNFAITHFUL":
            unfaithful += 1
        elif label == "PARTIAL_SUPPORT":
            partial += 1
        elif label == "CANT_VERIFY":
            cant_verify += 1
    total = len(verdicts)
    fables_score = round(faithful / max(faithful + unfaithful, 1), 4)
    ragas_strict = round(faithful / max(total, 1), 4)
    return {
        "fables_faithfulness": fables_score,
        "ragas_standard_faithfulness": ragas_strict,
        "fables_claims_total": total,
        "fables_claims_faithful": faithful,
        "fables_claims_unfaithful": unfaithful,
        "fables_claims_partial_support": partial,
        "fables_claims_cant_verify": cant_verify,
    }


def _patch_fables_fields(old_output: Any, new_fables: Dict[str, Any]) -> Any:
    return old_output


def _ordered_patch_dict(
    original: Dict[str, Any],
    updates: Dict[str, Any],
    *,
    add_missing: bool,
) -> Dict[str, Any]:
    """Patch dict while preserving original key order."""
    out: Dict[str, Any] = {}
    for k in original.keys():
        if k in updates:
            out[k] = updates[k]
        else:
            out[k] = original[k]
    if add_missing:
        for k, v in updates.items():
            if k not in out:
                out[k] = v
    return out


def _reorder_with_prefix(d: Dict[str, Any], prefix: Tuple[str, ...]) -> Dict[str, Any]:
    """Return dict reordered with prefix keys first, then the rest in original order."""
    out: Dict[str, Any] = {}
    for k in prefix:
        if k in d:
            out[k] = d[k]
    for k, v in d.items():
        if k in out:
            continue
        out[k] = v
    return out


def _ensure_present_in_ordered_prefix(d: Dict[str, Any], prefix: Tuple[str, ...]) -> Dict[str, Any]:
    """Ensure every prefix key exists in dict, with None when missing."""
    out = dict(d)
    for k in prefix:
        out.setdefault(k, None)
    return out


def _patch_span_output(span_name: str, old_output: Any, new_fables: Dict[str, Any]) -> Any:
    """Patch span output with correct nesting and without duplicate top-level keys.

    Rules:
    - fables_faithfulness: patch at top level, ensure keys exist.
    - ragas_evaluation: patch inside output.scores, ensure keys exist there; remove top-level FABLES duplicates if scores exists.
    - critic_agent: patch inside output.ragas_scores, ensure keys exist there; remove top-level FABLES duplicates if ragas_scores exists.
    """
    if not isinstance(old_output, dict):
        return old_output

    fables_updates = {k: new_fables[k] for k in FABLES_NUMERIC_KEYS}

    if span_name == "fables_faithfulness":
        return _ordered_patch_dict(old_output, fables_updates, add_missing=True)

    if span_name == "ragas_evaluation":
        out = dict(old_output)
        scores = out.get("scores")
        if isinstance(scores, dict):
            patched_scores = _ordered_patch_dict(scores, fables_updates, add_missing=True)
            patched_scores = _ensure_present_in_ordered_prefix(patched_scores, _SCORE_ORDER_PREFIX)
            out["scores"] = _reorder_with_prefix(patched_scores, _SCORE_ORDER_PREFIX)
            # Avoid duplicated FABLES fields at top-level when scores exists.
            for k in FABLES_NUMERIC_KEYS:
                if k in out:
                    del out[k]
        else:
            # No scores dict: do not inject new top-level keys (keep surgical).
            pass
        return out

    if span_name == "critic_agent":
        out = dict(old_output)
        rs = out.get("ragas_scores")
        if isinstance(rs, dict):
            patched_rs = _ordered_patch_dict(rs, fables_updates, add_missing=True)
            patched_rs = _ensure_present_in_ordered_prefix(patched_rs, _SCORE_ORDER_PREFIX)
            out["ragas_scores"] = _reorder_with_prefix(patched_rs, _SCORE_ORDER_PREFIX)
            for k in FABLES_NUMERIC_KEYS:
                if k in out:
                    del out[k]
        else:
            pass
        return out

    # Default: no-op.
    return old_output


def _write_snapshot(
    output_dir: Path,
    trace_id: str,
    before_scores: Dict[str, Any],
    before_summary: Dict[str, Any],
    after_summary: Dict[str, Any],
    new_generations: List[Dict[str, Any]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"{trace_id}_{ts}.json"
    payload = {
        "trace_id": trace_id,
        "snapshot_at": _utc_iso_ms_now(),
        "before": {
            "scores": before_scores,
            "summary": before_summary,
        },
        "after_planned": {
            "summary": after_summary,
        },
        "new_generations": new_generations,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# -------------------------------------------------------------------------
# Backup
# -------------------------------------------------------------------------


def _run_backup(skip: bool) -> Optional[Path]:
    if skip:
        logger.info("backup skipped via --skip-backup")
        return None
    backup_script = ROOT / "scripts" / "backup_eval_data.py"
    logger.info(f"running backup: {backup_script}")
    result = subprocess.run(
        [sys.executable, str(backup_script)],
        check=True,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    dest_line = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
    logger.info(f"backup completed: {dest_line}")
    return Path(dest_line) if dest_line else None


# -------------------------------------------------------------------------
# Evaluator builder (FABLES-only verification, no RAGAS llm needed)
# -------------------------------------------------------------------------


def _build_fables_evaluator() -> RagasEvaluator:
    from openai import AsyncOpenAI

    or_api_key = LLMProviderConfig.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")
    or_base_url = LLMProviderConfig.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1"
    model_name = os.environ.get("LLM_MODEL", "google/gemini-2.5-flash")
    if not or_api_key:
        raise SystemExit("OPENROUTER_API_KEY required.")

    openai_client = AsyncOpenAI(
        api_key=or_api_key,
        base_url=or_base_url,
        default_headers={"X-Title": "Incremental FABLES Verify"},
    )
    # ragas_llm and embeddings are not needed for _fables_verify_claim path.
    return RagasEvaluator(
        ragas_llm=None,
        embeddings=None,
        openai_client=openai_client,
        model_name=model_name,
        langfuse=get_langfuse(),
    )


async def _verify_chunk(evaluator: RagasEvaluator, claims: List[str], context_str: str) -> List[Dict[str, str]]:
    """Run _fables_verify_claim for each claim concurrently, return verdict dicts."""
    raw = await asyncio.gather(
        *[evaluator._fables_verify_claim(c, context_str) for c in claims],
        return_exceptions=False,
    )
    return [{"claim": claims[i], "verdict": str(raw[i]).upper()} for i in range(len(claims))]


# -------------------------------------------------------------------------
# Per-trace processing
# -------------------------------------------------------------------------


async def process_trace(
    trace_id: str,
    obs_list: List[Dict[str, Any]],
    *,
    dry_run: bool,
    snapshot_dir: Path,
    write_snapshot: bool,
    repair_consistency: bool,
    dedupe_scores: bool,
    reorder_spans_only: bool,
) -> Dict[str, Any]:
    """Process one trace; returns a structured result dict for summary output."""
    if not obs_list:
        return {"trace_id": trace_id, "ok": False, "error": "no observations found for trace"}

    if reorder_spans_only:
        span_patch_results: Dict[str, Optional[str]] = {}
        lf_wrapper = get_langfuse()
        if not lf_wrapper.enabled:
            return {"trace_id": trace_id, "ok": False, "error": "Langfuse client disabled"}
        for span_name in ("ragas_evaluation", "critic_agent"):
            span_obs = _find_span_obs(obs_list, span_name)
            if not span_obs or not span_obs.get("id"):
                span_patch_results[span_name] = "span not found in export"
                continue
            old_output = _coerce_json(span_obs.get("output"))
            if not isinstance(old_output, dict):
                span_patch_results[span_name] = "span output not a dict; skipped"
                continue
            # Reorder existing nested dict only; do not inject new values.
            if span_name == "ragas_evaluation" and isinstance(old_output.get("scores"), dict):
                scores = old_output["scores"]
                scores2 = _ensure_present_in_ordered_prefix(dict(scores), _SCORE_ORDER_PREFIX)
                new_output = dict(old_output)
                new_output["scores"] = _reorder_with_prefix(scores2, _SCORE_ORDER_PREFIX)
                # Remove duplicate top-level FABLES fields when scores exists.
                for k in FABLES_NUMERIC_KEYS:
                    if k in new_output:
                        del new_output[k]
            elif span_name == "critic_agent" and isinstance(old_output.get("ragas_scores"), dict):
                rs = old_output["ragas_scores"]
                rs2 = _ensure_present_in_ordered_prefix(dict(rs), _SCORE_ORDER_PREFIX)
                new_output = dict(old_output)
                new_output["ragas_scores"] = _reorder_with_prefix(rs2, _SCORE_ORDER_PREFIX)
                for k in FABLES_NUMERIC_KEYS:
                    if k in new_output:
                        del new_output[k]
            else:
                span_patch_results[span_name] = "no nested scores dict; skipped"
                continue

            sp_start = _to_iso_z(span_obs.get("startTime"))
            sp_end = _to_iso_z(span_obs.get("endTime")) or sp_start
            err = lf_wrapper._ingestion_span_update(
                trace_id=trace_id,
                observation_id=span_obs["id"],
                start_time=sp_start or sp_end,
                end_time=sp_end,
                output_data=new_output,
                name=span_name,
                event_timestamp=_utc_iso_ms_now(),
            )
            span_patch_results[span_name] = err
        lf_wrapper.flush()
        return {
            "trace_id": trace_id,
            "ok": True,
            "reorder_spans_only": True,
            "span_patch_results": span_patch_results,
        }

    try:
        all_claims = _extract_claims_from_obs(obs_list)
    except ValueError as e:
        return {"trace_id": trace_id, "ok": False, "error": str(e)}

    fables_span = _find_span_obs(obs_list, "fables_faithfulness")
    if not fables_span:
        return {"trace_id": trace_id, "ok": False, "error": "fables_faithfulness SPAN missing"}
    fables_span_id = fables_span.get("id")

    existing_gens, existing_verdicts, max_idx = _collect_existing_verify_generations(obs_list)
    if not existing_gens:
        return {
            "trace_id": trace_id,
            "ok": False,
            "error": "no fables_verify_all_claims* generation found - this script only extends existing FABLES results",
        }

    total_claims = len(all_claims)
    already_verified = len(existing_verdicts)
    remaining_claims = all_claims[already_verified:]

    if not remaining_claims and not repair_consistency:
        return {
            "trace_id": trace_id,
            "ok": True,
            "skipped": True,
            "reason": "all claims already verified",
            "total_claims": total_claims,
            "already_verified": already_verified,
            "max_existing_index": max_idx,
        }

    # Anchor: endTime of the latest existing generation (string preserved as-is).
    anchor_end_iso = _to_iso_z(existing_gens[-1].get("endTime"))
    if not anchor_end_iso:
        anchor_end_iso = _to_iso_z(existing_gens[-1].get("startTime"))
    if not anchor_end_iso:
        return {
            "trace_id": trace_id,
            "ok": False,
            "error": "could not determine anchor endTime from existing fables_verify_all_claims",
        }

    try:
        contexts = _extract_context_from_obs(obs_list)
    except ValueError as e:
        return {"trace_id": trace_id, "ok": False, "error": str(e)}
    context_str = "\n\n---\n\n".join(contexts)

    # Plan new generation names: starting at max_idx + 1, one per chunk of 10 remaining claims.
    chunk_plan: List[Dict[str, Any]] = []
    existing_gen_names = {str(o.get("name") or "") for o in obs_list if o.get("type") == "GENERATION"}
    next_idx = max_idx + 1
    for offset in range(0, len(remaining_claims), CHUNK_SIZE):
        chunk = remaining_claims[offset : offset + CHUNK_SIZE]
        absolute_start = already_verified + offset + 1
        absolute_end = absolute_start + len(chunk) - 1
        # Avoid creating a generation with a name that already exists (pre-existing duplicates).
        while f"{PRIMARY_GEN_NAME}_{next_idx}" in existing_gen_names:
            next_idx += 1
        chunk_plan.append(
            {
                "name": f"{PRIMARY_GEN_NAME}_{next_idx}",
                "claims_range": [absolute_start, absolute_end],
                "claims": chunk,
                "claim_count": len(chunk),
            }
        )
        next_idx += 1

    plan_summary = {
        "trace_id": trace_id,
        "total_claims": total_claims,
        "already_verified": already_verified,
        "remaining": len(remaining_claims),
        "max_existing_index": max_idx,
        "anchor_end_iso": anchor_end_iso,
        "fables_span_id": fables_span_id,
        "new_generations_plan": [
            {"name": p["name"], "claims_range": p["claims_range"], "count": p["claim_count"]}
            for p in chunk_plan
        ],
        "spans_to_patch": {
            n: (_find_span_obs(obs_list, n) or {}).get("id")
            for n in SPAN_NAMES_TO_PATCH
        },
    }

    if dry_run:
        plan_summary["dry_run"] = True
        plan_summary["repair_consistency"] = bool(repair_consistency)
        return plan_summary

    # Snapshot existing trace-level scores (jejak) before any write.
    existing_scores = _fetch_existing_scores(
        trace_id, ["fables_faithfulness", "ragas_standard_faithfulness"]
    )
    before_summary = _compute_fables_summary(existing_verdicts)

    # Run verification chunk-by-chunk and create new generations anchored to anchor_end_iso.
    evaluator = _build_fables_evaluator() if chunk_plan else None
    lf_wrapper = get_langfuse()
    if not lf_wrapper.enabled:
        return {"trace_id": trace_id, "ok": False, "error": "Langfuse client disabled"}

    new_verdicts_total: List[Dict[str, str]] = []
    if chunk_plan:
        assert evaluator is not None
        for chunk_info in chunk_plan:
            chunk = chunk_info["claims"]
            gen_name = chunk_info["name"]
            logger.info(
                f"trace {trace_id[:12]}... verifying {len(chunk)} claims -> {gen_name}"
            )
            chunk_verdicts = await _verify_chunk(evaluator, chunk, context_str)
            new_verdicts_total.extend(chunk_verdicts)

            gen_input = {
                "metric": "fables_faithfulness",
                "model": evaluator._ragas_model_name,
                "user_input": "(incremental verification - story unchanged)",
                "total_claims": len(chunk),
                "claims": chunk,
                "context_chars": len(context_str),
                "contexts": contexts,
            }
            gen_output = {
                "faithful": sum(1 for v in chunk_verdicts if v["verdict"] == "FAITHFUL"),
                "unfaithful": sum(1 for v in chunk_verdicts if v["verdict"] == "UNFAITHFUL"),
                "partial_support": sum(1 for v in chunk_verdicts if v["verdict"] == "PARTIAL_SUPPORT"),
                "cant_verify": sum(1 for v in chunk_verdicts if v["verdict"] == "CANT_VERIFY"),
                "verdicts": chunk_verdicts,
            }
            usage = {
                "input": max(1, len(json.dumps(gen_input, ensure_ascii=False)) // 4),
                "output": max(1, len(json.dumps(gen_output, ensure_ascii=False)) // 4),
            }
            usage["total"] = usage["input"] + usage["output"]

            err = lf_wrapper._ingestion_generation_create(
                trace_id=trace_id,
                parent_observation_id=fables_span_id,
                name=gen_name,
                model=evaluator._ragas_model_name,
                generation_input=gen_input,
                output_text=json.dumps(gen_output, ensure_ascii=False, indent=2),
                usage_details=usage,
                metadata={
                    "claims_range": chunk_info["claims_range"],
                    "incremental_batch_index": _parse_generation_index(gen_name),
                    "trace_id": trace_id,
                },
                start_time=anchor_end_iso,
                end_time=anchor_end_iso,
            )
            if err:
                logger.warning(f"generation-create {gen_name} failed: {err}")

    # Combine existing + new for span patches and final score.
    all_verdicts = list(existing_verdicts) + new_verdicts_total
    after_summary = _compute_fables_summary(all_verdicts)

    # Patch the three spans IN PLACE - timestamps reused from export so durations stay.
    span_patch_results: Dict[str, Optional[str]] = {}
    for span_name in SPAN_NAMES_TO_PATCH:
        span_obs = _find_span_obs(obs_list, span_name)
        if not span_obs or not span_obs.get("id"):
            span_patch_results[span_name] = "span not found in export"
            continue
        old_output = _coerce_json(span_obs.get("output"))
        if not isinstance(old_output, dict):
            span_patch_results[span_name] = "span output not a dict; skipped"
            continue
        new_output = _patch_span_output(span_name, old_output, after_summary)
        sp_start = _to_iso_z(span_obs.get("startTime"))
        sp_end = _to_iso_z(span_obs.get("endTime")) or sp_start or anchor_end_iso
        err = lf_wrapper._ingestion_span_update(
            trace_id=trace_id,
            observation_id=span_obs["id"],
            start_time=sp_start or sp_end,
            end_time=sp_end,
            output_data=new_output,
            name=span_name,
            event_timestamp=_utc_iso_ms_now(),
        )
        span_patch_results[span_name] = err

    snapshot_path: Optional[Path] = None
    if write_snapshot:
        snapshot_path = _write_snapshot(
            snapshot_dir,
            trace_id,
            before_scores=existing_scores,
            before_summary=before_summary,
            after_summary=after_summary,
            new_generations=[
                {
                    "name": p["name"],
                    "claims_range": p["claims_range"],
                    "claim_count": p["claim_count"],
                }
                for p in chunk_plan
            ],
        )

    # Write trace-level scores with proper FABLES formulas.
    if dedupe_scores:
        removed = _delete_scores_by_names_for_trace(
            trace_id, ["fables_faithfulness", "ragas_standard_faithfulness"]
        )
        if removed:
            logger.info(f"removed {removed} duplicate score row(s) on {trace_id[:12]}...")

    n_faith = after_summary["fables_claims_faithful"]
    n_unfaith = after_summary["fables_claims_unfaithful"]
    n_partial = after_summary["fables_claims_partial_support"]
    n_cant = after_summary["fables_claims_cant_verify"]
    n_total = after_summary["fables_claims_total"]

    lf_wrapper.create_score(
        name="fables_faithfulness",
        value=after_summary["fables_faithfulness"],
        trace_id=trace_id,
        observation_id=None,
        comment=(
            f"FABLES (Kim et al. §4) incremental: {n_faith}/{n_faith + n_unfaith} "
            f"on Faithful+Unfaithful only; excluded partial={n_partial}, cant_verify={n_cant}"
        ),
        metadata={**after_summary, "incremental_run": True},
    )
    lf_wrapper.create_score(
        name="ragas_standard_faithfulness",
        value=after_summary["ragas_standard_faithfulness"],
        trace_id=trace_id,
        observation_id=None,
        comment=(
            f"Strict faithfulness ratio incremental: {n_faith}/{n_total} "
            f"(only FAITHFUL in numerator)"
        ),
        metadata={**after_summary, "incremental_run": True},
    )
    lf_wrapper.flush()

    return {
        "trace_id": trace_id,
        "ok": True,
        "before": before_summary,
        "after": after_summary,
        "new_generations": [
            {"name": p["name"], "claims_range": p["claims_range"]} for p in chunk_plan
        ],
        "span_patch_results": span_patch_results,
        "snapshot": str(snapshot_path) if snapshot_path else None,
    }


# -------------------------------------------------------------------------
# Trace discovery (auto-discover)
# -------------------------------------------------------------------------


def _group_observations_by_trace(jsonl_paths: List[Path]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    seen_pairs: set = set()
    for path in jsonl_paths:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obs = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tid = obs.get("traceId")
                oid = obs.get("id")
                if not tid:
                    continue
                key = (tid, oid) if oid else None
                if key and key in seen_pairs:
                    continue
                if key:
                    seen_pairs.add(key)
                grouped.setdefault(tid, []).append(obs)
    return grouped


def _discover_traces_with_pending_claims(grouped: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Return trace ids whose extracted claims > total existing verdicts."""
    pending: List[str] = []
    for tid, obs_list in grouped.items():
        try:
            claims = _extract_claims_from_obs(obs_list)
        except ValueError:
            continue
        _, verdicts, _ = _collect_existing_verify_generations(obs_list)
        if len(claims) > len(verdicts):
            pending.append(tid)
    return pending


# -------------------------------------------------------------------------
# CLI / main
# -------------------------------------------------------------------------


def _print_summary(results: List[Dict[str, Any]]) -> None:
    print()
    print("=" * 60)
    print(" INCREMENTAL FABLES VERIFY - SUMMARY ".center(60, "="))
    print("=" * 60)
    for r in results:
        tid = r.get("trace_id", "?")
        if r.get("dry_run"):
            print(
                f"[PLAN] {tid[:12]}... total={r.get('total_claims')} "
                f"verified={r.get('already_verified')} remaining={r.get('remaining')} "
                f"new_gens={[p['name'] for p in r.get('new_generations_plan', [])]}"
            )
            continue
        if not r.get("ok"):
            print(f"[FAIL] {tid[:12]}... {r.get('error')}")
            continue
        if r.get("skipped"):
            print(f"[SKIP] {tid[:12]}... {r.get('reason')}")
            continue
        before = r.get("before", {})
        after = r.get("after", {})
        new_names = [p["name"] for p in r.get("new_generations", [])]
        print(
            f"[OK]   {tid[:12]}... "
            f"FABLES {before.get('fables_faithfulness')} -> {after.get('fables_faithfulness')} "
            f"({before.get('fables_claims_total')} -> {after.get('fables_claims_total')} claims) "
            f"new={new_names}"
        )
    print("=" * 60)


async def async_main(args: argparse.Namespace) -> None:
    _run_backup(args.skip_backup)

    eval_data = ROOT / "Eval_Data"
    obs_dir = Path(args.observations_dir) if args.observations_dir else eval_data / "Observations"
    jsonl_paths = (
        [Path(p) for p in args.obs_jsonl] if args.obs_jsonl else _glob_observation_files(obs_dir)
    )

    snapshot_dir = ROOT / "output" / "incremental_runs"

    trace_ids: List[str] = []
    by_trace: Dict[str, List[Dict[str, Any]]] = {}
    exclude_lower = {t.lower() for t in (args.exclude_trace_id or [])}

    lf_sdk = None
    if args.fetch_live or args.auto_discover:
        # SDK is only required for fetch-live or to validate connectivity in pilot mode.
        if args.fetch_live:
            lf_sdk = _build_langfuse_sdk()

    if args.trace_id:
        trace_ids = [t for t in args.trace_id if t.lower() not in exclude_lower]
        if args.fetch_live and lf_sdk is not None:
            for tid in trace_ids:
                by_trace[tid] = _fetch_observations_live(lf_sdk, tid, args.obs_limit)
        else:
            for tid in trace_ids:
                by_trace[tid] = _load_observations_for_trace(jsonl_paths, tid)
    elif args.auto_discover:
        grouped = _group_observations_by_trace(jsonl_paths)
        trace_ids = [t for t in _discover_traces_with_pending_claims(grouped) if t.lower() not in exclude_lower]
        if args.limit:
            trace_ids = trace_ids[: args.limit]
        if args.fetch_live and lf_sdk is not None:
            for tid in trace_ids:
                by_trace[tid] = _fetch_observations_live(lf_sdk, tid, args.obs_limit)
        else:
            for tid in trace_ids:
                by_trace[tid] = grouped.get(tid, [])
    else:
        raise SystemExit("Either --trace-id or --auto-discover is required.")

    if not trace_ids:
        logger.info("No traces to process.")
        return

    logger.info(f"processing {len(trace_ids)} trace(s) (dry_run={args.dry_run})")

    results: List[Dict[str, Any]] = []
    for tid in trace_ids:
        try:
            result = await process_trace(
                tid,
                by_trace.get(tid, []),
                dry_run=args.dry_run,
                snapshot_dir=snapshot_dir,
                write_snapshot=not args.no_snapshot,
                repair_consistency=bool(args.repair_consistency),
                dedupe_scores=not args.no_dedupe_scores,
                reorder_spans_only=bool(args.reorder_spans_only),
            )
        except Exception as e:
            logger.exception(f"unhandled exception for {tid}")
            result = {"trace_id": tid, "ok": False, "error": f"exception: {e}"}
        results.append(result)
        print(json.dumps(result, default=str, ensure_ascii=False)[:800])

    if args.write_summary:
        out_path = Path(args.write_summary)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(results, indent=2, default=str, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"summary written to {out_path}")

    _print_summary(results)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--trace-id",
        nargs="*",
        default=None,
        help="One or more trace ids to process (pilot mode).",
    )
    p.add_argument(
        "--auto-discover",
        action="store_true",
        help="Scan local Observations JSONL and pick all traces whose extracted claims > existing verdicts.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max traces to process when using --auto-discover (0 = all).",
    )
    p.add_argument(
        "--exclude-trace-id",
        nargs="*",
        default=None,
        help="Trace ids to exclude (applies to both --trace-id and --auto-discover).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan only - print what would be created/patched, no API writes.",
    )
    p.add_argument(
        "--skip-backup",
        action="store_true",
        help="Do not run scripts/backup_eval_data.py at start.",
    )
    p.add_argument(
        "--fetch-live",
        action="store_true",
        help="Fetch observations directly from Langfuse so observation ids match the server.",
    )
    p.add_argument(
        "--observations-dir",
        type=str,
        default=None,
        help="Folder with *.jsonl exports (default Eval_Data/Observations).",
    )
    p.add_argument(
        "--obs-jsonl",
        nargs="*",
        default=None,
        help="Explicit JSONL files (overrides --observations-dir).",
    )
    p.add_argument(
        "--obs-limit",
        type=int,
        default=100,
        help="Page size for --fetch-live (default 100).",
    )
    p.add_argument(
        "--write-summary",
        type=str,
        default=None,
        help="Optional path to write a JSON summary of all results.",
    )
    p.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Do not write output/incremental_runs snapshot files (still updates Langfuse).",
    )
    p.add_argument(
        "--repair-consistency",
        action="store_true",
        help="Even if all claims are already verified, patch spans + rewrite scores for consistency.",
    )
    p.add_argument(
        "--no-dedupe-scores",
        action="store_true",
        help="Do not delete existing scores before writing new ones (may create duplicates).",
    )
    p.add_argument(
        "--reorder-spans-only",
        action="store_true",
        help="Only reorder nested keys in critic_agent.ragas_scores and ragas_evaluation.scores; no claim verification, no score writes.",
    )
    args = p.parse_args()

    if args.trace_id and args.auto_discover:
        raise SystemExit("--trace-id and --auto-discover are mutually exclusive.")

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
