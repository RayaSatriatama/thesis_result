"""
Coherence analysis tab for the Streamlit evaluation dashboard.

Covers:
- G-Eval (5 sub-criteria: Fluency, Consistency, Clarity, Conciseness, Repetitiveness)
- LLM Coherence Evaluator (EHM model, 0-10 scale)
- Baseline comparison for both metrics
"""

import json
import re
import ast
import math
from pathlib import Path
from typing import Optional

import altair as alt
import pandas as pd
import streamlit as st

from lib.baseline_loader import (
    METRIC_LABELS,
    load_baseline_df,
    load_current_df,
    summary_stats,
)
from lib.analysis_utils import (
    add_language_col,
    filter_by_language,
    language_filter_widget,
    distribution_chart,
    boxplot_chart,
    compute_significance,
    render_significance_table,
)
from lib.faithfulness_metrics import (
    filter_all_traces_by_language,
    filter_tops_by_language,
    load_all_traces_df,
    load_ten_story_traces_df,
)
from lib.paths import repo_root


# ---------------------------------------------------------------------------
# G-Eval sub-criteria table
# ---------------------------------------------------------------------------

_GEVAL_TABLE = pd.DataFrame([
    {"Sub-Criterion": "Fluency", "Scale": "1–5", "Aspect": "Grammar, syntax, natural sentence flow"},
    {"Sub-Criterion": "Consistency", "Scale": "1–5", "Aspect": "Uniform narrative voice and tone throughout"},
    {"Sub-Criterion": "Clarity", "Scale": "1–5", "Aspect": "Clear, accessible language; no ambiguous jargon"},
    {"Sub-Criterion": "Conciseness", "Scale": "1–5", "Aspect": "No filler or padding; purposeful paragraphs"},
    {"Sub-Criterion": "Repetitiveness", "Scale": "1–5 (5=none)", "Aspect": "Minimal redundant phrases or ideas"},
])

_COHERENCE_CRITERIA_TABLE = pd.DataFrame([
    {
        "Criterion": "Fabula & Logicality",
        "Aspect": "Causal network, world rules, character motivations, temporal consistency",
    },
    {
        "Criterion": "Plot & Consistency",
        "Aspect": "Event chain continuity, no out-of-character behavior, no contradictory facts",
    },
    {
        "Criterion": "Discourse",
        "Aspect": "Narrative flow, sentence variety, overall readability",
    },
    {
        "Criterion": "Long-term Causal Network",
        "Aspect": "Episodic memory across paragraphs; event boundaries handled correctly",
    },
    {
        "Criterion": "Knowledge Grounding & Faithfulness",
        "Aspect": "No hallucination; story faithfully maps to provided structured knowledge",
    },
])

_EXPERT_JUDGEMENT_DIMS: tuple[str, ...] = (
    "Fluency",
    "Consistency",
    "Clarity",
    "Conciseness",
    "Repetitiveness",
)

_SUB13_CRITERIA: list[dict[str, object]] = [
    {"no": 1, "butir": "Ketepatan struktur kalimat", "dimensi": "Fluency"},
    {"no": 2, "butir": "Ketepatan tata bahasa", "dimensi": "Fluency"},
    {"no": 3, "butir": "Ketepatan ejaan", "dimensi": "Fluency"},
    {"no": 4, "butir": "Kesesuaian intelektual", "dimensi": "Fluency"},
    {"no": 5, "butir": "Kesesuaian emosional", "dimensi": "Fluency"},
    {"no": 6, "butir": "Konsistensi istilah", "dimensi": "Consistency"},
    {"no": 7, "butir": "Konsistensi simbol/ikon", "dimensi": "Consistency"},
    {"no": 8, "butir": "Kebakuan istilah", "dimensi": "Clarity"},
    {"no": 9, "butir": "Pemahaman pesan", "dimensi": "Clarity"},
    {"no": 10, "butir": "Kemampuan memotivasi", "dimensi": "Clarity"},
    {"no": 11, "butir": "Mendorong berpikir kritis", "dimensi": "Clarity"},
    {"no": 12, "butir": "Keefektifan kalimat", "dimensi": "Conciseness"},
    {"no": 13, "butir": "Ketidak-repetitifan", "dimensi": "Repetitiveness"},
]

# ---------------------------------------------------------------------------
# Ground truth: Validasi ahli (13 butir x 5 cerita)
# ---------------------------------------------------------------------------
_VALIDATION_ID_STORY_SCORES: dict[int, list[float]] = {
    1: [4, 4, 4, 4, 4],
    2: [3, 3, 3, 3, 3],
    3: [3, 3, 3, 3, 3],
    4: [3, 3, 3, 3, 3],
    5: [3, 3, 3, 3, 3],
    6: [5, 5, 5, 3, 3],
    7: [5, 5, 5, 3, 3],
    8: [4, 4, 3, 3, 4],
    9: [5, 5, 5, 5, 5],
    10: [5, 5, 5, 5, 5],
    11: [5, 5, 5, 5, 5],
    12: [5, 5, 4, 4, 4],
    13: [5, 5, 5, 3, 3],
}

_VALIDATION_EN_STORY_SCORES: dict[int, list[float]] = {
    1: [5, 5, 5, 3, 3],
    2: [5, 5, 5, 3, 3],
    3: [5, 5, 5, 4, 4],
    4: [3, 3, 2, 2, 2],
    5: [3, 3, 2, 2, 2],
    6: [5, 5, 5, 3, 3],
    7: [5, 5, 5, 3, 3],
    8: [4, 4, 5, 2, 5],
    9: [5, 5, 5, 1, 5],
    10: [5, 5, 5, 1, 5],
    11: [4, 5, 4, 1, 4],
    12: [4, 4, 4, 4, 3],
    13: [5, 5, 5, 3, 3],
}

_SUB13_TO_DIM: dict[int, str] = {int(r["no"]): str(r["dimensi"]) for r in _SUB13_CRITERIA}


def _gt_dim_scores_from_validation(*, language: str) -> pd.DataFrame:
    """
    Return ground-truth per story (1..5) and per dimension (1..5 scale),
    computed from expert validation tables by grouping 13 butir into 5 dims.
    """
    if language == "id":
        src = _VALIDATION_ID_STORY_SCORES
    elif language == "en":
        src = _VALIDATION_EN_STORY_SCORES
    else:
        return pd.DataFrame()

    rows = []
    for story_idx in range(1, 6):
        by_dim: dict[str, list[float]] = {d: [] for d in _EXPERT_JUDGEMENT_DIMS}
        for item_no in range(1, 14):
            dim = _SUB13_TO_DIM.get(item_no)
            if not dim or dim not in by_dim:
                continue
            scores = src.get(item_no)
            if not scores or len(scores) < story_idx:
                continue
            by_dim[dim].append(float(scores[story_idx - 1]))

        row = {"language": language, "story_idx": story_idx}
        for dim in _EXPERT_JUDGEMENT_DIMS:
            vals = by_dim.get(dim) or []
            if not vals:
                row[dim] = float("nan")
                continue
            mean_dim = float(pd.Series(vals).mean())
            # Sesuai instruksi: rata-rata per dimensi dibulatkan menjadi label 1-5.
            # (clip diperlukan untuk menjaga konsistensi skala).
            row[dim] = _clip_round_label_1_5(mean_dim)
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def _ordered_titles_from_sampling_md(language: str) -> list[str]:
    """
    Use the sampling eval markdown as the canonical Cerita 1..5 ordering:
    scripts/sampling/expert_judgement_evals_coherence_{id,en}.md
    """
    root = repo_root()
    p = root / "scripts" / "sampling" / f"expert_judgement_evals_coherence_{language}.md"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    title_re = re.compile(r"^\s*###\s+Judul:\s*(.+?)\s*$", re.IGNORECASE)
    for ln in lines:
        m = title_re.match(ln)
        if m:
            out.append(m.group(1).strip())
    return out


