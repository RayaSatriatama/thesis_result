"""
Shared analysis utilities for Streamlit evaluation tabs.

Provides:
- Language detection from input text
- Language filter widget (sidebar or inline)
- Distribution chart (histogram + boxplot)
- Significance test computation
- Standardized summary stats display

Both faithfulness and coherence tabs use these to ensure consistent analysis.
"""

from __future__ import annotations

from typing import Optional

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats as scipy_stats

# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------

def detect_language(input_series: pd.Series) -> pd.Series:
    """Detect 'en' or 'id' from input prompt prefix or JSON content."""
    import re
    s = input_series.astype(str).str.strip('"').str.strip()

    def _detect_one(x: str) -> str:
        # Standard prefixes
        if x.startswith("Create"):
            return "en"
        if x.startswith("Buat"):
            return "id"
        
        # Lowercase for search
        x_low = x.lower()
        
        # Regex search for "language":"en" or "language": "english" etc.
        # Handles escaped quotes and varying spaces
        match_en = re.search(r'language["\\]+:\s*["\\]+(en|english)', x_low)
        if match_en:
            return "en"
            
        match_id = re.search(r'language["\\]+:\s*["\\]+(id|indonesian)', x_low)
        if match_id:
            return "id"
        
        # Fallback to keywords
        if "create an educational story" in x_low:
            return "en"
        if "buat cerita edukasi" in x_low:
            return "id"
            
        return "unknown"

    return s.apply(_detect_one)


