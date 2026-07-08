"""
Metric Correlation Analysis tab for the Streamlit evaluation dashboard.

Analyzes inter-metric correlations between FABLES, RAGAS, and G-Eval
to understand how faithfulness and coherence evaluators relate to each other.
"""

from __future__ import annotations

from itertools import combinations

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats as scipy_stats

from lib.analysis_utils import add_language_col, filter_by_language, language_filter_widget
from lib.baseline_loader import load_baseline_df, load_current_df

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CORE_METRICS = [
    "fables_faithfulness",
    "ragas_standard_faithfulness",
    "geval_avg_raw",
]

GEVAL_SUBDIMS = [
    "geval_fluency",
    "geval_consistency",
    "geval_clarity",
    "geval_conciseness",
    "geval_repetitiveness",
]

CLAIM_COLS = [
    "fables_claims_total",
    "fables_claims_evaluated",
]

EXTENDED_METRICS = CORE_METRICS + ["educational_score"] + GEVAL_SUBDIMS + CLAIM_COLS

METRIC_DISPLAY = {
    "fables_faithfulness": "FABLES",
    "ragas_standard_faithfulness": "RAGAS",
    "geval_avg_raw": "G-Eval (avg)",
    "geval_fluency": "G-Eval Fluency",
    "geval_consistency": "G-Eval Consistency",
    "geval_clarity": "G-Eval Clarity",
    "geval_conciseness": "G-Eval Conciseness",
    "geval_repetitiveness": "G-Eval Repetitiveness",
    "educational_score": "Educational Score",
    "fables_claims_total": "Total Claims (RAGAS)",
    "fables_claims_evaluated": "Evaluated Claims (FABLES)",
}


# ---------------------------------------------------------------------------
# Filter widgets
# ---------------------------------------------------------------------------

def _system_filter_widget(key_suffix: str = "") -> str:
    """Render inline system filter radio. Returns 'all', 'baseline', or 'agentic'."""
    options = {"Semua": "all", "Baseline": "baseline", "Agentic AI": "agentic"}
    choice = st.radio(
        "Filter Sistem:",
        list(options.keys()),
        horizontal=True,
        key=f"sys_filter_{key_suffix}",
    )
    return options[choice]


def _filter_by_system(df: pd.DataFrame, sys_key: str) -> pd.DataFrame:
    """Filter combined DataFrame by source system."""
    if sys_key == "all" or "source" not in df.columns:
        return df
    if sys_key == "baseline":
        return df[df["source"] == "Baseline"].copy()
    if sys_key == "agentic":
        return df[df["source"] == "Agentic AI"].copy()
    return df


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _build_combined_df(
    baseline_df: pd.DataFrame | None,
    current_df: pd.DataFrame | None,
) -> pd.DataFrame | None:
    """Combine baseline and current DataFrames with a 'source' label column."""
    frames = []
    if baseline_df is not None and not baseline_df.empty:
        tmp = baseline_df.copy()
        tmp["source"] = "Baseline"
        frames.append(tmp)
    if current_df is not None and not current_df.empty:
        tmp = current_df.copy()
        tmp["source"] = "Agentic AI"
        frames.append(tmp)
    if not frames:
        return None
    combined = pd.concat(frames, ignore_index=True)
    for col in EXTENDED_METRICS:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce")
    return combined


def _available_metrics(df: pd.DataFrame) -> list[str]:
    """Return metric columns that exist and have non-null data."""
    return [
        c for c in EXTENDED_METRICS
        if c in df.columns and df[c].notna().sum() >= 3
    ]


# ---------------------------------------------------------------------------
# Correlation computation
# ---------------------------------------------------------------------------

def _compute_correlation_matrix(
    df: pd.DataFrame,
    metrics: list[str],
    method: str = "spearman",
) -> pd.DataFrame:
    """Compute correlation matrix for the given metrics."""
    sub = df[metrics].dropna()
    if sub.shape[0] < 3:
        return pd.DataFrame()
    return sub.corr(method=method).round(4)