def _clip_round_label_1_5(x: object) -> int | None:
    try:
        v = float(x)
    except Exception:
        return None
    if pd.isna(v):
        return None
    # Round half up (0.5 -> 1) for consistency with manual GT rounding.
    r = int(math.floor(v + 0.5)) if v >= 0 else int(math.ceil(v - 0.5))
    if r < 1:
        return 1
    if r > 5:
        return 5
    return r


def _confusion_matrix_1_5(y_true: list[int], y_pred: list[int]) -> pd.DataFrame:
    labels = [1, 2, 3, 4, 5]
    rows = []
    for t in labels:
        for p in labels:
            rows.append({"Ground Truth": t, "Prediksi": p, "Jumlah": 0})
    cm = pd.DataFrame(rows)
    if not y_true:
        return cm
    from collections import Counter

    counts = Counter(zip(y_true, y_pred))
    for (t, p), n in counts.items():
        cm.loc[(cm["Ground Truth"] == t) & (cm["Prediksi"] == p), "Jumlah"] = int(n)
    return cm


def _classification_report_1_5(y_true: list[int], y_pred: list[int]) -> pd.DataFrame:
    labels = [1, 2, 3, 4, 5]
    rows = []
    total = len(y_true)
    if total == 0:
        return pd.DataFrame()

    for lab in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p != lab)
        sup = sum(1 for t in y_true if t == lab)
        prec = (tp / (tp + fp)) if (tp + fp) else 0.0
        rec = (tp / (tp + fn)) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        rows.append(
            {
                "Kelas": str(lab),
                "Precision": prec,
                "Recall": rec,
                "F1-Score": f1,
                "Support": sup,
            }
        )

    df = pd.DataFrame(rows)
    present = df[df["Support"] > 0].copy()
    macro_base = present if not present.empty else df
    macro = {
        "Kelas": "Macro Avg",
        "Precision": float(macro_base["Precision"].mean()),
        "Recall": float(macro_base["Recall"].mean()),
        "F1-Score": float(macro_base["F1-Score"].mean()),
        "Support": total,
    }
    weighted = {
        "Kelas": "Weighted Avg",
        "Precision": float((df["Precision"] * df["Support"]).sum() / total),
        "Recall": float((df["Recall"] * df["Support"]).sum() / total),
        "F1-Score": float((df["F1-Score"] * df["Support"]).sum() / total),
        "Support": total,
    }
    out = pd.concat([df, pd.DataFrame([macro, weighted])], ignore_index=True)
    return out


def _subcriteria_table_from_validation(*, language: str) -> pd.DataFrame:
    if language == "id":
        src = _VALIDATION_ID_STORY_SCORES
    elif language == "en":
        src = _VALIDATION_EN_STORY_SCORES
    else:
        return pd.DataFrame()

    rows = []
    for r in _SUB13_CRITERIA:
        item_no = int(r["no"])
        scores = src.get(item_no, [float("nan")] * 5)
        scores = list(scores) + [float("nan")] * max(0, 5 - len(scores))
        rows.append(
            {
                "Dimensi": str(r["dimensi"]),
                "No": item_no,
                "Butir Penilaian": str(r["butir"]),
                "Cerita 1": scores[0],
                "Cerita 2": scores[1],
                "Cerita 3": scores[2],
                "Cerita 4": scores[3],
                "Cerita 5": scores[4],
            }
        )
    return pd.DataFrame(rows)


def _validator_language_summary_from_validation(*, language: str) -> pd.DataFrame:
    """
    Ekstraksi ringkasan nilai validator ahli bahasa untuk 5 cerita.

    Sumber: tabel validasi ahli (13 butir penilaian x 5 cerita) yang ditaruh di file ini.
    Output:
    - story_idx (1..5)
    - draft_title (mengikuti urutan judul di file sampling coherence)
    - mean_13 (rata-rata 13 butir untuk cerita tsb)
    """
    sub = _subcriteria_table_from_validation(language=language)
    if sub.empty:
        return pd.DataFrame()

    story_cols = [f"Cerita {i}" for i in range(1, 6)]
    for c in story_cols:
        if c not in sub.columns:
            return pd.DataFrame()

    titles = _ordered_titles_from_sampling_md(language)
    title_map = {i + 1: (titles[i].strip() if i < len(titles) else "") for i in range(5)}

    rows: list[dict[str, object]] = []
    for story_idx in range(1, 6):
        col = f"Cerita {story_idx}"
        ser = pd.to_numeric(sub[col], errors="coerce")
        mean_13 = float(ser.mean(skipna=True)) if not ser.dropna().empty else float("nan")
        rows.append(
            {
                "story_idx": story_idx,
                "draft_title": title_map.get(story_idx, ""),
                "mean_13": mean_13,
            }
        )
    return pd.DataFrame(rows)


def _style_gt_pred_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    comp_cols = [c for c in df.columns if c.startswith("C") and "(GT / Pred)" in c]

    def _cell_style(v: object) -> str:
        s = str(v or "").strip()
        if not s or "/" not in s:
            return ""
        left, right = [x.strip() for x in s.split("/", 1)]
        if not left or not right:
            return ""
        if left == right:
            return "background-color: #0f172a; color: #e2e8f0;"
        return "background-color: #7f1d1d; color: #fee2e2; font-weight: 700;"

    sty = df.style
    for c in comp_cols:
        sty = sty.map(_cell_style, subset=[c])
    return sty