def add_language_col(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with 'language' column added if not present."""
    out = df.copy()
    if "language" not in out.columns and "input" in out.columns:
        out["language"] = detect_language(out["input"])
    return out


def filter_by_language(df: pd.DataFrame, lang_key: str) -> pd.DataFrame:
    """Filter DataFrame by language. lang_key in {'en', 'id', 'all'}."""
    if lang_key == "all" or "language" not in df.columns:
        return df
    return df[df["language"] == lang_key].copy()


def language_filter_widget(key_suffix: str = "") -> str:
    """Render an inline language filter radio button. Returns 'all', 'en', or 'id'."""
    options = {"Semua": "all", "English (EN)": "en", "Indonesian (ID)": "id"}
    choice = st.radio(
        "Filter Bahasa:",
        list(options.keys()),
        horizontal=True,
        key=f"lang_filter_{key_suffix}",
    )
    return options[choice]


# ---------------------------------------------------------------------------
# Distribution chart (histogram + mean line)
# ---------------------------------------------------------------------------

def distribution_chart(
    baseline_series: pd.Series,
    current_series: pd.Series,
    metric_label: str,
    *,
    x_min: float = 0.0,
    x_max: Optional[float] = None,
    bin_step: float = 0.05,
) -> alt.Chart:
    """Overlaid histogram of baseline vs current distribution for one metric."""
    b_clean = pd.to_numeric(baseline_series, errors="coerce").dropna()
    c_clean = pd.to_numeric(current_series, errors="coerce").dropna()

    rows = (
        [{"Source": "Baseline", "Score": float(v)} for v in b_clean]
        + [{"Source": "Agentic AI (Current)", "Score": float(v)} for v in c_clean]
    )
    if not rows:
        return alt.Chart(pd.DataFrame()).mark_text(text="Tidak ada data").properties(height=240)

    plot_df = pd.DataFrame(rows)
    x_max_val = x_max if x_max is not None else float(plot_df["Score"].max())

    chart = (
        alt.Chart(plot_df)
        .mark_bar(opacity=0.6, binSpacing=1)
        .encode(
            x=alt.X(
                "Score:Q",
                bin=alt.Bin(step=bin_step),
                scale=alt.Scale(domain=[x_min, x_max_val]),
                title=metric_label,
            ),
            y=alt.Y("count():Q", title="Jumlah Trace", stack=None),
            color=alt.Color(
                "Source:N",
                scale=alt.Scale(
                    domain=["Baseline", "Agentic AI (Current)"],
                    range=["#64748b", "#3b82f6"],
                ),
                legend=alt.Legend(title="Sumber Data"),
            ),
            tooltip=["Source:N", alt.Tooltip("Score:Q", bin=alt.Bin(step=bin_step)), "count():Q"],
        )
        .properties(title=f"Distribusi {metric_label}", height=240)
    )

    # Mean lines
    means = plot_df.groupby("Source")["Score"].mean().reset_index()
    means.columns = ["Source", "Mean"]
    mean_lines = (
        alt.Chart(means)
        .mark_rule(strokeDash=[6, 3], strokeWidth=2)
        .encode(
            x="Mean:Q",
            color=alt.Color("Source:N", scale=alt.Scale(
                domain=["Baseline", "Agentic AI (Current)"],
                range=["#64748b", "#3b82f6"],
            )),
            tooltip=["Source:N", alt.Tooltip("Mean:Q", format=".4f", title="Mean")],
        )
    )
    return (chart + mean_lines).resolve_scale(color="shared")


def boxplot_chart(
    baseline_series: pd.Series,
    current_series: pd.Series,
    metric_label: str,
    *,
    x_min: float = 0.0,
    x_max: Optional[float] = None,
) -> alt.Chart:
    """Side-by-side boxplot of baseline vs current."""
    b_clean = pd.to_numeric(baseline_series, errors="coerce").dropna()
    c_clean = pd.to_numeric(current_series, errors="coerce").dropna()

    rows = (
        [{"Source": "Baseline", "Score": float(v)} for v in b_clean]
        + [{"Source": "Agentic AI (Current)", "Score": float(v)} for v in c_clean]
    )
    if not rows:
        return alt.Chart(pd.DataFrame()).mark_text(text="Tidak ada data").properties(height=200)

    plot_df = pd.DataFrame(rows)
    x_max_val = x_max if x_max is not None else float(plot_df["Score"].max())

    return (
        alt.Chart(plot_df)
        .mark_boxplot(size=40, median=alt.MarkConfig(color="white", strokeWidth=2))
        .encode(
            x=alt.X("Source:N", title=None),
            y=alt.Y(
                "Score:Q",
                scale=alt.Scale(domain=[x_min, x_max_val]),
                title=metric_label,
            ),
            color=alt.Color(
                "Source:N",
                scale=alt.Scale(
                    domain=["Baseline", "Agentic AI (Current)"],
                    range=["#64748b", "#3b82f6"],
                ),
                legend=None,
            ),
            tooltip=["Source:N", alt.Tooltip("Score:Q", format=".4f")],
        )
        .properties(title=f"Boxplot {metric_label}", height=240)
    )


# ---------------------------------------------------------------------------
# Significance test
# ---------------------------------------------------------------------------

def compute_significance(
    baseline_series: pd.Series,
    current_series: pd.Series,
    label: str,
) -> dict:
    """Run Mann-Whitney U (one-sided) and compute Cohen's d. Returns a result dict."""
    bv = pd.to_numeric(baseline_series, errors="coerce").dropna().values
    cv = pd.to_numeric(current_series, errors="coerce").dropna().values

    if len(bv) < 5 or len(cv) < 5:
        return {}

    _, p_mw = scipy_stats.mannwhitneyu(cv, bv, alternative="greater")
    pooled_std = float(np.sqrt((np.std(bv) ** 2 + np.std(cv) ** 2) / 2))
    d = (float(np.mean(cv)) - float(np.mean(bv))) / pooled_std if pooled_std > 0 else 0.0
    delta = float(np.mean(cv)) - float(np.mean(bv))
    delta_pct = delta / float(np.mean(bv)) * 100 if float(np.mean(bv)) != 0 else 0.0

    if p_mw < 0.001:
        sig_label = "*** (p<0.001)"
    elif p_mw < 0.01:
        sig_label = "** (p<0.01)"
    elif p_mw < 0.05:
        sig_label = "* (p<0.05)"
    else:
        sig_label = "ns"

    d_abs = abs(d)
    if d_abs < 0.2:
        d_label = "negligible"
    elif d_abs < 0.5:
        d_label = "small"
    elif d_abs < 0.8:
        d_label = "medium"
    else:
        d_label = "large"

    return {
        "Metrik": label,
        "Baseline n": int(len(bv)),
        "Baseline Mean ± Std": f"{np.mean(bv):.4f} ± {np.std(bv):.4f}",
        "Current n": int(len(cv)),
        "Current Mean ± Std": f"{np.mean(cv):.4f} ± {np.std(cv):.4f}",
        "Delta": f"{delta:+.4f} ({delta_pct:+.1f}%)",
        "p-value": f"{p_mw:.4f}",
        "Signifikansi": sig_label,
        "Cohen's d": f"{d:.3f} ({d_label})",
        "_p": float(p_mw),
    }


def render_significance_table(sig_rows: list[dict]) -> None:
    """Render a color-coded significance table + interpretation callouts."""
    if not sig_rows:
        st.info("Tidak cukup data untuk uji signifikansi.")
        return

    sig_df = pd.DataFrame(sig_rows)
    display_df = sig_df.drop(columns=["_p"])

    def _row_style(row: pd.Series):
        p = sig_df.at[row.name, "_p"]
        if p < 0.001:
            return ["background-color: #dcfce7"] * len(row)
        elif p < 0.05:
            return ["background-color: #fef9c3"] * len(row)
        else:
            return ["background-color: #fee2e2"] * len(row)

    st.dataframe(
        display_df.style.apply(_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    for row in sig_rows:
        p = row["_p"]
        cohensd = row["Cohen's d"]
        icon = "✅" if p < 0.05 else "❌"
        if p < 0.001:
            verdict = (
                f"{icon} **{row['Metrik']}**: Peningkatan **sangat signifikan** "
                f"({row['Signifikansi']}), effect size {cohensd}."
            )
        elif p < 0.05:
            verdict = (
                f"{icon} **{row['Metrik']}**: Peningkatan **signifikan** "
                f"({row['Signifikansi']}), effect size {cohensd}."
            )
        else:
            verdict = (
                f"{icon} **{row['Metrik']}**: Peningkatan **tidak signifikan** "
                f"({row['Signifikansi']}). Delta mungkin disebabkan variasi sampling."
            )
        st.markdown(verdict)