def _compute_pairwise_stats(
    df: pd.DataFrame,
    metrics: list[str],
) -> list[dict]:
    """Compute Pearson and Spearman correlation with p-values for all pairs."""
    results = []
    for m1, m2 in combinations(metrics, 2):
        valid = df[[m1, m2]].dropna()
        n = len(valid)
        if n < 5:
            continue
        x, y = valid[m1].values, valid[m2].values

        r_pearson, p_pearson = scipy_stats.pearsonr(x, y)
        r_spearman, p_spearman = scipy_stats.spearmanr(x, y)

        results.append({
            "Metrik A": METRIC_DISPLAY.get(m1, m1),
            "Metrik B": METRIC_DISPLAY.get(m2, m2),
            "n": n,
            "Pearson r": round(float(r_pearson), 4),
            "Pearson p": float(p_pearson),
            "Spearman rho": round(float(r_spearman), 4),
            "Spearman p": float(p_spearman),
            "_col_a": m1,
            "_col_b": m2,
        })
    return results


def _interpret_correlation(r: float) -> str:
    """Interpret correlation coefficient magnitude."""
    abs_r = abs(r)
    if abs_r < 0.1:
        return "negligible"
    if abs_r < 0.3:
        return "weak"
    if abs_r < 0.5:
        return "moderate"
    if abs_r < 0.7:
        return "strong"
    return "very strong"


# ---------------------------------------------------------------------------
# Visualization helpers
# ---------------------------------------------------------------------------

def _heatmap_chart(corr_matrix: pd.DataFrame, title: str) -> alt.Chart:
    """Create a correlation heatmap from a correlation matrix DataFrame."""
    labels = [METRIC_DISPLAY.get(c, c) for c in corr_matrix.columns]
    label_map = dict(zip(corr_matrix.columns, labels))

    melted = corr_matrix.reset_index().melt(
        id_vars="index", var_name="col", value_name="r",
    )
    melted["row_label"] = melted["index"].map(label_map)
    melted["col_label"] = melted["col"].map(label_map)

    base = alt.Chart(melted).encode(
        x=alt.X("col_label:N", title=None, sort=labels,
                 axis=alt.Axis(labelAngle=-45, labelFontSize=11)),
        y=alt.Y("row_label:N", title=None, sort=labels,
                 axis=alt.Axis(labelFontSize=11)),
    )

    heatmap = base.mark_rect(stroke="white", strokeWidth=1).encode(
        color=alt.Color(
            "r:Q",
            scale=alt.Scale(domain=[-1, 1], scheme="redblue"),
            legend=alt.Legend(title="Korelasi"),
        ),
        tooltip=[
            alt.Tooltip("row_label:N", title="Baris"),
            alt.Tooltip("col_label:N", title="Kolom"),
            alt.Tooltip("r:Q", title="Korelasi", format=".4f"),
        ],
    )

    text = base.mark_text(fontSize=13, fontWeight="bold").encode(
        text=alt.Text("r:Q", format=".2f"),
        color=alt.condition(
            (alt.datum.r > 0.6) | (alt.datum.r < -0.6),
            alt.value("white"),
            alt.value("black"),
        ),
    )

    return (heatmap + text).properties(title=title, width=400, height=400)