def _build_gt_pred_comparison_table(
    *,
    language: str,
    chosen: pd.DataFrame,
    gt_all: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build table:
    index: Dimensi
    columns: C1..C5 (GT / Pred)
    values: "{gt} / {pred}" (rounded labels 1-5)
    """
    titles = _ordered_titles_from_sampling_md(language)
    title_to_idx = {t.strip(): i + 1 for i, t in enumerate(titles)}

    # Pred labels per (story_idx, dim)
    pred_map: dict[tuple[int, str], int] = {}
    for _, r in chosen[chosen["language"] == language].iterrows():
        story_idx = title_to_idx.get(str(r.get("draft_title") or "").strip())
        if not story_idx:
            continue
        for dim in _EXPERT_JUDGEMENT_DIMS:
            pred_map[(story_idx, dim)] = _clip_round_label_1_5(r.get(dim))

    # GT labels per (story_idx, dim)
    gt_map: dict[tuple[int, str], int] = {}
    sub = gt_all[gt_all["language"] == language].copy()
    for _, r in sub.iterrows():
        story_idx = int(r.get("story_idx"))
        for dim in _EXPERT_JUDGEMENT_DIMS:
            gt_map[(story_idx, dim)] = _clip_round_label_1_5(r.get(dim))

    rows = []
    for dim in _EXPERT_JUDGEMENT_DIMS:
        row = {"Dimensi": dim}
        for story_idx in range(1, 6):
            gt = gt_map.get((story_idx, dim))
            pr = pred_map.get((story_idx, dim))
            key = f"C{story_idx} (GT / Pred)"
            if gt is None or pr is None:
                row[key] = ""
            else:
                row[key] = f"{gt} / {pr}"
        rows.append(row)
    out = pd.DataFrame(rows).set_index("Dimensi")
    return out


def _parse_expert_judgement_md(text: str, *, language: str) -> pd.DataFrame:
    """
    Parse sampling file:
    scripts/sampling/expert_judgement_evals_coherence_{id,en}.md

    Extract per-story:
    - title
    - G-Eval Norm (if present)
    - 5 sub-criteria scores (1-5)
    """
    lines = (text or "").splitlines()
    rows: list[dict] = []

    current: dict | None = None
    title_re = re.compile(r"^\s*###\s+Judul:\s*(.+?)\s*$", re.IGNORECASE)
    norm_re = re.compile(r"Koherensi\s+\(G-Eval\s+Norm\):\*\*\s*`([\d.]+)`", re.IGNORECASE)
    score_re = re.compile(
        r"^\s*-\s*\*\*(Fluency|Consistency|Clarity|Conciseness|Repetitiveness)\s*:\*\*.*?\*\*Skor\s+(\d+)\s*:",
        re.IGNORECASE,
    )

    def _flush() -> None:
        nonlocal current
        if not current:
            return
        title = str(current.get("title") or "").strip()
        if not title:
            current = None
            return
        for dim in _EXPERT_JUDGEMENT_DIMS:
            current.setdefault(dim, None)
        rows.append(current)
        current = None

    for raw in lines:
        m_title = title_re.match(raw)
        if m_title:
            _flush()
            current = {"language": language, "title": m_title.group(1).strip()}
            continue

        if current is None:
            continue

        m_norm = norm_re.search(raw)
        if m_norm:
            try:
                current["geval_norm"] = float(m_norm.group(1))
            except Exception:
                pass
            continue

        m_score = score_re.match(raw)
        if m_score:
            dim = m_score.group(1).strip().title()
            try:
                score = float(m_score.group(2))
            except Exception:
                score = None
            if dim in _EXPERT_JUDGEMENT_DIMS:
                current[dim] = score

    _flush()

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for dim in _EXPERT_JUDGEMENT_DIMS:
        if dim in df.columns:
            df[dim] = pd.to_numeric(df[dim], errors="coerce")

    df["mean_dim"] = df[list(_EXPERT_JUDGEMENT_DIMS)].mean(axis=1, skipna=True)
    df["f1_score"] = df["mean_dim"] / 5.0
    return df


def _load_expert_judgement_samples() -> pd.DataFrame:
    root = repo_root()
    p_id = root / "scripts" / "sampling" / "expert_judgement_evals_coherence_id.md"
    p_en = root / "scripts" / "sampling" / "expert_judgement_evals_coherence_en.md"

    dfs = []
    if p_id.exists():
        dfs.append(_parse_expert_judgement_md(p_id.read_text(encoding="utf-8"), language="id"))
    if p_en.exists():
        dfs.append(_parse_expert_judgement_md(p_en.read_text(encoding="utf-8"), language="en"))

    if not dfs:
        return pd.DataFrame()
    out = pd.concat(dfs, ignore_index=True)
    return out


def _parse_metric_cell(v: object) -> float:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return float("nan")
    s = str(v).strip().strip('"').strip("'")
    if not s or s == "[]":
        return float("nan")
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            vals = [float(x) for x in parsed if str(x).strip() != ""]
            return float(pd.Series(vals).mean()) if vals else float("nan")
        return float(parsed)
    except Exception:
        try:
            return float(s)
        except Exception:
            return float("nan")


def _latest_file(directory: Path, pattern: str) -> Path | None:
    files = list(directory.glob(pattern))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _load_latest_traces_df() -> pd.DataFrame:
    root = repo_root()
    traces_dir = root / "Eval_Data" / "Traces"
    p = _latest_file(traces_dir, "*.csv")
    if p is None:
        return pd.DataFrame()

    df = pd.read_csv(p, encoding="utf-8")
    if "id" in df.columns:
        df["id"] = df["id"].astype(str).str.strip('"').str.strip("'")

    for col in ["geval_coherence_normalized", "ragas_standard_faithfulness", "fables_faithfulness"]:
        if col in df.columns:
            df[col] = df[col].apply(_parse_metric_cell)
    return df


def _extract_title_from_trace_output(raw_output: object) -> str:
    if raw_output is None:
        return ""
    if isinstance(raw_output, dict):
        return str(raw_output.get("draft_title") or "").strip()
    s = str(raw_output).strip()
    if not s:
        return ""
    parsed = None
    try:
        parsed = json.loads(s)
    except Exception:
        try:
            parsed = ast.literal_eval(s)
        except Exception:
            parsed = None
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            parsed = None
    if isinstance(parsed, dict):
        return str(parsed.get("draft_title") or "").strip()
    return ""


def _pick_samples_from_eval_data(df_all: pd.DataFrame, *, lang_key: str) -> pd.DataFrame:
    """
    Sampling berasal dari Eval_Data dengan aturan (per bahasa):
    - max 2
    - min 2
    - median 1 (jarak sentral ke median sistem)

    Hierarki metrik (Coherence):
    - utama: geval_coherence_normalized
    - sekunder: ragas_standard_faithfulness
    - tersier: fables_faithfulness
    """
    if df_all is None or df_all.empty:
        return pd.DataFrame()

    if lang_key == "en":
        df = df_all[df_all["input"].astype(str).str.contains("Create an", na=False)].copy()
    elif lang_key == "id":
        df = df_all[df_all["input"].astype(str).str.contains("Buat cerita", na=False)].copy()
    else:
        return pd.DataFrame()

    metrik_utama = "geval_coherence_normalized"
    metrik_ragas = "ragas_standard_faithfulness"
    metrik_fables = "fables_faithfulness"
    needed = [metrik_utama, metrik_ragas, metrik_fables, "id"]
    if not all(c in df.columns for c in needed):
        return pd.DataFrame()

    df_valid = df.dropna(subset=[metrik_utama, metrik_ragas, metrik_fables]).copy()
    if df_valid.empty:
        return pd.DataFrame()

    sort_metrics = [metrik_utama, metrik_ragas, metrik_fables]

    # 1) max 2
    s_max = df_valid.sort_values(by=sort_metrics, ascending=[False, False, False]).head(2).copy()
    s_max["kategori"] = "MAX (Best Cases)"
    df_valid = df_valid.drop(s_max.index)

    # 2) min 2
    s_min = df_valid.sort_values(by=sort_metrics, ascending=[True, True, True]).head(2).copy()
    s_min["kategori"] = "MIN (Worst Cases)"
    df_valid = df_valid.drop(s_min.index)

    # 3) median 1 (distance to medians of remaining pool)
    median_coh = float(df_valid[metrik_utama].median())
    median_ragas = float(df_valid[metrik_ragas].median())
    median_fables = float(df_valid[metrik_fables].median())
    df_valid["jarak_sentral"] = (
        (df_valid[metrik_utama] - median_coh) ** 2
        + (df_valid[metrik_ragas] - median_ragas) ** 2
        + (df_valid[metrik_fables] - median_fables) ** 2
    ) ** 0.5
    s_med = df_valid.sort_values("jarak_sentral", ascending=True).head(1).copy()
    s_med["kategori"] = "MEDIAN (Average Case)"

    out = pd.concat([s_max, s_med, s_min], ignore_index=True)
    out["language"] = lang_key
    out["draft_title"] = out.get("output", pd.Series([""] * len(out))).apply(_extract_title_from_trace_output)
    return out


def _load_latest_geval_dim_scores(trace_ids: set[str]) -> pd.DataFrame:
    root = repo_root()
    obs_dir = root / "Eval_Data" / "Observations"
    p = _latest_file(obs_dir, "*.jsonl")
    if p is None or not trace_ids:
        return pd.DataFrame()

    rows: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            trace_id = str(obj.get("traceId") or "")
            if trace_id not in trace_ids:
                continue

            name = str(obj.get("name") or "")
            if not name.startswith("geval_"):
                continue

            output = obj.get("output", {})
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except Exception:
                    output = {}

            if not isinstance(output, dict):
                continue

            score = output.get("score", None)
            try:
                score_f = float(score)
            except Exception:
                continue

            dim = name.replace("geval_", "").strip().title()
            if dim not in _EXPERT_JUDGEMENT_DIMS:
                continue

            rows.append({"trace_id": trace_id, "dim": dim, "score": score_f})

    if not rows:
        return pd.DataFrame()

    wide = pd.DataFrame(rows).pivot_table(index="trace_id", columns="dim", values="score", aggfunc="mean").reset_index()
    wide.columns.name = None
    return wide


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _short_prompt(text: str, max_chars: int = 60) -> str:
    t = str(text).strip('"').strip("'")
    return t[:max_chars] + "…" if len(t) > max_chars else t


def _load_geval_comparison() -> tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Return (baseline_df, current_df, comparison_df) with geval_coherence_normalized."""
    baseline = load_baseline_df()
    current = load_current_df()

    if baseline is None or current is None:
        return baseline, current, None

    metric = "geval_coherence_normalized"
    if metric not in baseline.columns or metric not in current.columns:
        return baseline, current, None

    from lib.baseline_loader import get_comparison_df
    comp = get_comparison_df(baseline, current)
    return baseline, current, comp


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _geval_bar_chart(df: pd.DataFrame, col: str, title: str) -> alt.Chart:
    """Bar chart of geval scores per story (short prompt as label)."""
    plot_df = df[["input", col]].dropna().copy()
    plot_df["story"] = plot_df["input"].apply(lambda x: _short_prompt(x, 55))
    plot_df["score"] = plot_df[col].round(4)

    return (
        alt.Chart(plot_df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("story:N", sort="-y", axis=alt.Axis(labelAngle=-35, labelLimit=250), title="Story"),
            y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 1]), title="G-Eval Normalized (0–1)"),
            color=alt.Color(
                "score:Q",
                scale=alt.Scale(scheme="blues", domain=[0, 1]),
                legend=None,
            ),
            tooltip=["story:N", alt.Tooltip("score:Q", format=".3f")],
        )
        .properties(title=title, height=320)
    )


