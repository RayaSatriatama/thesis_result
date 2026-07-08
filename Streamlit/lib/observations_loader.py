"""
Observations loader — extracts raw G-Eval sub-dimension scores from Langfuse
observations CSV exports.

Langfuse observation rows have one row per LLM call. G-Eval runs 5 parallel
sub-criteria (geval_fluency, geval_consistency, geval_clarity, geval_conciseness,
geval_repetitiveness), each stored as a separate observation with its output
JSON containing {"score": int, "normalized": float, "reason": str}.

This module parses those rows, pivots them per traceId, and returns a DataFrame
with per-dimension scores and an averaged aggregate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from lib.paths import repo_root

GEVAL_DIMENSIONS = [
    "geval_fluency",
    "geval_consistency",
    "geval_clarity",
    "geval_conciseness",
    "geval_repetitiveness",
]


def _find_observations_csv(directory: Path) -> Optional[Path]:
    matches = sorted(directory.glob("*lf-observations-export*.csv"))
    return matches[0] if matches else None


def _find_latest_observations_jsonl(directory: Path) -> Optional[Path]:
    matches = list(directory.glob("*lf-observations-export*.jsonl"))
    if not matches:
        matches = list(directory.glob("*.jsonl"))
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def _parse_output_score(raw: str) -> Optional[dict]:
    try:
        return json.loads(raw)
    except Exception:
        return None


def load_geval_per_trace_from_df(obs: pd.DataFrame) -> pd.DataFrame:
    """Parse G-Eval sub-dimension raw scores from an observations DataFrame.

    Returns a DataFrame with columns:
        traceId,
        geval_fluency / consistency / clarity / conciseness / repetitiveness (1-5),
        geval_avg_raw, geval_avg_norm, geval_norm_recalc.
    """
    name_clean = obs["name"].astype(str).str.strip('"').str.strip("'")
    geval_rows = obs[name_clean.isin(GEVAL_DIMENSIONS)].copy()
    geval_rows["name_clean"] = name_clean[geval_rows.index]
    geval_rows["traceId_clean"] = (
        geval_rows["traceId"].astype(str).str.strip('"').str.strip("'")
    )

    records = []
    for _, row in geval_rows.iterrows():
        parsed = _parse_output_score(str(row["output"]))
        if parsed is None:
            continue
        score = parsed.get("score")
        if score is None:
            continue
        records.append({
            "traceId": row["traceId_clean"],
            "dimension": row["name_clean"],
            "score": float(score),
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    pivot = (
        df.pivot_table(index="traceId", columns="dimension", values="score", aggfunc="first")
        .reset_index()
    )
    pivot.columns.name = None

    dims_present = [d for d in GEVAL_DIMENSIONS if d in pivot.columns]
    pivot["geval_avg_raw"] = pivot[dims_present].mean(axis=1).round(4)
    pivot["geval_avg_norm"] = ((pivot["geval_avg_raw"] - 1) / 4).round(4)

    raw = pivot["geval_avg_raw"]
    rmin, rmax = raw.min(), raw.max()
    if rmax > rmin:
        pivot["geval_norm_recalc"] = ((raw - rmin) / (rmax - rmin)).round(4)
    else:
        pivot["geval_norm_recalc"] = 0.0

    return pivot


def load_geval_per_trace(obs_csv: Path) -> pd.DataFrame:
    """Parse G-Eval sub-dimension raw scores from an observations CSV path."""
    obs = pd.read_csv(obs_csv, encoding="utf-8")
    return load_geval_per_trace_from_df(obs)


def load_baseline_geval() -> Optional[pd.DataFrame]:
    """Load G-Eval per-trace scores from Eval_Data/Baselines/Observations/."""
    obs_dir = repo_root() / "Eval_Data" / "Baselines" / "Observations"
    csv_path = _find_observations_csv(obs_dir)
    if csv_path is None:
        return None
    obs = pd.read_csv(csv_path, encoding="utf-8")
    return load_geval_per_trace_from_df(obs)


def load_current_geval() -> Optional[pd.DataFrame]:
    """Load G-Eval per-trace scores from Eval_Data/Observations/."""
    obs_dir = repo_root() / "Eval_Data" / "Agentic-AI-LightRAG" / "Observations"
    csv_path = _find_observations_csv(obs_dir)
    if csv_path is None:
        return None
    obs = pd.read_csv(csv_path, encoding="utf-8")
    return load_geval_per_trace_from_df(obs)


def load_fables_claim_counts_from_jsonl(jsonl_path: Path) -> pd.DataFrame:
    """
    Load per-trace claim counts from Langfuse observations JSONL export.

    Source of truth: span `fables_faithfulness` output fields:
      - fables_claims_total
      - fables_claims_faithful
      - fables_claims_unfaithful
      - fables_claims_cant_verify
      - fables_claims_partial_support

    `ragas_standard_faithfulness` uses total claims (strict, all included), while the
    2x2 FABLES matrix uses evaluated claims only (faithful + unfaithful).
    """
    rows: dict[str, dict] = {}
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            s = (line or "").strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if str(obj.get("name") or "") != "fables_faithfulness":
                continue
            trace_id = str(obj.get("traceId") or "").strip()
            if not trace_id:
                continue
            out = obj.get("output") or {}
            if not isinstance(out, dict):
                continue
            tot = out.get("fables_claims_total")
            if tot is None:
                continue
            try:
                tot_i = int(tot)
            except Exception:
                continue

            def _as_int(x: object) -> int:
                try:
                    return int(x)
                except Exception:
                    return 0

            faithful = _as_int(out.get("fables_claims_faithful"))
            unfaithful = _as_int(out.get("fables_claims_unfaithful"))
            cant_verify = _as_int(out.get("fables_claims_cant_verify"))
            partial_support = _as_int(out.get("fables_claims_partial_support"))
            evaluated = faithful + unfaithful

            rows[trace_id] = {
                "traceId": trace_id,
                "fables_claims_total": tot_i,
                "fables_claims_evaluated": evaluated,
                "fables_claims_faithful": faithful,
                "fables_claims_unfaithful": unfaithful,
                "fables_claims_cant_verify": cant_verify,
                "fables_claims_partial_support": partial_support,
            }

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(list(rows.values()))


def load_baseline_claim_counts() -> Optional[pd.DataFrame]:
    obs_dir = repo_root() / "Eval_Data" / "Baselines" / "Observations"
    p = _find_latest_observations_jsonl(obs_dir)
    if p is None:
        return None
    df = load_fables_claim_counts_from_jsonl(p)
    return df if not df.empty else None


def load_current_claim_counts() -> Optional[pd.DataFrame]:
    obs_dir = repo_root() / "Eval_Data" / "Agentic-AI-LightRAG" / "Observations"
    p = _find_latest_observations_jsonl(obs_dir)
    if p is None:
        return None
    df = load_fables_claim_counts_from_jsonl(p)
    return df if not df.empty else None