def _scatter_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: str = "source",
) -> alt.Chart:
    """Create a scatter plot with regression trendline for two metrics."""
    x_label = METRIC_DISPLAY.get(x_col, x_col)
    y_label = METRIC_DISPLAY.get(y_col, y_col)

    sub = df[[x_col, y_col, color_col]].dropna()
    if sub.empty:
        return alt.Chart(pd.DataFrame()).mark_text(text="Tidak ada data").properties(height=300)

    points = (
        alt.Chart(sub)
        .mark_circle(size=60, opacity=0.6)
        .encode(
            x=alt.X(f"{x_col}:Q", title=x_label),
            y=alt.Y(f"{y_col}:Q", title=y_label),
            color=alt.Color(
                f"{color_col}:N",
                scale=alt.Scale(
                    domain=["Baseline", "Agentic AI"],
                    range=["#64748b", "#3b82f6"],
                ),
                legend=alt.Legend(title="Sistem"),
            ),
            tooltip=[
                alt.Tooltip(f"{color_col}:N", title="Sistem"),
                alt.Tooltip(f"{x_col}:Q", title=x_label, format=".4f"),
                alt.Tooltip(f"{y_col}:Q", title=y_label, format=".4f"),
            ],
        )
    )

    trendline = (
        alt.Chart(sub)
        .mark_line(color="#ef4444", strokeWidth=2, strokeDash=[6, 3])
        .transform_regression(x_col, y_col, method="linear")
        .encode(
            x=f"{x_col}:Q",
            y=f"{y_col}:Q",
        )
    )

    return (points + trendline).properties(
        title=f"{x_label} vs {y_label}",
        height=300,
    )


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_correlation_matrix_section(df: pd.DataFrame, metrics: list[str]) -> None:
    """Section A: Correlation matrix heatmaps."""
    st.subheader("A. Matriks Korelasi")
    st.caption(
        "Matriks korelasi Spearman (non-parametrik) antar metrik evaluasi. "
        "Warna merah = korelasi positif, biru = korelasi negatif."
    )

    core_avail = [m for m in CORE_METRICS if m in metrics]
    extended_avail = [m for m in metrics if m in EXTENDED_METRICS]

    if len(core_avail) < 2:
        st.warning("Minimal 2 metrik inti diperlukan untuk menghitung korelasi.")
        return

    col1, col2 = st.columns(2)
    with col1:
        corr_sp = _compute_correlation_matrix(df, core_avail, method="spearman")
        if not corr_sp.empty:
            st.altair_chart(
                _heatmap_chart(corr_sp, "Spearman (Metrik Inti)"),
                use_container_width=True,
            )

    with col2:
        corr_pe = _compute_correlation_matrix(df, core_avail, method="pearson")
        if not corr_pe.empty:
            st.altair_chart(
                _heatmap_chart(corr_pe, "Pearson (Metrik Inti)"),
                use_container_width=True,
            )

    # Extended heatmap with G-Eval sub-dimensions
    geval_in_data = [m for m in GEVAL_SUBDIMS if m in metrics]
    if geval_in_data:
        with st.expander("Matriks korelasi diperluas (termasuk sub-dimensi G-Eval)", expanded=False):
            corr_ext = _compute_correlation_matrix(df, extended_avail, method="spearman")
            if not corr_ext.empty:
                st.altair_chart(
                    _heatmap_chart(corr_ext, "Spearman (Semua Metrik)"),
                    use_container_width=True,
                )


def _render_scatter_section(df: pd.DataFrame, metrics: list[str]) -> None:
    """Section B: Pairwise scatter plots for the 3 core metrics."""
    st.subheader("B. Scatter Plot Pasangan Metrik")
    st.caption(
        "Scatter plot menampilkan hubungan antar pasangan metrik. "
        "Garis merah putus-putus = regresi linear. "
        "Setiap titik mewakili satu trace/cerita."
    )

    core_avail = [m for m in CORE_METRICS if m in metrics]
    pairs = list(combinations(core_avail, 2))

    if not pairs:
        st.info("Tidak cukup metrik inti untuk membuat scatter plot.")
        return

    n_cols = min(len(pairs), 3)
    cols = st.columns(n_cols)
    for idx, (m1, m2) in enumerate(pairs):
        with cols[idx % n_cols]:
            st.altair_chart(
                _scatter_chart(df, m1, m2),
                use_container_width=True,
            )


