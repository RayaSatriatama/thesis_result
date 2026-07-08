#!/usr/bin/env python3
"""
Re-import Langfuse traces + observations from local JSONL exports via POST /api/public/ingestion.

Reads the same layout as ``backup_eval_data.py`` output: ``Traces/*.jsonl`` and ``Observations/*.jsonl``.
For each trace: ``trace-create`` first, then ``span-create`` / ``generation-create`` in parent-before-child
order so ``parentObservationId`` resolves, then ``score-create`` events rebuilt from **flattened score
columns** on the trace export row (Langfuse CSV/JSONL exports often wrap values as single-element lists).
Default scores are **trace-level** (root trace badges / table). ``--score-source auto``: **API** for SDK-style metrics, **EVAL** only for ``Faithfulness``.
Optional ``--traces-csv`` (Langfuse traces export) adds all ``id`` values to the trace filter (case-insensitive union with repeatable ``--trace-id``).

**English:** Restore deleted traces from backup exports using the public ingestion API (optional scores).

Requires: ``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY``, ``LANGFUSE_HOST`` (see ``ObservabilityConfig``),
``.env`` loaded like other scripts.

Caveat: if a trace or observation id already exists in the project, Langfuse may reject or merge
unexpectedly — **delete the trace in Langfuse first** if you need a clean re-import with the same ids.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import uuid
from datetime import datetime, timezone
from collections import deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from settings import ObservabilityConfig  # noqa: E402

def load_trace_ids_from_csv(path: Path) -> set[str]:
    """Load trace ids from a Langfuse traces export CSV (expects an 'id' column)."""
    import csv

    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not isinstance(row, dict):
                continue
            tid = (row.get("id") or "").strip()
            if tid:
                ids.add(tid)
    return ids

# Observation types in UI exports → ingestion event types (same body shape as span / generation).
_TYPE_TO_EVENT = {
    "GENERATION": "generation-create",
    "SPAN": "span-create",
    "AGENT": "agent-create",
    "TOOL": "tool-create",
    "CHAIN": "chain-create",
    "RETRIEVER": "retriever-create",
    "EVALUATOR": "evaluator-create",
    "EMBEDDING": "embedding-create",
    "GUARDRAIL": "guardrail-create",
}


def _read_jsonl(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in paths:
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    return rows


def _glob_jsonl(dir_path: Path) -> List[Path]:
    if not dir_path.is_dir():
        return []
    return sorted(dir_path.glob("*.jsonl"))


def _topo_observations(observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {str(o["id"]): o for o in observations}
    ids = set(by_id.keys())
    children: Dict[str, List[str]] = {i: [] for i in ids}
    indeg = {i: 0 for i in ids}
    for o in observations:
        oid = str(o["id"])
        pid = o.get("parentObservationId")
        if pid is not None:
            pid = str(pid)
        if pid and pid in ids:
            children[pid].append(oid)
            indeg[oid] += 1
    q = deque([i for i in ids if indeg[i] == 0])
    ordered: List[str] = []
    while q:
        cur = q.popleft()
        ordered.append(cur)
        for c in children.get(cur, []):
            indeg[c] -= 1
            if indeg[c] == 0:
                q.append(c)
    if len(ordered) != len(ids):
        remainder = [i for i in ids if i not in ordered]
        ordered.extend(remainder)
    return [by_id[i] for i in ordered]


def _env_name(raw: Any) -> str:
    s = (str(raw) if raw is not None else "default").strip().lower()
    return s or "default"


# Trace JSONL row keys that are not flattened scores (avoid treating metadata as scores).
_TRACE_ROW_RESERVED_KEYS = frozenset(
    {
        "id",
        "timestamp",
        "name",
        "userId",
        "sessionId",
        "release",
        "version",
        "environment",
        "tags",
        "bookmarked",
        "public",
        "input",
        "output",
        "metadata",
        "comments",
        "externalId",
        "projectId",
    }
)

_TRACE_SCORE_EXTRA_KEYS = frozenset(
    {
        "Faithfulness",
        "coherence_score",
        "educational_score",
        "overall_score",
        "fables_faithfulness",
        "ragas_faithfulness",
        "ragas_standard_faithfulness",
        "revision_count",
    }
)


def _unwrap_score_cell(value: Any) -> Any:
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _score_cell_to_typed(value: Any) -> Optional[Tuple[str, Any]]:
    """Return (dataType, api_value) for Langfuse score-create, or None to skip."""
    v = _unwrap_score_cell(value)
    if v is None or v == "" or v == []:
        return None
    if isinstance(v, bool):
        return ("BOOLEAN", 1 if v else 0)
    if isinstance(v, int) and not isinstance(v, bool):
        return ("NUMERIC", float(v))
    if isinstance(v, float):
        return ("NUMERIC", v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            f = float(s)
            if f.is_integer():
                return ("NUMERIC", float(int(f)))
            return ("NUMERIC", f)
        except ValueError:
            return ("CATEGORICAL", s)
    return None


def _trace_row_is_score_column(key: str) -> bool:
    if key in _TRACE_ROW_RESERVED_KEYS:
        return False
    kl = key.lower()
    if kl.endswith("_normalized"):
        return False
    if key in _TRACE_SCORE_EXTRA_KEYS:
        return True
    if kl.startswith("ragas_") or kl.startswith("geval_"):
        return True
    if kl.endswith("_score"):
        return True
    return False


def _last_observation_id_by_name(observations: List[Dict[str, Any]]) -> Dict[str, str]:
    """Last occurrence wins (topo order: parents before children)."""
    out: Dict[str, str] = {}
    for o in _topo_observations(observations):
        n = o.get("name")
        if n:
            out[str(n)] = str(o["id"])
    return out


def _resolve_score_observation_id(
    column_name: str,
    obs_by_name: Dict[str, str],
    *,
    link_observation: bool,
) -> Optional[str]:
    """Only used with ``--link-score-observations`` (optional). Default is trace-level only."""
    if not link_observation or not obs_by_name:
        return None
    return obs_by_name.get(str(column_name))


# Langfuse list columns use ``{name}-{SOURCE}-{dataType}``. In this project the Python SDK
# logs most metrics as **API**; only the thesis column ``Faithfulness`` is **EVAL**.
def _infer_score_source(column_name: str) -> str:
    cn = str(column_name).lower()
    if cn == "faithfulness" or cn.startswith("fables_") or cn.startswith("ragas_") or cn.startswith("geval_"):
        return "EVAL"
    return "API"


def _resolve_score_source(column_name: str, mode: str) -> str:
    if mode == "API" or mode == "EVAL":
        return mode
    return _infer_score_source(column_name)


def _build_score_events(
    trace_row: Dict[str, Any],
    observations: List[Dict[str, Any]],
    trace_id: str,
    *,
    link_observation: bool,
    score_source_mode: str = "auto",
) -> List[Dict[str, Any]]:
    env = _env_name(trace_row.get("environment"))
    # Gunakan timestamp dari trace agar skor sinkron dengan waktu trace di Langfuse
    # Jika menggunakan datetime.now(), skor bisa tidak muncul karena filter tanggal UI Langfuse
    ts = str(trace_row["timestamp"])
    obs_by_name = _last_observation_id_by_name(observations) if link_observation else {}
    events: List[Dict[str, Any]] = []

    def _append_score_event(
        column_name: str, dtype: str, val: Any, src: str
    ) -> None:
        body: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "name": str(column_name),
            "traceId": str(trace_id),
            "environment": env,
            "source": src,
        }
        if dtype == "NUMERIC":
            body["dataType"] = "NUMERIC"
            body["value"] = float(val)
        elif dtype == "BOOLEAN":
            body["dataType"] = "BOOLEAN"
            body["value"] = int(val)
        else:
            body["dataType"] = "CATEGORICAL"
            body["stringValue"] = str(val)
        oid = _resolve_score_observation_id(
            column_name, obs_by_name, link_observation=link_observation
        )
        if oid:
            body["observationId"] = oid
        events.append(_wrap_ingestion_event("score-create", body, ts))

    for key, raw in trace_row.items():
        if not _trace_row_is_score_column(key):
            continue
        typed = _score_cell_to_typed(raw)
        if not typed:
            continue
        dtype, val = typed
        sk = str(key)
        _append_score_event(sk, dtype, val, _resolve_score_source(sk, score_source_mode))

    for obs in observations:
        nm = str(obs.get("name") or "")
        if nm == "geval_coherence":
            out = obs.get("output", {})
            if isinstance(out, str):
                try:
                    import json
                    out = json.loads(out)
                except Exception:
                    out = {}
            if isinstance(out, dict) and "geval_coherence" in out:
                try:
                    raw_score = float(out["geval_coherence"])
                    src = "EVAL" if score_source_mode == "auto" else score_source_mode
                    _append_score_event("geval_coherence", "NUMERIC", raw_score, src)
                except (ValueError, TypeError):
                    pass

    return events


def _trace_event_body(row: Dict[str, Any]) -> Dict[str, Any]:
    tid = row.get("id")
    ts = row.get("timestamp")
    if not tid or not ts:
        raise ValueError("trace row missing id or timestamp")
    body: Dict[str, Any] = {
        "id": str(tid),
        "timestamp": ts,
        "name": row.get("name"),
        "input": row.get("input"),
        "output": row.get("output"),
        "environment": _env_name(row.get("environment")),
    }
    if row.get("userId") is not None:
        body["userId"] = row["userId"]
    if row.get("sessionId") is not None:
        body["sessionId"] = row["sessionId"]
    if row.get("release") is not None:
        body["release"] = row["release"]
    if row.get("version") is not None:
        body["version"] = row["version"]
    if row.get("public") is not None:
        body["public"] = row["public"]
    import json
    trace_tags = []
    
    # 1. Determine Type Tag
    trace_name = str(row.get("name", ""))
    if "Baseline" in trace_name:
        trace_tags.append("Baseline")
    else:
        trace_tags.append("Agentic-AI-LightRAG")
        
    # 2. Determine Language Tag
    existing_tags_raw = row.get("tags")
    existing_tags = []
    if isinstance(existing_tags_raw, str):
        try:
            existing_tags = json.loads(existing_tags_raw)
        except Exception:
            pass
    elif isinstance(existing_tags_raw, list):
        existing_tags = existing_tags_raw
        
    existing_tags_lower = [str(t).lower() for t in existing_tags]
    if "en" in existing_tags_lower:
        trace_tags.append("EN")
    elif "id" in existing_tags_lower:
        trace_tags.append("ID")
    else:
        # Fallback to checking the input text prompt
        input_text = str(row.get("input", "")).lower()
        if "buat cerita" in input_text or "cerita edukatif" in input_text:
            trace_tags.append("ID")
        else:
            trace_tags.append("EN")
            
    body["tags"] = trace_tags
    md = row.get("metadata")
    if isinstance(md, dict) and md:
        body["metadata"] = md
    return {k: v for k, v in body.items() if v is not None}


def _usage_from_obs(obs: Dict[str, Any]) -> Optional[Dict[str, int]]:
    usage: Dict[str, int] = {}
    ud = obs.get("usageDetails")
    if isinstance(ud, dict):
        for key in ("input", "output", "total"):
            v = ud.get(key)
            if isinstance(v, int) and v >= 0:
                usage[key] = v
    if not usage:
        mapping = [("input", "inputUsage"), ("output", "outputUsage"), ("total", "totalUsage")]
        for out_k, src_k in mapping:
            v = obs.get(src_k)
            if isinstance(v, int) and v >= 0:
                usage[out_k] = v
    return usage if usage else None


def _usage_details_sanitized(obs: Dict[str, Any]) -> Optional[Dict[str, int]]:
    ud = obs.get("usageDetails")
    if not isinstance(ud, dict):
        return None
    out: Dict[str, int] = {}
    for k, v in ud.items():
        if isinstance(v, int) and v >= 0:
            out[str(k)] = v
    return out if out else None


def _cost_details_sanitized(obs: Dict[str, Any]) -> Optional[Dict[str, float]]:
    cd = obs.get("costDetails")
    if not isinstance(cd, dict):
        return None
    out: Dict[str, float] = {}
    for k, v in cd.items():
        if isinstance(v, (int, float)) and v == v and v >= 0:
            out[str(k)] = float(v)
    return out if out else None


def _observation_body_base(obs: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "id": str(obs["id"]),
        "traceId": str(trace_id),
        "environment": _env_name(obs.get("environment")),
        "name": obs.get("name"),
        "startTime": obs["startTime"],
        "endTime": obs["endTime"],
    }
    pid = obs.get("parentObservationId")
    if pid is not None and str(pid).strip():
        body["parentObservationId"] = str(pid)
    for key in ("input", "output", "level", "statusMessage", "version"):
        v = obs.get(key)
        if v is not None:
            body[key] = v
    md = obs.get("metadata")
    if isinstance(md, dict) and md:
        body["metadata"] = md
    return {k: v for k, v in body.items() if v is not None}


def _observation_event(obs: Dict[str, Any], trace_id: str) -> Tuple[str, Dict[str, Any], str]:
    """Returns (event_type, body, timestamp_for_envelope)."""
    otype = str(obs.get("type") or "SPAN").strip().upper()
    event_type = _TYPE_TO_EVENT.get(otype, "span-create")
    base = _observation_body_base(obs, trace_id)
    ts = str(obs.get("startTime") or obs.get("endTime"))

    if event_type != "span-create":
        # Non-span types use the same extended body as generation-create in Langfuse ingestion.
        st = obs["startTime"]
        cst = obs.get("completionStartTime") or st
        base["completionStartTime"] = cst
        if obs.get("model"):
            base["model"] = obs["model"]
        mp = obs.get("modelParameters")
        if isinstance(mp, dict) and mp:
            base["modelParameters"] = mp
        u = _usage_from_obs(obs)
        if u:
            base["usage"] = u
        ud = _usage_details_sanitized(obs)
        if ud:
            base["usageDetails"] = ud
        cd = _cost_details_sanitized(obs)
        if cd:
            base["costDetails"] = cd
        pn, pv = obs.get("promptName"), obs.get("promptVersion")
        if pn and isinstance(pv, int):
            base["promptName"] = pn
            base["promptVersion"] = pv

    return event_type, base, ts


def _wrap_ingestion_event(event_type: str, body: Dict[str, Any], ts: str) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "timestamp": ts,
        "type": event_type,
        "body": body,
    }


def _batch_json_size(batch: List[Dict[str, Any]]) -> int:
    return len(json.dumps({"batch": batch}, default=str).encode("utf-8"))


def _iter_batches(events: List[Dict[str, Any]], max_bytes: int) -> Iterable[List[Dict[str, Any]]]:
    batch: List[Dict[str, Any]] = []
    for ev in events:
        trial = batch + [ev]
        if batch and _batch_json_size(trial) > max_bytes:
            yield batch
            batch = [ev]
        else:
            batch = trial
    if batch:
        yield batch


def _ingestion_post(host: str, pk: str, sk: str, body: Dict[str, Any]) -> Optional[str]:
    try:
        auth = base64.b64encode(f"{pk}:{sk}".encode()).decode("ascii")
        req = Request(
            f"{host}/api/public/ingestion",
            data=json.dumps(body, default=str).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth}",
            },
            method="POST",
        )
        with urlopen(req, timeout=120.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        out = json.loads(raw) if raw else {}
        errs = out.get("errors") or []
        if errs:
            return f"ingestion errors: {errs[:5]}"
        return None
    except HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:800]
        except Exception:
            detail = str(e)
        return f"HTTP {e.code}: {detail}"
    except URLError as e:
        return f"URL error: {e}"
    except Exception as e:
        return str(e)


def _build_trace_events(trace_row: Dict[str, Any]) -> List[Dict[str, Any]]:
    tid = str(trace_row["id"])
    ts = str(trace_row["timestamp"])
    body = _trace_event_body(trace_row)
    return [_wrap_ingestion_event("trace-create", body, ts)]


def _build_observation_events(
    observations: List[Dict[str, Any]], trace_id: str
) -> List[Dict[str, Any]]:
    ordered = _topo_observations(observations)
    out: List[Dict[str, Any]] = []
    for obs in ordered:
        if str(obs.get("traceId") or "") != str(trace_id):
            continue
        etype, obody, ts = _observation_event(obs, trace_id)
        out.append(_wrap_ingestion_event(etype, obody, ts))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backup-root",
        type=str,
        default=None,
        help="Folder that contains Traces/ and Observations/ (e.g. Eval_Data/backups/pre-faithfulness-replay_...)",
    )
    parser.add_argument(
        "--traces-dir",
        type=str,
        default=None,
        help="Directory of trace JSONL files (default: Eval_Data/Agentic-AI-LightRAG/Traces or backup-root/Traces)",
    )
    parser.add_argument(
        "--observations-dir",
        type=str,
        default=None,
        help="Directory of observation JSONL files (default: Eval_Data/Agentic-AI-LightRAG/Observations or backup-root/Observations)",
    )
    parser.add_argument(
        "--trace-id",
        action="append",
        default=[],
        metavar="ID",
        help="Only import these trace ids (repeatable). Default: all traces found in trace JSONL.",
    )
    parser.add_argument(
        "--traces-csv",
        type=str,
        default=None,
        help="Langfuse traces export CSV: add all ``id`` values to the filter (case-insensitive). "
        "Combined with --trace-id as union of both sets.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts and batch sizes; do not POST.",
    )
    parser.add_argument(
        "--max-batch-mb",
        type=float,
        default=3.5,
        help="Max approximate JSON body size per ingestion request (default: 3.5).",
    )
    parser.add_argument(
        "--no-scores",
        action="store_true",
        help="Do not emit score-create from flattened columns on trace JSONL rows.",
    )
    parser.add_argument(
        "--link-score-observations",
        action="store_true",
        help="Set observationId when a score column name matches an observation name. "
        "Default is **off**: scores are trace-level only (matches root trace badges / table like StoryGenerationWorkflow).",
    )
    parser.add_argument(
        "--score-source",
        choices=("auto", "API", "EVAL"),
        default="auto",
        help="Score ``source`` for Langfuse columns: ``auto`` maps RAGAS/GEval names to EVAL and "
        "the rest to API (matches headers like ``(eval)`` vs ``(api)``).",
    )
    parser.add_argument(
        "--scores-only",
        action="store_true",
        help="Only POST score-create events (trace must already exist in Langfuse). "
        "Use after a prior import omitted scores or used the wrong source.",
    )
    parser.add_argument(
        "--strict-scores",
        action="store_true",
        help="Exit non-zero if any score batch fails (default: warn and continue after trace+observation import).",
    )
    args = parser.parse_args()

    eval_data = ROOT / "Eval_Data"
    if args.backup_root:
        br = Path(args.backup_root).resolve()
        traces_dir = Path(args.traces_dir).resolve() if args.traces_dir else br / "Traces"
        obs_dir = Path(args.observations_dir).resolve() if args.observations_dir else br / "Observations"
    else:
        traces_dir = Path(args.traces_dir).resolve() if args.traces_dir else eval_data / "Agentic-AI-LightRAG" / "Traces"
        obs_dir = Path(args.observations_dir).resolve() if args.observations_dir else eval_data / "Agentic-AI-LightRAG" / "Observations"

    trace_paths = _glob_jsonl(traces_dir)
    obs_paths = _glob_jsonl(obs_dir)
    if not trace_paths:
        raise SystemExit(f"No *.jsonl under traces dir: {traces_dir}")
    if not obs_paths:
        raise SystemExit(f"No *.jsonl under observations dir: {obs_dir}")

    traces = _read_jsonl(trace_paths)
    all_obs = _read_jsonl(obs_paths)

    filter_ids = {t.lower() for t in (args.trace_id or [])}
    if args.traces_csv:
        filter_ids |= {i.lower() for i in load_trace_ids_from_csv(Path(args.traces_csv))}
    if filter_ids:
        traces = [t for t in traces if str(t.get("id", "")).lower() in filter_ids]
    trace_by_id = {str(t["id"]): t for t in traces if t.get("id")}

    if filter_ids:
        missing = filter_ids - {k.lower() for k in trace_by_id}
        if missing:
            print(
                "warning: --trace-id not found in trace JSONL (no row to import): "
                + ", ".join(sorted(missing)),
                file=sys.stderr,
            )
        if not trace_by_id:
            raise SystemExit("No matching traces in JSONL exports; check --trace-id and traces dir.")

    obs_by_trace: Dict[str, List[Dict[str, Any]]] = {}
    for o in all_obs:
        tid = o.get("traceId")
        if not tid:
            continue
        tid = str(tid)
        if filter_ids and tid.lower() not in filter_ids:
            continue
        obs_by_trace.setdefault(tid, []).append(o)

    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
    host = (ObservabilityConfig.LANGFUSE_HOST or "").strip().rstrip("/")
    if not args.dry_run and (not host or not pk or not sk):
        raise SystemExit("LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST required (or use --dry-run).")

    max_bytes = max(1024 * 1024, int(float(args.max_batch_mb) * 1024 * 1024))

    total_events = 0
    total_batches = 0
    link_scores = bool(args.link_score_observations)
    score_mode = args.score_source
    scores_only = bool(args.scores_only)

    for tid, trow in sorted(trace_by_id.items(), key=lambda x: x[0]):
        obs_list = obs_by_trace.get(tid, [])
        score_ev: List[Dict[str, Any]] = []
        if not args.no_scores:
            score_ev = _build_score_events(
                trow,
                obs_list,
                tid,
                link_observation=link_scores,
                score_source_mode=score_mode,
            )

        if scores_only:
            core_events = []
        else:
            core_events = _build_trace_events(trow) + _build_observation_events(obs_list, tid)

        total_events += len(core_events)
        if not args.no_scores:
            total_events += len(score_ev)

        if args.dry_run:
            if scores_only:
                print(f"trace {tid}: scores-only, {len(score_ev)} score events (source mode={score_mode})")
            else:
                print(
                    f"trace {tid}: {len(obs_list)} observations, {len(score_ev)} scores -> "
                    f"{len(core_events) + len(score_ev)} ingestion events (source mode={score_mode})"
                )
            for b in _iter_batches(core_events if not scores_only else score_ev, max_bytes):
                total_batches += 1
                label = "score" if scores_only else "core"
                print(f"  {label} batch ~{_batch_json_size(b)} bytes, {len(b)} events")
            if not scores_only and score_ev and not args.no_scores:
                for b in _iter_batches(score_ev, max_bytes):
                    total_batches += 1
                    print(f"  score batch ~{_batch_json_size(b)} bytes, {len(b)} events")
            continue

        for batch in _iter_batches(core_events, max_bytes):
            if not batch:
                continue
            total_batches += 1
            err = _ingestion_post(host, pk, sk, {"batch": batch})
            if err:
                raise SystemExit(f"Failed trace {tid} core batch {total_batches}: {err}")

        if not scores_only and not args.no_scores and score_ev:
            for batch in _iter_batches(score_ev, max_bytes):
                total_batches += 1
                err = _ingestion_post(host, pk, sk, {"batch": batch})
                if err:
                    msg = f"[WARN] trace {tid[:12]}… score batch: {err}"
                    print(msg, file=sys.stderr)
                    if args.strict_scores:
                        raise SystemExit(msg)
        elif scores_only and not args.no_scores:
            for batch in _iter_batches(score_ev, max_bytes):
                total_batches += 1
                err = _ingestion_post(host, pk, sk, {"batch": batch})
                if err:
                    msg = f"Failed trace {tid} scores batch: {err}"
                    if args.strict_scores:
                        raise SystemExit(msg)
                    print(f"[WARN] {msg}", file=sys.stderr)

        if scores_only:
            print(f"ok scores trace {tid} ({len(score_ev)} scores)")
        else:
            print(f"ok trace {tid} ({len(obs_list)} observations)")

    if args.dry_run:
        print(f"dry-run: {len(trace_by_id)} traces, {total_events} events, {total_batches} batches (max {max_bytes} B)")
    else:
        print(f"done: {len(trace_by_id)} traces, {total_events} events, {total_batches} batches")


if __name__ == "__main__":
    main()
