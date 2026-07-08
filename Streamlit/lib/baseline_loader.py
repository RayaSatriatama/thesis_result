"""
Baseline data loader for Streamlit dashboard.

Loads Langfuse trace CSV exports from Eval_Data/Baselines and Eval_Data/Traces
for side-by-side comparison.
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Optional

import pandas as pd

from lib.paths import repo_root

METRIC_COLS = [
    "fables_faithfulness",
    "ragas_standard_faithfulness",
    "geval_avg_raw",
    "educational_score",
    "overall_score",
    "revision_count",
]

METRIC_LABELS = {
    "fables_faithfulness": "FABLES Faithfulness",
    "ragas_standard_faithfulness": "RAGAS Standard Faithfulness",
    "geval_avg_raw": "G-Eval Coherence (avg raw, 1-5)",
    "geval_avg_norm": "G-Eval Coherence (avg normalized, 0-1)",
    "geval_norm_recalc": "G-Eval Coherence (re-normalized, 0-1)",
    "geval_coherence_normalized": "G-Eval Coherence (pre-computed, 0-1)",
    "educational_score": "Educational Score",
    "overall_score": "Overall Score",
    "revision_count": "Revision Count",
}


def _find_csv(directory: Path) -> Optional[Path]:
    """Return latest CSV found under directory (by mtime)."""
    matches = list(directory.glob("*.csv"))
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def _iter_csv_paths_newest_first(directory: Path) -> list[Path]:
    paths = list(directory.glob("*.csv"))
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def _pick_csv_with_nonbaseline_rows(directory: Path) -> Optional[Path]:
    """
    Pick newest CSV that contains at least one non-baseline trace row.

    This prevents accidentally selecting a baseline-only export that was copied into
    Eval_Data/Traces/.
    """
    for p in _iter_csv_paths_newest_first(directory):
        try:
            df = pd.read_csv(p, encoding="utf-8", usecols=["name"])
        except Exception:
            continue
        if "name" not in df.columns or df.empty:
            continue
        names = df["name"].astype(str).str.strip('"').str.strip("'")
        if (names != "BaselineWikiEvalWorkflow").any():
            return p
    return None


def _pick_csv_with_baseline_rows(directory: Path) -> Optional[Path]:
    """Pick newest CSV that contains BaselineWikiEvalWorkflow rows."""
    for p in _iter_csv_paths_newest_first(directory):
        try:
            df = pd.read_csv(p, encoding="utf-8", usecols=["name"])
        except Exception:
            continue
        if "name" not in df.columns or df.empty:
            continue
        names = df["name"].astype(str).str.strip('"').str.strip("'")
        if (names == "BaselineWikiEvalWorkflow").any():
            return p
    return None


def _clean_traces_df(df: pd.DataFrame) -> pd.DataFrame:
    """Strip extra quotes and brackets from Langfuse CSV export and coerce metric columns."""
    # Langfuse exports wrap values in extra quotes -- strip them
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip('"').str.strip("'")

    # Coerce metric columns to numeric -- also handle bracket-wrapped values like '[0.7778]'
    for col in METRIC_COLS:
        if col in df.columns:
            s = df[col].astype(str).str.strip().str.lstrip('[').str.rstrip(']').str.strip()
            df[col] = pd.to_numeric(s, errors="coerce")

    return df


def load_traces_csv(path: Path) -> pd.DataFrame:
    """Load and clean a Langfuse traces CSV export."""
    df = pd.read_csv(path, encoding="utf-8")
    df = _clean_traces_df(df)
    if "id" in df.columns:
        df["id"] = df["id"].astype(str).str.strip('"').str.strip("'")
    return df


def latest_baseline_csv_path() -> Optional[Path]:
    root = repo_root()
    baseline_dir = root / "Eval_Data" / "Baselines" / "Traces"
    return _pick_csv_with_baseline_rows(baseline_dir) or _find_csv(baseline_dir)


def latest_current_csv_path() -> Optional[Path]:
    root = repo_root()
    current_dir = root / "Eval_Data" / "Traces"
    return _pick_csv_with_nonbaseline_rows(current_dir) or _find_csv(current_dir)


def load_baseline_df() -> Optional[pd.DataFrame]:
    """Load baseline traces CSV, filter to BaselineWikiEvalWorkflow, and join G-Eval scores."""
    from lib.observations_loader import load_baseline_geval, load_baseline_claim_counts
    root = repo_root()
    baseline_dir = root / "Eval_Data" / "Baselines" / "Traces"
    csv_path = _pick_csv_with_baseline_rows(baseline_dir) or _find_csv(baseline_dir)
    if csv_path is None:
        return None
    df = load_traces_csv(csv_path)
    if "name" in df.columns:
        name_clean = df["name"].astype(str).str.strip('"').str.strip("'")
        df = df[name_clean == "BaselineWikiEvalWorkflow"].reset_index(drop=True)
        if df.empty:
            return None
    
    # Deduplicate by input, keeping latest timestamp
    if "input" in df.columns and "timestamp" in df.columns:
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"].astype(str).str.strip('"'))
        df = df.sort_values("timestamp_dt", ascending=True)
        df = df.drop_duplicates(subset=["input"], keep="last").reset_index(drop=True)
        df = df.drop(columns=["timestamp_dt"])
        
    geval = load_baseline_geval()
    if geval is not None and "traceId" in geval.columns and "id" in df.columns:
        df = df.merge(geval[["traceId"] + [c for c in geval.columns if c.startswith("geval")]],
                      left_on="id", right_on="traceId", how="left").drop(columns=["traceId"], errors="ignore")
        if "geval_avg_norm" in df.columns:
            df["geval_coherence_normalized"] = df["geval_avg_norm"]

    claims = load_baseline_claim_counts()
    if claims is not None and "traceId" in claims.columns and "id" in df.columns:
        df = df.merge(
            claims,
            left_on="id",
            right_on="traceId",
            how="left",
        ).drop(columns=["traceId"], errors="ignore")
    return df


def load_current_df() -> Optional[pd.DataFrame]:
    """Load current traces CSV and join G-Eval raw scores from observations."""
    from lib.observations_loader import load_current_geval, load_current_claim_counts
    root = repo_root()
    current_dir = root / "Eval_Data" / "Traces"
    csv_path = _pick_csv_with_nonbaseline_rows(current_dir) or _find_csv(current_dir)
    if csv_path is None:
        return None
    df = load_traces_csv(csv_path)

    # Exclude baseline workflow traces if the export contains multiple workflows.
    if "name" in df.columns:
        name_clean = df["name"].astype(str).str.strip('"').str.strip("'")
        df = df[name_clean != "BaselineWikiEvalWorkflow"].reset_index(drop=True)
        if df.empty:
            return None
    
    # Deduplicate by input, keeping latest timestamp
    if "input" in df.columns and "timestamp" in df.columns:
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"].astype(str).str.strip('"'))
        df = df.sort_values("timestamp_dt", ascending=True)
        df = df.drop_duplicates(subset=["input"], keep="last").reset_index(drop=True)
        df = df.drop(columns=["timestamp_dt"])
        
    geval = load_current_geval()
    if geval is not None and "traceId" in geval.columns and "id" in df.columns:
        df = df.merge(geval[["traceId"] + [c for c in geval.columns if c.startswith("geval")]],
                      left_on="id", right_on="traceId", how="left").drop(columns=["traceId"], errors="ignore")
        if "geval_avg_norm" in df.columns:
            df["geval_coherence_normalized"] = df["geval_avg_norm"]

    claims = load_current_claim_counts()
    if claims is not None and "traceId" in claims.columns and "id" in df.columns:
        df = df.merge(
            claims,
            left_on="id",
            right_on="traceId",
            how="left",
        ).drop(columns=["traceId"], errors="ignore")
    return df


def get_comparison_df(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    on: str = "input",
) -> pd.DataFrame:
    """
    Merge baseline and current DataFrames on the `input` column (story prompt).
    Returns a merged DataFrame with _baseline and _current suffixes on metric cols.
    """
    avail_metrics = [c for c in METRIC_COLS if c in baseline_df.columns and c in current_df.columns]

    b = baseline_df[["input"] + avail_metrics].copy()
    c = current_df[["input"] + avail_metrics].copy()

    b["input"] = b["input"].astype(str).str.strip('"').str[:200]
    c["input"] = c["input"].astype(str).str.strip('"').str[:200]

    merged = pd.merge(b, c, on="input", suffixes=("_baseline", "_current"), how="inner")
    return merged


def compute_deltas(comparison_df: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
    """
    Compute delta = current - baseline for each metric column.
    Returns a DataFrame with columns: input, {metric}_baseline, {metric}_current, {metric}_delta.
    """
    result = comparison_df[["input"]].copy()
    for metric in metric_cols:
        b_col = f"{metric}_baseline"
        c_col = f"{metric}_current"
        if b_col in comparison_df.columns and c_col in comparison_df.columns:
            result[b_col] = comparison_df[b_col]
            result[c_col] = comparison_df[c_col]
            result[f"{metric}_delta"] = comparison_df[c_col] - comparison_df[b_col]
    return result


def summary_stats(df: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
    """Compute mean, std, min, max for each metric column."""
    avail = [c for c in metric_cols if c in df.columns]
    rows = []
    for col in avail:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        rows.append({
            "Metric": METRIC_LABELS.get(col, col),
            "Mean": float(series.mean()) if len(series) else 0.0,
            "Std": float(series.std()) if len(series) > 1 else 0.0,
            "Min": float(series.min()) if len(series) else 0.0,
            "Max": float(series.max()) if len(series) else 0.0,
            "N": int(len(series)),
        })
    return pd.DataFrame(rows)