def _delta_bar_chart(delta_df: pd.DataFrame, metric: str, label: str) -> alt.Chart:
    """Side-by-side delta bar chart (baseline vs current) for one metric."""
    b_col = f"{metric}_baseline"
    c_col = f"{metric}_current"
    d_col = f"{metric}_delta"

    if not all(c in delta_df.columns for c in [b_col, c_col, d_col]):
        return None

    rows = []
    for _, row in delta_df.dropna(subset=[b_col, c_col]).iterrows():
        story = _short_prompt(row["input"], 50)
        rows.append({"Story": story, "Source": "Baseline", "Score": row[b_col]})
        rows.append({"Story": story, "Source": "Current", "Score": row[c_col]})

    plot_df = pd.DataFrame(rows)
    return (
        alt.Chart(plot_df)
        .mark_bar()
        .encode(
            x=alt.X("Story:N", axis=alt.Axis(labelAngle=-35, labelLimit=200)),
            y=alt.Y("Score:Q", title=label),
            color=alt.Color(
                "Source:N",
                scale=alt.Scale(domain=["Baseline", "Current"], range=["#64748b", "#3b82f6"]),
            ),
            xOffset="Source:N",
            tooltip=["Story:N", "Source:N", alt.Tooltip("Score:Q", format=".3f")],
        )
        .properties(height=300)
    )