def _render_stats_table_section(df: pd.DataFrame, metrics: list[str]) -> None:
    """Section C: Statistical correlation table."""
    st.subheader("C. Tabel Korelasi Statistik")
    st.caption(
        "Pearson r mengukur korelasi linear; Spearman rho mengukur korelasi monoton (non-parametrik). "
        "p-value < 0.05 menunjukkan korelasi signifikan secara statistik."
    )

    pairwise = _compute_pairwise_stats(df, metrics)
    if not pairwise:
        st.info("Tidak cukup data untuk menghitung korelasi statistik.")
        return

    stats_df = pd.DataFrame(pairwise)

    display_df = stats_df.drop(columns=["_col_a", "_col_b"]).copy()
    display_df["Pearson p"] = display_df["Pearson p"].map(lambda x: f"{x:.4f}")
    display_df["Spearman p"] = display_df["Spearman p"].map(lambda x: f"{x:.4f}")
    display_df["Interpretasi"] = stats_df["Spearman rho"].map(_interpret_correlation)

    def _row_style(row: pd.Series):
        rho = float(stats_df.iloc[row.name]["Spearman rho"])
        if abs(rho) >= 0.5:
            return ["background-color: rgba(34, 197, 94, 0.1)"] * len(row)
        if abs(rho) >= 0.3:
            return ["background-color: rgba(234, 179, 8, 0.1)"] * len(row)
        return ["background-color: rgba(239, 68, 68, 0.08)"] * len(row)

    st.dataframe(
        display_df.style.apply(_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )


def _render_per_system_section(
    baseline_df: pd.DataFrame | None,
    current_df: pd.DataFrame | None,
    metrics: list[str],
) -> None:
    """Section D: Compare correlation patterns between Baseline and Agentic AI."""
    st.subheader("D. Perbandingan Pola Korelasi per Sistem")
    st.caption(
        "Apakah hubungan antar metrik berubah antara sistem Baseline dan Agentic AI? "
        "Perbedaan pola korelasi mengindikasikan bahwa agentic loop mengubah dinamika antar metrik."
    )

    core_avail_base = (
        [m for m in CORE_METRICS if m in metrics and m in baseline_df.columns]
        if baseline_df is not None else []
    )
    core_avail_curr = (
        [m for m in CORE_METRICS if m in metrics and m in current_df.columns]
        if current_df is not None else []
    )
    common = sorted(set(core_avail_base) & set(core_avail_curr))

    if len(common) < 2:
        st.info("Tidak cukup metrik bersama untuk perbandingan per sistem.")
        return

    rows = []
    for m1, m2 in combinations(common, 2):
        label_a = METRIC_DISPLAY.get(m1, m1)
        label_b = METRIC_DISPLAY.get(m2, m2)
        pair_label = f"{label_a} vs {label_b}"

        for df_src, sys_name in [(baseline_df, "Baseline"), (current_df, "Agentic AI")]:
            if df_src is None:
                continue
            valid = df_src[[m1, m2]].dropna()
            if len(valid) < 5:
                continue
            rho, p_val = scipy_stats.spearmanr(valid[m1], valid[m2])
            rows.append({
                "Pasangan": pair_label,
                "Sistem": sys_name,
                "n": len(valid),
                "Spearman rho": round(float(rho), 4),
                "p-value": f"{float(p_val):.4f}",
                "Interpretasi": _interpret_correlation(rho),
            })

    if not rows:
        st.info("Tidak cukup data per sistem.")
        return

    comp_df = pd.DataFrame(rows)
    st.dataframe(comp_df, use_container_width=True, hide_index=True)


def _render_geval_subdim_section(df: pd.DataFrame, metrics: list[str]) -> None:
    """Section E: How G-Eval sub-dimensions correlate with faithfulness metrics."""
    st.subheader("E. Korelasi Sub-Dimensi G-Eval dengan Metrik Faithfulness")
    st.caption(
        "Masing-masing sub-dimensi G-Eval (Fluency, Consistency, Clarity, Conciseness, Repetitiveness) "
        "mungkin memiliki hubungan yang berbeda dengan skor faithfulness FABLES dan RAGAS."
    )

    faith_cols = [m for m in ["fables_faithfulness", "ragas_standard_faithfulness"] if m in metrics]
    geval_cols = [m for m in GEVAL_SUBDIMS if m in metrics]

    if not faith_cols or not geval_cols:
        st.info("Sub-dimensi G-Eval atau metrik faithfulness tidak tersedia.")
        return

    rows = []
    for fc in faith_cols:
        for gc in geval_cols:
            valid = df[[fc, gc]].dropna()
            if len(valid) < 5:
                continue
            rho, p_val = scipy_stats.spearmanr(valid[fc], valid[gc])
            rows.append({
                "Faithfulness Metric": METRIC_DISPLAY.get(fc, fc),
                "G-Eval Dimension": METRIC_DISPLAY.get(gc, gc),
                "n": len(valid),
                "Spearman rho": round(float(rho), 4),
                "p-value": f"{float(p_val):.4f}",
                "Interpretasi": _interpret_correlation(rho),
            })

    if not rows:
        st.info("Tidak cukup data untuk korelasi sub-dimensi.")
        return

    subdim_df = pd.DataFrame(rows)

    def _color_row(row: pd.Series):
        rho = row["Spearman rho"]
        if abs(rho) >= 0.5:
            return ["background-color: rgba(34, 197, 94, 0.1)"] * len(row)
        if abs(rho) >= 0.3:
            return ["background-color: rgba(234, 179, 8, 0.1)"] * len(row)
        return [""] * len(row)

    st.dataframe(
        subdim_df.style.apply(_color_row, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # Bar chart of Spearman rho per dimension
    chart_df = subdim_df.copy()
    chart_df["abs_rho"] = chart_df["Spearman rho"].abs()

    bar = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("Spearman rho:Q", title="Spearman rho",
                     scale=alt.Scale(domain=[-1, 1])),
            y=alt.Y("G-Eval Dimension:N", title=None, sort="-x"),
            color=alt.Color(
                "Faithfulness Metric:N",
                scale=alt.Scale(
                    domain=[METRIC_DISPLAY.get(c, c) for c in faith_cols],
                    range=["#8b5cf6", "#f97316"],
                ),
            ),
            tooltip=[
                "Faithfulness Metric:N",
                "G-Eval Dimension:N",
                alt.Tooltip("Spearman rho:Q", format=".4f"),
            ],
        )
        .properties(
            title="Korelasi Sub-Dimensi G-Eval terhadap Faithfulness",
            height=250,
        )
    )
    st.altair_chart(bar, use_container_width=True)


def _render_educational_section(df: pd.DataFrame, metrics: list[str]) -> None:
    """Section F: Educational Score correlations with all other metrics."""
    st.subheader("F. Korelasi Educational Score dengan Metrik Lainnya")
    st.caption(
        "Educational Score (1-5) mengukur kualitas pedagogis cerita. "
        "Bagaimana hubungannya dengan faithfulness (FABLES/RAGAS) dan koherensi (G-Eval)?"
    )

    edu_col = "educational_score"
    if edu_col not in metrics:
        st.info("Educational Score tidak tersedia dalam data.")
        return

    target_cols = [
        m for m in metrics
        if m != edu_col and m in df.columns
    ]
    if not target_cols:
        st.info("Tidak ada metrik lain untuk dikorelasikan dengan Educational Score.")
        return

    # Correlation table
    rows = []
    for tc in target_cols:
        valid = df[[edu_col, tc]].dropna()
        if len(valid) < 5:
            continue
        rho, p_val = scipy_stats.spearmanr(valid[edu_col], valid[tc])
        r_pe, p_pe = scipy_stats.pearsonr(valid[edu_col], valid[tc])
        rows.append({
            "Metrik": METRIC_DISPLAY.get(tc, tc),
            "n": len(valid),
            "Spearman rho": round(float(rho), 4),
            "Spearman p": f"{float(p_val):.4f}",
            "Pearson r": round(float(r_pe), 4),
            "Pearson p": f"{float(p_pe):.4f}",
            "Interpretasi": _interpret_correlation(rho),
            "_rho": float(rho),
        })

    if not rows:
        st.info("Tidak cukup data untuk korelasi Educational Score.")
        return

    edu_df = pd.DataFrame(rows)

    def _color_edu(row: pd.Series):
        rho = edu_df.iloc[row.name]["_rho"]
        if abs(rho) >= 0.5:
            return ["background-color: rgba(34, 197, 94, 0.1)"] * len(row)
        if abs(rho) >= 0.3:
            return ["background-color: rgba(234, 179, 8, 0.1)"] * len(row)
        return [""] * len(row)

    display_edu = edu_df.drop(columns=["_rho"])
    st.dataframe(
        display_edu.style.apply(_color_edu, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # Scatter plots: Educational vs core metrics
    core_targets = [m for m in CORE_METRICS if m in target_cols]
    if core_targets:
        cols = st.columns(min(len(core_targets), 3))
        for idx, tc in enumerate(core_targets):
            with cols[idx % len(cols)]:
                st.altair_chart(
                    _scatter_chart(df, edu_col, tc),
                    use_container_width=True,
                )

    # Bar chart
    bar_df = edu_df[["Metrik", "_rho"]].rename(columns={"_rho": "Spearman rho"})
    bar = (
        alt.Chart(bar_df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("Spearman rho:Q", scale=alt.Scale(domain=[-1, 1])),
            y=alt.Y("Metrik:N", title=None, sort="-x"),
            color=alt.condition(
                alt.datum["Spearman rho"] > 0,
                alt.value("#22c55e"),
                alt.value("#ef4444"),
            ),
            tooltip=["Metrik:N", alt.Tooltip("Spearman rho:Q", format=".4f")],
        )
        .properties(title="Korelasi Educational Score vs Metrik Lainnya", height=250)
    )
    st.altair_chart(bar, use_container_width=True)

    # Interpretation
    st.markdown(
        "**Catatan:** Educational Score diukur oleh evaluator internal (LLM-as-a-Judge, 5 dimensi pedagogis). "
        "Korelasi negatif dengan RAGAS mengindikasikan bahwa cerita dengan kualitas edukatif tinggi "
        "tidak selalu memiliki faithfulness tinggi secara strict (trade-off kreativitas vs faktualitas)."
    )


def _render_claims_correlation_section(df: pd.DataFrame, metrics: list[str]) -> None:
    """Section G: How claim counts correlate with G-Eval and Educational Score."""
    st.subheader("G. Korelasi Jumlah Klaim dengan Kualitas Cerita")
    st.caption(
        "Apakah cerita yang menghasilkan lebih banyak fakta/klaim (lebih detail) cenderung "
        "memiliki skor G-Eval atau Educational Score yang berbeda? "
        "RAGAS menggunakan Total Claims, sedangkan FABLES menggunakan Evaluated Claims."
    )

    claims_avail = [c for c in CLAIM_COLS if c in metrics]
    targets = [m for m in [
        "fables_faithfulness",
        "ragas_standard_faithfulness",
        "geval_avg_raw",
        "educational_score"
    ] if m in metrics]

    if not claims_avail or not targets:
        st.info("Data jumlah klaim atau metrik target (Faithfulness/G-Eval/Edu) tidak tersedia.")
        return

    rows = []
    for cc in claims_avail:
        for tc in targets:
            valid = df[[cc, tc]].dropna()
            if len(valid) < 5:
                continue
            rho, p_val = scipy_stats.spearmanr(valid[cc], valid[tc])
            rows.append({
                "Metrik Klaim": METRIC_DISPLAY.get(cc, cc),
                "Target": METRIC_DISPLAY.get(tc, tc),
                "n": len(valid),
                "Spearman rho": round(float(rho), 4),
                "p-value": f"{float(p_val):.4f}",
                "Interpretasi": _interpret_correlation(rho),
                "_rho": float(rho),
            })

    if not rows:
        st.info("Tidak cukup data untuk korelasi jumlah klaim.")
        return

    claims_df = pd.DataFrame(rows)

    def _color_claims(row: pd.Series):
        rho = claims_df.iloc[row.name]["_rho"]
        if abs(rho) >= 0.5:
            return ["background-color: rgba(34, 197, 94, 0.1)"] * len(row)
        if abs(rho) >= 0.3:
            return ["background-color: rgba(234, 179, 8, 0.1)"] * len(row)
        return [""] * len(row)

    display_claims = claims_df.drop(columns=["_rho"])
    st.dataframe(
        display_claims.style.apply(_color_claims, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # Scatter plots
    cols = st.columns(min(len(claims_avail) * len(targets), 4))
    idx = 0
    for cc in claims_avail:
        for tc in targets:
            with cols[idx % len(cols)]:
                st.altair_chart(
                    _scatter_chart(df, cc, tc),
                    use_container_width=True,
                )
            idx += 1


def _render_interpretation_section(df: pd.DataFrame, metrics: list[str]) -> None:
    """Section H: Auto-generated interpretation of findings."""
    st.subheader("H. Interpretasi Temuan")

    core_avail = [m for m in CORE_METRICS if m in metrics]
    pairwise = _compute_pairwise_stats(df, core_avail)

    if not pairwise:
        st.info("Tidak cukup data untuk menghasilkan interpretasi.")
        return

    for row in pairwise:
        rho = row["Spearman rho"]
        p = row["Spearman p"]
        interp = _interpret_correlation(rho)
        direction = "positif" if rho > 0 else "negatif"
        sig = "signifikan (p < 0.05)" if p < 0.05 else "tidak signifikan (p >= 0.05)"

        icon = "+" if rho > 0 else "-"
        if abs(rho) >= 0.5:
            marker = "[KUAT]"
        elif abs(rho) >= 0.3:
            marker = "[MODERAT]"
        else:
            marker = "[LEMAH]"

        st.markdown(
            f"**{marker} {row['Metrik A']} vs {row['Metrik B']}**: "
            f"Korelasi {direction} {interp} (rho = {rho:.4f}, {sig}). "
        )

    st.divider()
    st.markdown(
        "**Catatan Metodologis:**\n"
        "- FABLES dan RAGAS sama-sama mengukur *faithfulness* tetapi dengan pendekatan berbeda "
        "(claim-level verification vs statement-level scoring), sehingga korelasi tinggi mengindikasikan "
        "konsistensi evaluasi.\n"
        "- G-Eval mengukur *koherensi naratif* (dimensi berbeda dari faithfulness), "
        "sehingga korelasi moderat atau lemah dengan FABLES/RAGAS adalah wajar dan menunjukkan "
        "bahwa kedua aspek (faithfulness vs coherence) bersifat komplementer.\n"
        "- Korelasi tinggi antara faithfulness dan coherence justru perlu diwaspadai "
        "karena bisa mengindikasikan *confounding* (misal, cerita pendek mendapat skor tinggi di keduanya)."
    )


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_correlation_tab() -> None:
    """Render the full metric correlation analysis tab."""
    st.header("Analisis Korelasi Antar Metrik")
    st.markdown(
        "Analisis hubungan antar metrik evaluasi **FABLES**, **RAGAS**, dan **G-Eval** "
        "untuk memahami apakah metrik-metrik tersebut mengukur konstruk yang sama, "
        "saling melengkapi, atau independen satu sama lain."
    )

    baseline_raw = load_baseline_df()
    current_raw = load_current_df()

    if baseline_raw is not None:
        baseline_raw = add_language_col(baseline_raw)
    if current_raw is not None:
        current_raw = add_language_col(current_raw)

    combined = _build_combined_df(baseline_raw, current_raw)
    if combined is None or combined.empty:
        st.warning(
            "Data trace tidak ditemukan. Pastikan CSV export tersedia di "
            "Eval_Data/Baselines/Traces/ dan Eval_Data/Agentic-AI-LightRAG/Traces/."
        )
        return

    # Filters: language + system
    fc1, fc2 = st.columns(2)
    with fc1:
        lang_key = language_filter_widget(key_suffix="correlation")
    with fc2:
        sys_key = _system_filter_widget(key_suffix="correlation")

    # Apply language filter first on the combined df
    combined = filter_by_language(combined, lang_key)

    # Keep per-system copies before system filter (for section D)
    baseline_lang = filter_by_language(baseline_raw, lang_key) if baseline_raw is not None else None
    current_lang = filter_by_language(current_raw, lang_key) if current_raw is not None else None

    # Apply system filter
    combined = _filter_by_system(combined, sys_key)

    n_total = len(combined)
    n_base = len(combined[combined["source"] == "Baseline"]) if "source" in combined.columns else 0
    n_agent = len(combined[combined["source"] == "Agentic AI"]) if "source" in combined.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Traces", n_total)
    c2.metric("Baseline", n_base)
    c3.metric("Agentic AI", n_agent)

    metrics = _available_metrics(combined)
    if len(metrics) < 2:
        st.warning("Minimal 2 metrik dengan data non-null diperlukan.")
        return

    st.divider()

    _render_correlation_matrix_section(combined, metrics)
    st.divider()

    _render_scatter_section(combined, metrics)
    st.divider()

    _render_stats_table_section(combined, metrics)
    st.divider()

    _render_per_system_section(baseline_lang, current_lang, metrics)
    st.divider()

    _render_geval_subdim_section(combined, metrics)
    st.divider()

    _render_educational_section(combined, metrics)
    st.divider()

    _render_claims_correlation_section(combined, metrics)
    st.divider()

    _render_interpretation_section(combined, metrics)
