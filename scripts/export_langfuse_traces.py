"""
Export Langfuse traces (and optionally observations) via the public API / Python SDK.

Uses the same credentials as the app: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY,
LANGFUSE_HOST (see src/settings.py ObservabilityConfig).

Examples:
  uv run python scripts/export_langfuse_traces.py --limit 50
  uv run python scripts/export_langfuse_traces.py --trace-id <id> --with-observations
  uv run python scripts/export_langfuse_traces.py --user-id u1 --from-time 2025-03-01T00:00:00Z \\
      --format jsonl -o output/langfuse_export/run.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path setup (match other scripts) ─────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from settings import ObservabilityConfig  # noqa: E402


def _parse_iso_datetime(value: str) -> datetime:
    s = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    # Langfuse OpenAPI client uses pydantic v1 models with .json()
    if hasattr(obj, "json") and callable(obj.json) and hasattr(obj, "dict"):
        return json.loads(obj.json())
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    return obj


def _build_client():
    from langfuse import Langfuse

    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
    host = (ObservabilityConfig.LANGFUSE_HOST or "").strip()
    if not pk or not sk:
        raise SystemExit(
            "Missing LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY in environment (.env)."
        )
    if not host:
        raise SystemExit("Missing LANGFUSE_HOST in environment (.env).")
    return Langfuse(public_key=pk, secret_key=sk, host=host.rstrip("/"))


def _fetch_observations_for_trace(client, trace_id: str, obs_limit: int) -> List[Dict[str, Any]]:
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


def _export_single_trace(
    client,
    trace_id: str,
    with_observations: bool,
    obs_limit: int,
) -> Dict[str, Any]:
    detail = client.api.trace.get(trace_id)
    out: Dict[str, Any] = {
        "trace_id": trace_id,
        "trace": _to_jsonable(detail),
    }
    if with_observations:
        out["observations"] = _fetch_observations_for_trace(
            client, trace_id, obs_limit
        )
    return out


def _list_all_traces(
    client,
    *,
    limit: int,
    user_id: Optional[str],
    session_id: Optional[str],
    name: Optional[str],
    tags: Optional[List[str]],
    from_ts: Optional[datetime],
    to_ts: Optional[datetime],
    max_traces: Optional[int],
    max_pages: int,
) -> List[Dict[str, Any]]:
    page = 1
    collected: List[Dict[str, Any]] = []
    while page <= max_pages:
        resp = client.api.trace.list(
            limit=limit,
            page=page,
            user_id=user_id,
            session_id=session_id,
            name=name,
            tags=tags,
            from_timestamp=from_ts,
            to_timestamp=to_ts,
        )
        data = getattr(resp, "data", None) or []
        for t in data:
            collected.append(_to_jsonable(t))
            if max_traces is not None and len(collected) >= max_traces:
                return collected
        meta = resp.meta
        if page >= meta.total_pages or not data:
            break
        page += 1
    return collected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Langfuse traces via API (SDK v3)."
    )
    parser.add_argument(
        "--trace-id",
        help="Export one trace by ID (full detail).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file. Default: output/langfuse_export/traces_<timestamp>.{json|jsonl}",
    )
    parser.add_argument(
        "--format",
        choices=("json", "jsonl"),
        default="json",
        help="json: one array or one object; jsonl: one record per line (list mode only).",
    )
    parser.add_argument("--limit", type=int, default=100, help="Page size for list API.")
    parser.add_argument(
        "--max-traces",
        type=int,
        default=None,
        help="Stop after this many traces (list mode).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10_000,
        help="Safety cap on list pagination.",
    )
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--name", default=None, help="Filter traces by name.")
    parser.add_argument(
        "--tags",
        default=None,
        help="Comma-separated tags filter.",
    )
    parser.add_argument(
        "--from-time",
        dest="from_time",
        default=None,
        help="ISO-8601 lower bound on trace timestamp (e.g. 2025-03-01T00:00:00Z).",
    )
    parser.add_argument(
        "--to-time",
        dest="to_time",
        default=None,
        help="ISO-8601 upper bound on trace timestamp.",
    )
    parser.add_argument(
        "--with-observations",
        action="store_true",
        help="Include observations (extra API calls per trace when listing).",
    )
    parser.add_argument(
        "--obs-limit",
        type=int,
        default=500,
        help="Page size when fetching observations per trace.",
    )
    args = parser.parse_args()

    tags_list: Optional[List[str]] = None
    if args.tags:
        tags_list = [t.strip() for t in args.tags.split(",") if t.strip()]

    from_ts = _parse_iso_datetime(args.from_time) if args.from_time else None
    to_ts = _parse_iso_datetime(args.to_time) if args.to_time else None

    client = _build_client()

    out_path = args.output
    if out_path is None:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        subdir = ROOT / "output" / "langfuse_export"
        subdir.mkdir(parents=True, exist_ok=True)
        ext = "jsonl" if args.format == "jsonl" and not args.trace_id else "json"
        out_path = subdir / f"traces_{ts}.{ext}"

    if args.trace_id:
        record = _export_single_trace(
            client,
            args.trace_id,
            with_observations=args.with_observations,
            obs_limit=args.obs_limit,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        print(f"Wrote 1 trace to {out_path}")
        return

    summaries = _list_all_traces(
        client,
        limit=args.limit,
        user_id=args.user_id,
        session_id=args.session_id,
        name=args.name,
        tags=tags_list,
        from_ts=from_ts,
        to_ts=to_ts,
        max_traces=args.max_traces,
        max_pages=args.max_pages,
    )

    if args.with_observations:
        full: List[Dict[str, Any]] = []
        for row in summaries:
            tid = row.get("id")
            if not tid:
                continue
            full.append(
                _export_single_trace(
                    client,
                    tid,
                    with_observations=True,
                    obs_limit=args.obs_limit,
                )
            )
        payload: Any = full
    else:
        payload = summaries

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "jsonl":
        with open(out_path, "w", encoding="utf-8") as f:
            for item in payload:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    n = len(payload) if isinstance(payload, list) else 1
    print(f"Wrote {n} trace record(s) to {out_path}")


if __name__ == "__main__":
    main()