def _coherence_dist_chart_notebook_style(
    df: pd.DataFrame,
    col: str,
    title: str,
    sample_df: pd.DataFrame | None = None,
    sample_label: str = "Sampling",
    bar_color: str = "#805AD5",
    kde_color: str = "#4A148C",
) -> alt.Chart:
    """Notebook-style distribution chart for coherence."""
    if df.empty or col not in df.columns:
        return alt.Chart().mark_text(text="Data tidak tersedia").properties(height=300)

    sub = df[[col]].copy()
    sub[col] = pd.to_numeric(sub[col], errors="coerce")
    sub = sub.dropna()

    if sub.empty:
        return alt.Chart().mark_text(text="Data tidak tersedia").properties(height=300)

    if "normalized" in col or "score" not in col and "geval" not in col:
        extent_lo, extent_hi = 0.0, 1.0 if "normalized" in col else 5.0
        if "geval_avg_raw" in col or "educational_score" in col:
            extent_lo, extent_hi = 1.0, 5.0
    else:
        extent_lo, extent_hi = 0.0, 1.0

    span = extent_hi - extent_lo

    if span <= 1.0:
        bin_config = alt.Bin(step=0.1, extent=[0.0, 1.0])
        x_axis = alt.Axis(titleFontSize=11, labelFontSize=10, labelAngle=-45, grid=False, values=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    else:
        bin_config = alt.Bin(step=0.5, extent=[extent_lo, extent_hi])
        x_axis = alt.Axis(titleFontSize=11, labelFontSize=10, labelAngle=-45, grid=False, values=[1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0])

    y_axis = alt.Axis(titleFontSize=11, labelFontSize=10, grid=True, gridColor="#f0f0f0", tickCount=5)

    histogram = (
        alt.Chart(sub)
        .mark_bar(opacity=0.85, color=bar_color)
        .encode(
            x=alt.X(f"{col}:Q", bin=bin_config, axis=x_axis, title="Skor Koherensi", scale=alt.Scale(domain=[extent_lo, extent_hi])),
            y=alt.Y("count()", title="Frekuensi", axis=y_axis),
            tooltip=[
                alt.Tooltip(f"{col}:Q", bin=bin_config, title="Skor", format=".3f"),
                alt.Tooltip("count()", title="Jumlah"),
            ],
        )
    )

    layers: list[alt.Chart] = [histogram]

    if len(sub) >= 2:
        # Gunakan bandwidth yang lebih kecil (tajam) agar sesuai dengan histogram
        bw = max(span * 0.08, 0.02) if span > 0 else 0.05
        kde = (
            alt.Chart(sub)
            .transform_density(
                col,
                as_=[col, "density"],
                groupby=[],
                extent=[extent_lo, extent_hi],
                bandwidth=bw,
            )
            .mark_line(color=kde_color, strokeWidth=2.5)
            .encode(
                x=alt.X(f"{col}:Q", axis=x_axis),
                y=alt.Y("density:Q", axis=None),
                tooltip=[
                    alt.Tooltip(field=col, type="quantitative", title="Skor", format=".3f"),
                    alt.Tooltip("density:Q", title="Densitas", format=".3f"),
                ],
            )
        )
        layers.append(kde)

    s = sub[col]
    marker_label_min, marker_label_mean, marker_label_max = "Min", "Mean", "Max"
    
    ref_s = s
    if sample_df is not None and not sample_df.empty and col in sample_df.columns:
        s_samp = pd.to_numeric(sample_df[col], errors="coerce").dropna()
        if not s_samp.empty:
            ref_s = s_samp

    markers = pd.DataFrame([
        {"kind": marker_label_min, "value": float(ref_s.min())},
        {"kind": marker_label_mean, "value": float(ref_s.mean())},
        {"kind": marker_label_max, "value": float(ref_s.max())},
    ])
    
    color_scale = alt.Scale(
        domain=[marker_label_min, marker_label_mean, marker_label_max],
        range=["#1565C0", "#C62828", "#2E7D32"],
    )
    rules = (
        alt.Chart(markers)
        .mark_rule(strokeWidth=2.5, strokeDash=[7, 4])
        .encode(
            x=alt.X("value:Q", axis=x_axis),
            color=alt.Color(
                "kind:N", scale=color_scale,
                legend=alt.Legend(title=None, labelFontSize=10, symbolStrokeWidth=2, orient="top", direction="horizontal", symbolType="stroke", symbolDash=[7, 4]),
            ),
            tooltip=[alt.Tooltip("kind:N", title="Marker"), alt.Tooltip("value:Q", title="Nilai", format=".3f")],
        )
    )
    layers.append(rules)

    chart_title = alt.TitleParams(
        text=title, 
        fontSize=13, 
        fontWeight="bold", 
        color="#212121", 
        subtitleFontSize=10, 
        subtitleColor="#555555",
        limit=500,
    )
    return alt.layer(*layers).resolve_scale(y="independent").properties(height=300, title=chart_title)


def _describe_coherence_scores_combined(df_all: pd.DataFrame, df_en: pd.DataFrame, df_id: pd.DataFrame) -> pd.DataFrame | None:
    cols = {
        "geval_coherence_normalized": "Koherensi Naratif",
        "educational_score": "Skor Edukatif",
    }
    
    rows = []
    
    def _add_stats(sub_df, pop_label, c_name, base_label):
        if sub_df is None or sub_df.empty or c_name not in sub_df.columns:
            return
        s = pd.to_numeric(sub_df[c_name], errors="coerce").dropna()
        if s.empty:
            return
        rows.append({
            "Metrik": f"{base_label} ({pop_label})",
            "N": int(s.count()),
            "Mean": s.mean(),
            "Median": s.median(),
            "Std Dev": s.std(),
            "Min": s.min(),
            "Q1": s.quantile(0.25),
            "Q3": s.quantile(0.75),
            "Max": s.max(),
        })

    for c, label in cols.items():
        _add_stats(df_en, "EN", c, label)
        _add_stats(df_id, "ID", c, label)
        _add_stats(df_all, "Keseluruhan", c, label)
        
    return pd.DataFrame(rows) if rows else None


def _format_stats_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    return df.style.format({
        "Mean": "{:.3f}",
        "Median": "{:.3f}",
        "Std Dev": "{:.3f}",
        "Min": "{:.3f}",
        "Q1": "{:.3f}",
        "Q3": "{:.3f}",
        "Max": "{:.3f}"
    })


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render_coherence_tab() -> None:
    st.header("Analisis Koherensi Naratif")
    st.markdown(
        "Tab ini menampilkan dua dimensi evaluasi koherensi: "
        "**G-Eval** (kualitas linguistik, 5 sub-kriteria) dan "
        "**LLM Coherence Evaluator** (model Event Horizon, 0–10), "
        "beserta perbandingan dengan data baseline."
    )

    # Global language filter — affects all sections
    lang_key = language_filter_widget(key_suffix="coherence")

    st.header("Ringkasan Performa Klasifikasi (Expert Judgement vs Auto-Grade)")
    st.caption(
        "Sampel dipilih dari `Eval_Data/Traces` dengan aturan per bahasa: max 2, min 2, median 1 "
        "(hierarki: `geval_coherence_normalized`, `ragas_standard_faithfulness`, `fables_faithfulness`). "
        "Skor 5 dimensi (1-5) diambil dari `Eval_Data/Observations` dengan nama `geval_*`. "
        "Ground truth dipakai dari **tabel validasi ahli** (13 butir untuk 5 cerita), "
        "dikelompokkan ke dimensi: Fluency (1-5), Consistency (6-7), Clarity (8-11), "
        "Conciseness (12), Repetitiveness (13). "
        "Pemetaan Cerita 1..5 ke judul menggunakan urutan di `scripts/sampling/expert_judgement_evals_coherence_{id,en}.md`. "
        "Evaluasi dihitung sebagai **klasifikasi multi-kelas (1-5)**: `y_true` = skor expert, `y_pred` = skor auto-grade (dibulatkan)."
    )

    df_traces = _load_latest_traces_df()
    if df_traces.empty:
        st.warning("CSV trace tidak ditemukan di Eval_Data/Traces.")
    else:
        chosen_frames = []
        if lang_key in ("all", "id"):
            chosen_frames.append(_pick_samples_from_eval_data(df_traces, lang_key="id"))
        if lang_key in ("all", "en"):
            chosen_frames.append(_pick_samples_from_eval_data(df_traces, lang_key="en"))
        chosen = pd.concat([c for c in chosen_frames if c is not None and not c.empty], ignore_index=True)

        if chosen.empty:
            st.warning("Sampel tidak dapat dipilih dari trace (metrik atau filter tidak cocok).")
        else:
            trace_ids = set(chosen["id"].astype(str).tolist())
            dims = _load_latest_geval_dim_scores(trace_ids)
            if not dims.empty:
                chosen = chosen.merge(dims, left_on="id", right_on="trace_id", how="left").drop(columns=["trace_id"], errors="ignore")

            # Ground truth: validasi ahli (13 butir x 5 cerita) -> 5 dimensi
            chosen["draft_title"] = chosen["draft_title"].astype(str).str.strip()

            y_true: list[int] = []
            y_pred: list[int] = []
            y_rows: list[dict] = []
            n_labels = 0
            report = pd.DataFrame()

            gt_frames = []
            for lk in ["id", "en"]:
                if lang_key != "all" and lang_key != lk:
                    continue
                titles = _ordered_titles_from_sampling_md(lk)
                if len(titles) != 5:
                    continue
                gt_dim = _gt_dim_scores_from_validation(language=lk)
                if gt_dim.empty:
                    continue
                title_map = pd.DataFrame(
                    {"language": lk, "story_idx": [1, 2, 3, 4, 5], "draft_title": titles}
                )
                gt = title_map.merge(gt_dim, on=["language", "story_idx"], how="left")
                gt_frames.append(gt)

            gt_all = pd.concat(gt_frames, ignore_index=True) if gt_frames else pd.DataFrame()
            if gt_all.empty:
                st.warning("Ground truth validasi ahli tidak bisa dibangun (cek file sampling coherence).")
                st.divider()
            else:
                merged = chosen.merge(
                    gt_all[["language", "draft_title"] + list(_EXPERT_JUDGEMENT_DIMS)],
                    on=["language", "draft_title"],
                    how="left",
                    suffixes=("", "_gt"),
                )
                for _, r in merged.iterrows():
                    for dim in _EXPERT_JUDGEMENT_DIMS:
                        gt = _clip_round_label_1_5(r.get(f"{dim}_gt"))
                        pr = _clip_round_label_1_5(r.get(dim))
                        if gt is None or pr is None:
                            continue
                        y_true.append(gt)
                        y_pred.append(pr)
                        y_rows.append({"Judul": r.get("draft_title", ""), "Dimensi": dim, "GT": gt, "Pred": pr})

                n_labels = len(y_true)
                acc = (sum(1 for t, p in zip(y_true, y_pred) if t == p) / n_labels) if n_labels else 0.0
                report = _classification_report_1_5(y_true, y_pred)
                macro_f1 = float(report.loc[report["Kelas"] == "Macro Avg", "F1-Score"].iloc[0]) if not report.empty else 0.0
                weighted_f1 = float(report.loc[report["Kelas"] == "Weighted Avg", "F1-Score"].iloc[0]) if not report.empty else 0.0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Macro F1-Score (1-5)", f"{macro_f1:.3f}", "Keseluruhan")
                c2.metric("Weighted F1-Score (1-5)", f"{weighted_f1:.3f}", "Keseluruhan")
                c3.metric("Accuracy (Exact Match)", f"{acc * 100:.2f}%", "Kesamaan label")
                c4.metric("Total Label Dievaluasi", str(n_labels), "5 dimensi x cerita")

            st.markdown("---")

            st.header("Detail Analisis: Confusion Matrix dan Classification Report")
            col_left, col_right = st.columns([1.25, 1.75])

            with col_left:
                st.subheader("Confusion Matrix (Label 1-5)")
                st.caption("Baris = Ground Truth (expert), Kolom = Prediksi (auto-grade).")

                if n_labels:
                    cm_df = _confusion_matrix_1_5(y_true, y_pred)
                    base = alt.Chart(cm_df).encode(
                        x=alt.X("Prediksi:O", sort=[1, 2, 3, 4, 5], title="Prediksi (Auto-Grade)"),
                        y=alt.Y("Ground Truth:O", sort=[1, 2, 3, 4, 5], title="Ground Truth (Expert)"),
                    )
                    cm_max = max(int(cm_df["Jumlah"].max()), 1)
                    color_max = max(cm_max, 10)
                    rects = base.mark_rect().encode(
                        color=alt.Color(
                            "Jumlah:Q",
                            scale=alt.Scale(scheme="blues", domain=[0, color_max]),
                            legend=None,
                        )
                    )
                    text = base.mark_text(baseline="middle", size=18, fontWeight="bold").encode(
                        text="Jumlah:Q",
                        color=alt.condition(
                            alt.datum.Jumlah > (color_max * 0.35), alt.value("white"), alt.value("black")
                        ),
                    )
                    st.altair_chart((rects + text).properties(height=320), use_container_width=True)
                else:
                    st.info("Confusion matrix tidak tersedia (ground truth/prediksi kosong).")

                with st.expander("Pemetaan 13 butir penilaian -> dimensi (sesuai Eval_Data)"):
                    st.caption(
                        "Pengelompokan: Fluency (1-5), Consistency (6-7), Clarity (8-11), "
                        "Conciseness (12), Repetitiveness (13). "
                        "Skor per dimensi bersumber dari Observations `geval_*` (skala 1-5)."
                    )
                    map_df = pd.DataFrame(_SUB13_CRITERIA).rename(
                        columns={"no": "No", "butir": "Butir Penilaian", "dimensi": "Dimensi"}
                    )
                    st.dataframe(map_df, use_container_width=True, hide_index=True)

            with col_right:
                st.subheader("Classification Report (Multi-class 1-5)")
                st.caption("Precision/Recall/F1 dihitung per kelas label (1-5), lalu agregasi macro dan weighted.")
                if n_labels and not report.empty:
                    rep = report.copy()
                    for c in ["Precision", "Recall", "F1-Score"]:
                        rep[c] = rep[c].map(lambda x: f"{float(x) * 100:.2f}%" if pd.notna(x) else "")
                    rep["Support"] = rep["Support"].astype(int).astype(str)
                    st.dataframe(rep.set_index("Kelas"), use_container_width=True)
                else:
                    st.info("Classification report tidak tersedia (ground truth/prediksi kosong).")

                with st.expander("Detail label per dimensi dan judul (GT vs Pred)"):
                    if y_rows:
                        y_df = pd.DataFrame(y_rows)
                        st.dataframe(y_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("Tidak ada pasangan label GT vs Pred yang dapat ditampilkan.")

                with st.expander("Tabel pembandingan GT vs Pred (diwarnai jika berbeda)"):
                    st.caption(
                        "Format: `GT / Pred`. Sel berwarna merah menandakan nilai tidak sama. "
                        "Tabel ini mengikuti format dokumen pembandingan rata-rata per dimensi."
                    )
                    if gt_all.empty:
                        st.info("Tabel pembandingan tidak tersedia (ground truth kosong).")
                    else:
                        tab_id, tab_en = st.tabs(["Bahasa Indonesia", "Bahasa Inggris"])
                        with tab_id:
                            df_cmp = _build_gt_pred_comparison_table(language="id", chosen=chosen, gt_all=gt_all)
                            st.dataframe(_style_gt_pred_table(df_cmp), use_container_width=True)
                        with tab_en:
                            df_cmp = _build_gt_pred_comparison_table(language="en", chosen=chosen, gt_all=gt_all)
                            st.dataframe(_style_gt_pred_table(df_cmp), use_container_width=True)

                st.divider()
                st.subheader("Tabel Nilai 13 Sub-Kriteria (GT)")
                st.caption(
                    "Tabel ini mengikuti format dokumen validasi ahli: Dimensi, No, Butir Penilaian, Cerita 1-5. "
                    "Nilai yang ditampilkan adalah GT terbaru (setelah penyesuaian)."
                )

                st.subheader("Ekstraksi Nilai Validator Ahli Bahasa (Ringkasan)")
                st.caption(
                    "Ringkasan dihitung dari tabel 13 butir (GT): rata-rata per cerita dan rata-rata keseluruhan per bahasa."
                )
                sum_id, sum_en = st.tabs(["Bahasa Indonesia", "Bahasa Inggris"])
                with sum_id:
                    df_sum = _validator_language_summary_from_validation(language="id")
                    overall = float(pd.to_numeric(df_sum["mean_13"], errors="coerce").mean(skipna=True)) if not df_sum.empty else float("nan")
                    st.metric("Rata-rata keseluruhan (13 butir x 5 cerita)", f"{overall:.3f}" if not pd.isna(overall) else "N/A")
                    if not df_sum.empty:
                        st.dataframe(
                            df_sum.rename(
                                columns={
                                    "story_idx": "Cerita",
                                    "draft_title": "Judul",
                                    "mean_13": "Rata-rata (13 butir)",
                                }
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("Ringkasan tidak tersedia (tabel validasi kosong).")
                with sum_en:
                    df_sum = _validator_language_summary_from_validation(language="en")
                    overall = float(pd.to_numeric(df_sum["mean_13"], errors="coerce").mean(skipna=True)) if not df_sum.empty else float("nan")
                    st.metric("Rata-rata keseluruhan (13 butir x 5 cerita)", f"{overall:.3f}" if not pd.isna(overall) else "N/A")
                    if not df_sum.empty:
                        st.dataframe(
                            df_sum.rename(
                                columns={
                                    "story_idx": "Cerita",
                                    "draft_title": "Judul",
                                    "mean_13": "Rata-rata (13 butir)",
                                }
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("Ringkasan tidak tersedia (tabel validasi kosong).")

                v_id, v_en = st.tabs(["A. Lembar Validasi Bahasa Indonesia", "B. Lembar Validasi Bahasa Inggris"])
                with v_id:
                    st.dataframe(
                        _subcriteria_table_from_validation(language="id"),
                        use_container_width=True,
                        hide_index=True,
                    )
                with v_en:
                    st.dataframe(
                        _subcriteria_table_from_validation(language="en"),
                        use_container_width=True,
                        hide_index=True,
                    )

            # Cross-check vs urutan judul file sampling coherence (Cerita 1..5)
            sampling_titles = []
            if lang_key in ("all", "id"):
                sampling_titles += _ordered_titles_from_sampling_md("id")
            if lang_key in ("all", "en"):
                sampling_titles += _ordered_titles_from_sampling_md("en")
            sampling_titles_set = set([t.strip() for t in sampling_titles if str(t).strip()])
            chosen_titles = set(chosen["draft_title"].astype(str).str.strip())
            missing = sorted([t for t in chosen_titles if t and t not in sampling_titles_set])
            extra = sorted([t for t in sampling_titles_set if t and t not in chosen_titles])
            with st.expander("Cek kesamaan judul vs file sampling coherence"):
                st.write(f"Judul dipilih dari Eval_Data: {len([t for t in chosen_titles if t])}")
                st.write(f"Judul di file sampling coherence: {len([t for t in sampling_titles_set if t])}")
                if not missing and not extra:
                    st.success("Judul match 100% antara Eval_Data sampling dan file sampling coherence.")
                else:
                    if missing:
                        st.warning("Ada judul sampel dari Eval_Data yang tidak ditemukan di file sampling coherence.")
                        st.code("\n".join(missing), language="text")
                    if extra:
                        st.warning("Ada judul di file sampling coherence yang tidak terpilih oleh sampling Eval_Data.")
                        st.code("\n".join(extra), language="text")

    st.markdown("---")

    st.header("Statistik Skor Koherensi (Tingkat Jejak / Trace)")
    st.caption(
        "Distribusi mencakup **seluruh** trace pada CSV terbaru. "
        "Setiap baris menampilkan 3 kolom bahasa: **Keseluruhan** (N=100), "
        "**Bahasa Inggris** (N=50), dan **Bahasa Indonesia** (N=50). "
        "Garis putus-putus vertikal menandai **min / mean / max** dari "
        "subset sampling skripsi (10 jejak; 5 per bahasa). "
        "Legenda Min, Mean, dan Max ditampilkan di dalam grafik pada sisi kiri atas."
    )

    all_df_raw: pd.DataFrame | None = None
    try:
        all_df_raw = load_all_traces_df()
    except Exception:
        all_df_raw = None

    tops_df_raw: pd.DataFrame | None = None
    try:
        tops_df_raw = load_ten_story_traces_df()
    except Exception:
        tops_df_raw = None

    if all_df_raw is not None and not all_df_raw.empty:
        all_scores_all = filter_all_traces_by_language(all_df_raw, "all")
        all_scores_en = filter_all_traces_by_language(all_df_raw, "en")
        all_scores_id = filter_all_traces_by_language(all_df_raw, "id")

        tops_all = filter_tops_by_language(tops_df_raw, "all") if tops_df_raw is not None else None
        tops_en = filter_tops_by_language(tops_df_raw, "en") if tops_df_raw is not None else None
        tops_id = filter_tops_by_language(tops_df_raw, "id") if tops_df_raw is not None else None

        n_all = int(all_scores_all.shape[0]) if all_scores_all is not None else 0
        n_en = int(all_scores_en.shape[0]) if all_scores_en is not None else 0
        n_id = int(all_scores_id.shape[0]) if all_scores_id is not None else 0
        n_tops = int(tops_all.shape[0]) if tops_all is not None else 0

        st.caption(
            f"Populasi: N={n_all} (Keseluruhan), N={n_en} (Inggris), N={n_id} (Indonesia). "
            f"Subset sampling skripsi: n={n_tops} jejak."
        )

        stats_tbl = _describe_coherence_scores_combined(all_scores_all, all_scores_en, all_scores_id)
        if stats_tbl is not None:
            st.markdown(f"**Statistik Deskriptif (Keseluruhan & Per Bahasa)**")
            st.dataframe(_format_stats_table(stats_tbl), use_container_width=True, hide_index=True)

        CHART_METRICS = [
            ("geval_coherence_normalized", "G-Eval Normalized (0-1)"),
            ("educational_score", "Educational Score (1-5)"),
        ]
        LANG_COLS = [
            ("Keseluruhan", all_scores_all, tops_all),
            ("Bahasa Inggris", all_scores_en, tops_en),
            ("Bahasa Indonesia", all_scores_id, tops_id),
        ]

        for metric_col, metric_label in CHART_METRICS:
            st.markdown(f"**{metric_label}**")
            cols_chart = st.columns(3)
            
            bar_col_val = "#FF9800"  # Lighter Orange for bars
            kde_col_val = "#E65100"  # Darker Orange for KDE line

            for idx, (lang_label, pop_df, samp_df) in enumerate(LANG_COLS):
                n_pop = int(pop_df.shape[0]) if pop_df is not None and not pop_df.empty else 0
                n_samp = int(samp_df.shape[0]) if samp_df is not None and not samp_df.empty else 0
                chart_title = f"{metric_label} ({lang_label})"
                samp_label = f"Sampling (n={n_samp})"
                plot_df = pop_df if pop_df is not None and not pop_df.empty else pd.DataFrame()
                with cols_chart[idx]:
                    st.caption(f"N={n_pop}")
                    if plot_df.empty or metric_col not in plot_df.columns:
                        st.info("Data tidak tersedia.")
                    else:
                        st.altair_chart(
                            _coherence_dist_chart_notebook_style(
                                plot_df,
                                metric_col,
                                chart_title,
                                sample_df=samp_df,
                                sample_label=samp_label,
                                bar_color=bar_col_val,
                                kde_color=kde_col_val,
                            ),
                            use_container_width=True,
                        )
    else:
        st.info("Tidak ada dataframe jejak untuk statistik skor (CSV trace atau sampling gagal).")

    st.divider()

    baseline_raw = load_baseline_df()
    current_raw = load_current_df()

    baseline_df = None
    current_df = None
    if baseline_raw is not None:
        baseline_df = filter_by_language(add_language_col(baseline_raw), lang_key)
    if current_raw is not None:
        current_df = filter_by_language(add_language_col(current_raw), lang_key)

    # -----------------------------------------------------------------------
    # Section 1: G-Eval Analysis
    # -----------------------------------------------------------------------
    st.subheader("1. G-Eval — Kualitas Linguistik (DeepEval)")

    st.markdown("**5 Sub-Kriteria G-Eval:**")
    st.dataframe(_GEVAL_TABLE, use_container_width=True, hide_index=True)

    GEVAL_DIMS = [
        ("geval_avg_raw", "G-Eval Avg (1-5)"),
        ("geval_fluency", "Fluency"),
        ("geval_consistency", "Consistency"),
        ("geval_clarity", "Clarity"),
        ("geval_conciseness", "Conciseness"),
        ("geval_repetitiveness", "Repetitiveness"),
    ]

    if current_df is not None:
        # Summary metrics
        if "geval_avg_raw" in current_df.columns:
            series = current_df["geval_avg_raw"].dropna()
            col_a, col_b, col_c, col_d, col_e = st.columns(5)
            col_a.metric("Mean (1-5)", f"{series.mean():.3f}")
            col_b.metric("Std", f"{series.std():.3f}")
            col_c.metric("Min", f"{series.min():.2f}")
            col_d.metric("Max", f"{series.max():.2f}")
            col_e.metric("N Traces", len(series))

        # Distribution per dimension
        st.markdown("**Distribusi per Dimensi (Current / Agentic AI):**")
        avail_dims = [(col, lbl) for col, lbl in GEVAL_DIMS if col in (current_df.columns if current_df is not None else [])]
        if avail_dims and baseline_df is not None:
            for col, lbl in avail_dims:
                if col not in baseline_df.columns:
                    continue
                st.markdown(f"*{lbl}*")
                c1, c2 = st.columns(2)
                with c1:
                    st.altair_chart(
                        distribution_chart(
                            baseline_df[col], current_df[col], lbl,
                            x_min=1.0, x_max=5.0, bin_step=0.2,
                        ),
                        use_container_width=True,
                    )
                with c2:
                    st.altair_chart(
                        boxplot_chart(baseline_df[col], current_df[col], lbl, x_min=1.0, x_max=5.0),
                        use_container_width=True,
                    )
    else:
        st.warning("Data G-Eval tidak tersedia di Eval_Data/Traces/.")

    # G-Eval methodology
    with st.expander("Metodologi G-Eval (PRD)"):
        st.markdown("""
**Framework:** DeepEval G-Eval (Liu et al., 2023; arXiv:2303.16634)

| Parameter | Value |
|-----------|-------|
| Scale | 1–5 raw; 0–1 normalized |
| Sub-criteria | 5 (Fluency, Consistency, Clarity, Conciseness, Repetitiveness) |
| Execution | Parallel per sub-criterion via `asyncio.gather` |
| Timing | **Finalize only** — not during revision loop |
| Output | `geval_coherence` (avg 1–5), `geval_coherence_normalized` (avg 0–1), per-criterion scores |
| Routing impact | None — logging & thesis analysis only |

**Score normalization:** GEval scores are natively 0–1; raw 1–5 equivalent = `(score × 4) + 1`.
""")

    st.divider()

    # -----------------------------------------------------------------------
    # Section 2: Coherence Evaluator (LLM-based)
    # -----------------------------------------------------------------------
    st.subheader("2. LLM Coherence Evaluator — Event Horizon Model")

    st.markdown("**5 Kriteria Evaluasi Koherensi:**")
    st.dataframe(_COHERENCE_CRITERIA_TABLE, use_container_width=True, hide_index=True)

    if current_df is not None:
        root = repo_root()
        obs_dir = root / "Eval_Data" / "Observations"
        obs_rows = _load_coherence_from_observations(obs_dir)

        if obs_rows:
            obs_df = pd.DataFrame(obs_rows)
            _render_coherence_observations(obs_df)
        elif "geval_coherence_normalized" in current_df.columns:
            st.info(
                "Data observasi koherensi detail tidak ditemukan di Eval_Data/Observations/. "
                "Menampilkan G-Eval sebagai proxy koherensi."
            )
        else:
            st.warning("Data koherensi tidak tersedia.")

    with st.expander("Metodologi LLM Coherence Evaluator (PRD)"):
        st.markdown("""
**Framework:** LLM-as-a-Judge dengan structured output (`LLMCoherenceEvaluation`)

| Parameter | Value |
|-----------|-------|
| Model | Event Horizon Model (EHM) |
| Scale | 0.0–10.0 |
| Evaluation | 5 kriteria naratif: Fabula, Plot, Discourse, Long-term Causal, Knowledge Grounding |
| Issue types | severity: `critical` / `major` / `minor` |
| Timing | **Setiap iterasi** revision loop — mempengaruhi routing |
| Routing impact | `critical` atau `major` issue → paksa keputusan REVISE |
| Output | `coherence_score`, `issues[]`, `needs_revision`, `revision_reason`, `summary`, `strengths` |
""")

    st.divider()

    # -----------------------------------------------------------------------
    # Section 3: Baseline vs Agentic AI — Standardized Analysis
    # -----------------------------------------------------------------------
    st.subheader("3. Perbandingan Baseline vs Agentic AI")

    if baseline_df is None or current_df is None:
        st.warning(
            "Data perbandingan tidak tersedia. "
            "Pastikan Eval_Data/Baselines/Traces/ dan Eval_Data/Traces/ keduanya berisi CSV export."
        )
        return

    b_n = len(baseline_df)
    c_n = len(current_df)
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Baseline n", b_n)
    col_b.metric("Agentic AI n", c_n)
    col_c.metric("Filter", lang_key.upper() if lang_key != "all" else "Semua")

    if b_n < 5 or c_n < 5:
        st.warning("Data terlalu sedikit setelah filter. Pilih filter 'Semua'.")
        return

    # Distribution charts
    st.markdown("**A. Distribusi Skor G-Eval:**")
    COHERENCE_METRICS = [
        ("geval_avg_raw", "G-Eval Coherence — Avg Raw (1-5)", 1.0, 5.0, 0.2),
        ("geval_fluency", "Fluency (1-5)", 1.0, 5.0, 0.2),
        ("geval_consistency", "Consistency (1-5)", 1.0, 5.0, 0.2),
        ("geval_clarity", "Clarity (1-5)", 1.0, 5.0, 0.2),
        ("geval_conciseness", "Conciseness (1-5)", 1.0, 5.0, 0.2),
        ("geval_repetitiveness", "Repetitiveness (1-5)", 1.0, 5.0, 0.2),
    ]

    for col_name, label, x_min, x_max, bin_step in COHERENCE_METRICS:
        if col_name not in baseline_df.columns or col_name not in current_df.columns:
            continue
        if baseline_df[col_name].dropna().empty and current_df[col_name].dropna().empty:
            continue
        st.markdown(f"*{label}*")
        c1, c2 = st.columns(2)
        with c1:
            st.altair_chart(
                distribution_chart(baseline_df[col_name], current_df[col_name], label,
                                   x_min=x_min, x_max=x_max, bin_step=bin_step),
                use_container_width=True,
            )
        with c2:
            st.altair_chart(
                boxplot_chart(baseline_df[col_name], current_df[col_name], label,
                              x_min=x_min, x_max=x_max),
                use_container_width=True,
            )

    st.divider()

    # Significance tests
    st.markdown("**B. Uji Signifikansi Statistik (G-Eval per Dimensi):**")
    st.markdown(
        "**Mann-Whitney U test** (one-sided: Agentic AI > Baseline). "
        f"n Baseline = {b_n}, n Agentic AI = {c_n} "
        f"({'filter: ' + lang_key.upper() if lang_key != 'all' else 'semua bahasa'})."
    )
    from lib.analysis_utils import compute_combined_significance_coherence, render_combined_significance_coherence
    
    b_all_raw = add_language_col(load_baseline_df())
    c_all_raw = add_language_col(load_current_df())
    
    b_en = b_all_raw[b_all_raw["language"] == "en"] if "language" in b_all_raw.columns else pd.DataFrame()
    c_en = c_all_raw[c_all_raw["language"] == "en"] if "language" in c_all_raw.columns else pd.DataFrame()
    b_id = b_all_raw[b_all_raw["language"] == "id"] if "language" in b_all_raw.columns else pd.DataFrame()
    c_id = c_all_raw[c_all_raw["language"] == "id"] if "language" in c_all_raw.columns else pd.DataFrame()

    sig_rows = []
    for col_name, label, *_ in COHERENCE_METRICS:
        if col_name not in b_all_raw.columns or col_name not in c_all_raw.columns:
            continue
        # Use simpler base label for dimensions (e.g. "Conciseness" instead of "Conciseness (1-5)")
        clean_label = label.split(" (")[0]
        res = compute_combined_significance_coherence(
            b_all_raw[col_name], c_all_raw[col_name],
            b_en[col_name] if not b_en.empty else [], c_en[col_name] if not c_en.empty else [],
            b_id[col_name] if not b_id.empty else [], c_id[col_name] if not c_id.empty else [],
            col_name, clean_label
        )
        sig_rows.extend(res)
    render_combined_significance_coherence(sig_rows)

    st.divider()

    # Summary stats
    st.markdown("**C. Ringkasan Statistik Deskriptif:**")
    focus = [col for col, *_ in COHERENCE_METRICS if col in baseline_df.columns and col in current_df.columns]
    if focus:
        b_stats = summary_stats(baseline_df, focus).rename(
            columns={"Mean": "Baseline Mean", "Std": "Baseline Std", "N": "Baseline N"}
        )
        c_stats = summary_stats(current_df, focus).rename(
            columns={"Mean": "Current Mean", "Std": "Current Std", "N": "Current N"}
        )
        combined = b_stats[["Metric", "Baseline N", "Baseline Mean", "Baseline Std"]].merge(
            c_stats[["Metric", "Current N", "Current Mean", "Current Std"]],
            on="Metric", how="outer",
        )
        combined["Current Mean"] = pd.to_numeric(combined["Current Mean"], errors="coerce")
        combined["Baseline Mean"] = pd.to_numeric(combined["Baseline Mean"], errors="coerce")
        combined["Delta Mean"] = (combined["Current Mean"] - combined["Baseline Mean"]).round(4)
        combined["Delta Mean"] = combined["Delta Mean"].apply(lambda x: f"{x:+.3f}" if pd.notna(x) else "N/A")
        st.dataframe(combined, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Observation loader helper
# ---------------------------------------------------------------------------

def _load_coherence_from_observations(obs_dir: Path) -> list[dict]:
    """Load critic_coherence_eval_llm observations from JSONL files."""
    rows = []
    if not obs_dir.exists():
        return rows

    for jsonl_file in obs_dir.glob("*.jsonl"):
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("name") == "critic_coherence_eval_llm":
                        output = obj.get("output", {})
                        if isinstance(output, str):
                            try:
                                output = json.loads(output)
                            except Exception:
                                continue
                        score = output.get("coherence_score")
                        if score is not None:
                            rows.append({
                                "trace_id": obj.get("traceId", ""),
                                "coherence_score": float(score),
                                "needs_revision": output.get("needs_revision", False),
                                "issues_count": len(output.get("issues", [])),
                                "critical_count": sum(
                                    1 for i in output.get("issues", []) if i.get("severity") == "critical"
                                ),
                                "major_count": sum(
                                    1 for i in output.get("issues", []) if i.get("severity") == "major"
                                ),
                                "minor_count": sum(
                                    1 for i in output.get("issues", []) if i.get("severity") == "minor"
                                ),
                            })
        except Exception:
            continue
    return rows


def _render_coherence_observations(obs_df: pd.DataFrame) -> None:
    """Render coherence score charts from observation data."""
    col_a, col_b = st.columns([2, 1])

    with col_a:
        hist = (
            alt.Chart(obs_df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#6366f1")
            .encode(
                x=alt.X("coherence_score:Q", bin=alt.Bin(maxbins=10), title="Coherence Score (0–10)"),
                y=alt.Y("count():Q", title="Jumlah Observasi"),
                tooltip=[alt.Tooltip("coherence_score:Q", title="Score"), "count()"],
            )
            .properties(title="Distribusi Skor Koherensi LLM", height=280)
        )
        st.altair_chart(hist, use_container_width=True)

    with col_b:
        series = obs_df["coherence_score"]
        st.metric("Mean Score", f"{series.mean():.2f}/10")
        st.metric("Std", f"{series.std():.2f}")
        needs_rev = obs_df["needs_revision"].sum()
        st.metric("Needs Revision", f"{needs_rev}/{len(obs_df)}")

    # Issue severity breakdown
    if "critical_count" in obs_df.columns:
        st.markdown("**Distribusi Severity Issues:**")
        sev_df = pd.DataFrame({
            "Severity": ["Critical", "Major", "Minor"],
            "Count": [
                obs_df["critical_count"].sum(),
                obs_df["major_count"].sum(),
                obs_df["minor_count"].sum(),
            ],
        })
        sev_chart = (
            alt.Chart(sev_df)
            .mark_bar()
            .encode(
                x=alt.X("Severity:N", sort=["Critical", "Major", "Minor"]),
                y="Count:Q",
                color=alt.Color(
                    "Severity:N",
                    scale=alt.Scale(
                        domain=["Critical", "Major", "Minor"],
                        range=["#ef4444", "#f97316", "#eab308"],
                    ),
                    legend=None,
                ),
                tooltip=["Severity:N", "Count:Q"],
            )
            .properties(height=220)
        )
        st.altair_chart(sev_chart, use_container_width=True)
