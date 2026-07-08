"""Faithfulness evaluation tab (FABLES / RAGAS, confusion matrix, HTML claims)."""

from __future__ import annotations

import glob
import os

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from lib.faithfulness_metrics import (
    filter_all_traces_by_language,
    filter_tops_by_language,
    load_metrics_or_fallback,
    load_all_traces_df,
    load_ten_story_traces_df,
    load_trace_claims,
)
from lib.paths import images_faithfulness_dir


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _filter_html_paths(paths: list[str], lang_key: str) -> list[str]:
    if lang_key == "id":
        return [p for p in paths if "_ID_" in os.path.basename(p)]
    if lang_key == "en":
        return [p for p in paths if "_EN_" in os.path.basename(p)]
    return paths


def _ensure_faithfulness_avg(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    ms1, ms2 = "ragas_standard_faithfulness", "fables_faithfulness"
    if ms1 not in out.columns or ms2 not in out.columns:
        return out
    if "faithfulness_avg" not in out.columns:
        out["faithfulness_avg"] = (pd.to_numeric(out[ms1], errors="coerce") + pd.to_numeric(out[ms2], errors="coerce")) / 2.0
    return out


def _describe_faithfulness_scores(df: pd.DataFrame) -> pd.DataFrame | None:
    cols = {
        "ragas_standard_faithfulness": "RAGAS Standard Faithfulness",
        "fables_faithfulness": "FABLES Faithfulness",
    }
    rows = []
    for c, label in cols.items():
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append(
            {
                "Metrik": label,
                "n": int(s.count()),
                "Mean": float(s.mean()),
                "Median": float(s.median()),
                "Std": float(s.std(ddof=0)) if s.count() > 1 else 0.0,
                "Min": float(s.min()),
                "Q25": float(s.quantile(0.25)),
                "Q75": float(s.quantile(0.75)),
                "Max": float(s.max()),
            }
        )
    if not rows:
        return None
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def _claim_label_counts_all_traces(lang_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aggregate claim verdict counts (4-label) for ALL traces in the latest export.

    Returns:
    - per_trace_df: one row per trace (story), with counts per verdict label
    - totals_df: totals by language + overall
    """
    labels = ["FAITHFUL", "UNFAITHFUL", "PARTIAL_SUPPORT", "CANT_VERIFY"]

    df_all = filter_all_traces_by_language(load_all_traces_df(), lang_key)
    if df_all is None or df_all.empty:
        return pd.DataFrame(), pd.DataFrame()

    trace_ids = [str(x).strip().strip('"') for x in df_all["id"].tolist()]
    claim_map = load_trace_claims(trace_ids)

    rows: list[dict[str, object]] = []
    for _, r in df_all.iterrows():
        tid = str(r.get("id", "")).strip().strip('"')
        if not tid:
            continue
        verdicts = claim_map.get(tid, []) or []
        cnt = {k: 0 for k in labels}
        unknown = 0
        for v in verdicts:
            raw = (v.get("verdict") if isinstance(v, dict) else None) or ""
            key = str(raw).strip().upper()
            if key in cnt:
                cnt[key] += 1
            else:
                unknown += 1
        total = int(sum(cnt.values()) + unknown)

        # language is inferred by prompt convention used in sampling helpers
        inp = str(r.get("input", ""))
        lang = "en" if "Create an" in inp else ("id" if "Buat cerita" in inp else "")

        rows.append(
            {
                "trace_id": tid,
                "language": lang or str(r.get("language", "") or ""),
                "draft_title": str(r.get("draft_title", "") or ""),
                "total_claims": total,
                "FAITHFUL": int(cnt["FAITHFUL"]),
                "UNFAITHFUL": int(cnt["UNFAITHFUL"]),
                "PARTIAL_SUPPORT": int(cnt["PARTIAL_SUPPORT"]),
                "CANT_VERIFY": int(cnt["CANT_VERIFY"]),
                "UNKNOWN": int(unknown),
            }
        )

    per_trace = pd.DataFrame(rows)
    if per_trace.empty:
        return per_trace, pd.DataFrame()

    def _tot(scope: str, df: pd.DataFrame) -> dict[str, object]:
        return {
            "scope": scope,
            "total_claims": int(df["total_claims"].sum()),
            "FAITHFUL": int(df["FAITHFUL"].sum()),
            "UNFAITHFUL": int(df["UNFAITHFUL"].sum()),
            "PARTIAL_SUPPORT": int(df["PARTIAL_SUPPORT"].sum()),
            "CANT_VERIFY": int(df["CANT_VERIFY"].sum()),
            "UNKNOWN": int(df["UNKNOWN"].sum()),
            "n_traces": int(df.shape[0]),
        }

    totals_rows = []
    totals_rows.append(_tot("en", per_trace[per_trace["language"] == "en"]))
    totals_rows.append(_tot("id", per_trace[per_trace["language"] == "id"]))
    totals_rows.append(_tot("all", per_trace))
    totals = pd.DataFrame(totals_rows)
    return per_trace, totals


def _format_stats_table(t: pd.DataFrame) -> pd.DataFrame:
    disp = t.copy()
    for col in ("Mean", "Median", "Std", "Min", "Q25", "Q75", "Max"):
        if col in disp.columns:
            disp[col] = disp[col].map(lambda x: f"{x:.4f}")
    return disp


def _faithfulness_dist_chart_notebook_style(
    df: pd.DataFrame,
    col: str,
    title: str,
    *,
    sample_df: pd.DataFrame | None = None,
    sample_label: str = "Sampling",
    bar_color: str = "#9932CC",
    kde_color: str = "#4a148c",
    max_bins: int = 12,
) -> alt.Chart:
    """
    Histogram + KDE distribution chart, selaras notebooks/02_analisis_evaluasi_model.ipynb.
    Menampilkan legenda marker (min/mean/max) yang jelas.
    Sumbu X diatur otomatis agar tidak padat.
    """
    sub = df[[col]].copy()
    sub[col] = pd.to_numeric(sub[col], errors="coerce")
    sub = sub.dropna(subset=[col])
    if sub.empty:
        return (
            alt.Chart(pd.DataFrame({col: [0]}))
            .mark_text(text="Tidak ada data", fontSize=14, color="#555555")
            .properties(height=300, title=title)
        )

    vmin = float(sub[col].min())
    vmax = float(sub[col].max())
    span = vmax - vmin
    pad = max(span * 0.08, 0.02) if span > 0 else 0.05
    extent_lo = max(0.0, vmin - pad) if vmax <= 1.0 + 1e-6 and vmin >= -1e-6 else vmin - pad
    extent_hi = min(1.0, vmax + pad) if vmax <= 1.0 + 1e-6 and vmin >= -1e-6 else vmax + pad

    x_axis = alt.Axis(
        tickCount=6,
        labelAngle=-30,
        format=".2f",
        labelFontSize=11,
        titleFontSize=12,
        titleColor="#333333",
        labelColor="#333333",
        gridColor="#e8e8e8",
    )
    y_axis = alt.Axis(
        tickCount=5,
        labelFontSize=11,
        titleFontSize=12,
        titleColor="#333333",
        labelColor="#333333",
        gridColor="#e8e8e8",
    )

    histogram = (
        alt.Chart(sub)
        .mark_bar(opacity=0.75, color=bar_color, stroke="white", strokeWidth=0.8)
        .encode(
            x=alt.X(f"{col}:Q", bin=alt.Bin(maxbins=max_bins), axis=x_axis, title="Skor Faithfulness"),
            y=alt.Y("count()", title="Frekuensi", axis=y_axis),
            tooltip=[
                alt.Tooltip(f"{col}:Q", bin=alt.Bin(maxbins=max_bins), title="Skor", format=".3f"),
                alt.Tooltip("count()", title="Jumlah"),
            ],
        )
    )

    layers: list[alt.Chart] = [histogram]

    if len(sub) >= 2:
        bw = max(span * 0.25, 0.04) if span > 0 else 0.1
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

    # Calculate min, mean, max from the plotted population data
    s = sub[col]
    marker_label_min = "Min"
    marker_label_mean = "Mean"
    marker_label_max = "Max"
    markers = pd.DataFrame(
        [
            {"kind": marker_label_min, "value": float(s.min())},
            {"kind": marker_label_mean, "value": float(s.mean())},
            {"kind": marker_label_max, "value": float(s.max())},
        ]
    )
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
                "kind:N",
                scale=color_scale,
                legend=alt.Legend(
                    title=None,
                    labelFontSize=10,
                    symbolStrokeWidth=2,
                    orient="top",
                    direction="horizontal",
                    symbolType="stroke",
                    symbolDash=[7, 4],
                ),
            ),
            tooltip=[
                alt.Tooltip("kind:N", title="Marker"),
                alt.Tooltip("value:Q", title="Nilai", format=".4f"),
            ],
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
    )

    return (
        alt.layer(*layers)
        .resolve_scale(y="independent")
        .properties(height=300, title=chart_title)
    )


def render_faithfulness_tab() -> None:
    html_folder = str(images_faithfulness_dir())
    html_files_all = sorted(glob.glob(os.path.join(html_folder, "*.html")))

    st.header("🎯 Ringkasan Performa Klasifikasi")

    lang_choice = st.radio(
        "Filter bahasa (metrik klaim, skor jejak, daftar HTML):",
        ["Semua", "Bahasa Indonesia", "Bahasa Inggris"],
        horizontal=True,
        help="Indonesia / Inggris = subset 5 jejak (story_01–05 EN, story_06–10 ID) selaras `generate_faithfulness_images_10.py`.",
    )
    lang_map = {"Semua": "all", "Bahasa Indonesia": "id", "Bahasa Inggris": "en"}
    lang_key = lang_map[lang_choice]

    fables_m, ragas_m, metrics_live, tops_filtered = load_metrics_or_fallback(lang_key)
    if metrics_live:
        st.caption(
            "Metrik dihitung dari `Eval_Data/Observations/*.jsonl` + 10 trace sampel skripsi; "
            "ground-truth FP manual = `Streamlit/lib/faithfulness_metrics.py` (sinkron dengan HTML generator)."
        )
    else:
        st.caption(
            "⚠️ Observasi/trace tidak lengkap — menampilkan snapshot fallback terakhir. "
            "Pasang export Langfuse terbaru dan pastikan `sampling_expert` mengembalikan trace yang sama."
        )
        if lang_key != "all":
            st.info(
                "Snapshot fallback memakai agregasi kohort penuh (10 jejak). "
                "Filter bahasa tetap memfilter HTML dan statistik skor dari CSV trace bila tersedia."
            )

    eval_standard = st.radio(
        "Pilih Standar Evaluasi Analisis:",
        ["FABLES Framework", "RAGAS Standard"],
        horizontal=True,
    )

    if eval_standard == "FABLES Framework":
        m = fables_m
        cm_data = pd.DataFrame(
            {
                "Realitas (Ground Truth)": [
                    "Faithful",
                    "Faithful",
                    "Unfaithful",
                    "Unfaithful",
                ],
                "Prediksi LLM": [
                    "Faithful",
                    "Unfaithful",
                    "Faithful",
                    "Unfaithful",
                ],
                "Jumlah": [
                    m["tp"],
                    m["fn"],
                    m["fp"],
                    m["tn"],
                ],
            }
        )

        n_cv = int(m["n_cant_verify_excluded"])
        n_ps = int(m.get("n_partial_support_excluded", 0))
        n_eval = int(m["n_evaluated"])
        n_tot = int(m["n_total_claims"])
        fp_n = int(m["fp"])
        rec_u = m["recall_unfaithful"]
        interp_text = f"""
        **Interpretasi FABLES (Kim et al., arXiv:2404.01261v2):**
        * Klaim **Can't Verify** (**{n_cv}**) dan **Partial support** (**{n_ps}**) **dikecualikan** dari matriks 2×2 (hanya pasangan Faithful vs Unfaithful yang dihitung, selaras §4); sel terisi = **{n_eval}** klaim (total baris verifikasi per trace = **{n_tot}**).
        * **False positive** (prediksi FAITHFUL vs ground-truth tidak setia konteks, termasuk penyesuaian manual seperti Story 7 klaim 7 tanpa kata *resep*): **{fp_n}** klaim.
        * Recall kelas negatif (Unfaithful) ≈ **{_pct(rec_u)}** — model cenderung melewatkan pelanggaran yang seharusnya ditandai.
        """

    else:
        m = ragas_m
        cm_data = pd.DataFrame(
            {
                "Realitas (Ground Truth)": [
                    "Faithful",
                    "Faithful",
                    "Unfaithful",
                    "Unfaithful",
                ],
                "Prediksi LLM": [
                    "Faithful",
                    "Unfaithful",
                    "Faithful",
                    "Unfaithful",
                ],
                "Jumlah": [
                    m["tp"],
                    m["fn"],
                    m["fp"],
                    m["tn"],
                ],
            }
        )

        fp_f = int(fables_m["fp"])
        fp_r = int(m["fp"])
        delta_fp = fp_r - fp_f
        prec_f = fables_m["precision_faithful"]
        prec_r = m["precision_faithful"]
        n_ragas_eval = int(m["n_evaluated"])
        interp_text = f"""
        **Interpretasi RAGAS (strict / semua klaim):**
        * Di panel ini, prediksi **positif** = hanya **FAITHFUL**. Sisi negatif (Unfaithful) menggabungkan **UNFAITHFUL**, **PARTIAL_SUPPORT**, dan **CANT_VERIFY** — selaras rasio strict `ragas_standard_faithfulness` (hanya FAITHFUL di pembilang).
        * Selisih vs FABLES (FP **{fp_f}** → **{fp_r}**, Δ **{delta_fp:+d}**): FABLES (Kim et al. §4) mengeluarkan banyak **CANT_VERIFY** / **PARTIAL_SUPPORT** dari 2×2; RAGAS-style memasukkan **semua** klaim dengan aturan positif di atas.
        * Precision kelas Faithful: **{_pct(prec_f)}** (FABLES) vs **{_pct(prec_r)}** (RAGAS-style, **{n_ragas_eval}** klaim).
        """

    macro_f1 = _pct(m["macro_f1"])
    f1_faithful = _pct(m["f1_faithful"])
    f1_unfaithful = _pct(m["f1_unfaithful"])
    total_claims = str(int(m["n_evaluated"]))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Macro F1-Score ({eval_standard})", macro_f1, "Keseluruhan")
    m2.metric("F1-Score (Faithful)", f1_faithful, "Kelas Positif")
    m3.metric(
        "F1-Score (Unfaithful)",
        f1_unfaithful,
        "Kelas Negatif (-)",
        delta_color="inverse",
    )
    m4.metric("Total Klaim Dievaluasi", total_claims, "Klaim")

    st.markdown("---")

    st.header(
        f"📊 Detail Analisis {eval_standard}: Confusion Matrix & Classification Report"
    )
    col1, col2 = st.columns([1.2, 1.8])

    with col1:
        st.subheader("Confusion Matrix")
        st.caption("Visualisasi perbandingan Prediksi LLM vs Realitas (Ground Truth)")

        sort_order_pred = ["Faithful", "Unfaithful"]
        base = alt.Chart(cm_data).encode(
            x=alt.X(
                "Prediksi LLM:O",
                sort=sort_order_pred,
                title="Prediksi LLM (LLM-as-a-Judge)",
            ),
            y=alt.Y(
                "Realitas (Ground Truth):O",
                sort=["Faithful", "Unfaithful"],
                title="Realitas (Ground Truth)",
            ),
        )

        cm_max = max(int(cm_data["Jumlah"].max()), 1)
        color_max = max(cm_max, 10)

        rects = base.mark_rect().encode(
            color=alt.Color(
                "Jumlah:Q", scale=alt.Scale(scheme="blues", domain=[0, color_max]), legend=None
            )
        )

        text = base.mark_text(baseline="middle", size=24, fontWeight="bold").encode(
            text="Jumlah:Q",
            color=alt.condition(
                alt.datum.Jumlah > (color_max * 0.35), alt.value("white"), alt.value("black")
            ),
        )

        cm_chart = (rects + text).properties(height=350)
        st.altair_chart(cm_chart, use_container_width=True)

    with col2:
        st.subheader("Classification Report")
        st.caption("Rincian metrik evaluasi per kelas berdasarkan Confusion Matrix")

        sup_f = int(m["support_faithful"])
        sup_u = int(m["support_unfaithful"])
        tot = sup_f + sup_u
        report_data = pd.DataFrame(
            {
                "Kelas": [
                    "Faithful (Positif)",
                    "Unfaithful (Negatif)",
                    "Macro Avg",
                    "Weighted Avg",
                ],
                "Precision": [
                    _pct(m["precision_faithful"]),
                    _pct(m["precision_unfaithful"]),
                    _pct((m["precision_faithful"] + m["precision_unfaithful"]) / 2),
                    _pct(m["weighted_precision"]),
                ],
                "Recall": [
                    _pct(m["recall_faithful"]),
                    _pct(m["recall_unfaithful"]),
                    _pct((m["recall_faithful"] + m["recall_unfaithful"]) / 2),
                    _pct(m["weighted_recall"]),
                ],
                "F1-Score": [
                    _pct(m["f1_faithful"]),
                    _pct(m["f1_unfaithful"]),
                    _pct(m["macro_f1"]),
                    _pct(m["weighted_f1"]),
                ],
                "Support": [str(sup_f), str(sup_u), str(tot), str(tot)],
            }
        ).set_index("Kelas")

        st.dataframe(report_data, use_container_width=True)

        st.markdown(interp_text)

    st.markdown("---")

    st.header("Statistik Skor Faithfulness (Tingkat Jejak / Trace)")
    st.caption(
        "Distribusi mencakup **seluruh** trace pada CSV terbaru. "
        "Setiap baris menampilkan 3 kolom bahasa: **Keseluruhan** (N=100), "
        "**Bahasa Inggris** (N=50), dan **Bahasa Indonesia** (N=50). "
        "Garis putus-putus vertikal menandai **min / mean / max** dari "
        "subset sampling skripsi (10 jejak; 5 per bahasa). "
        "Legenda Min, Mean, dan Max ditampilkan di dalam grafik pada sisi kiri atas."
    )

    # Load full population and sampling subset data.
    all_df_raw: pd.DataFrame | None = None
    try:
        all_df_raw = load_all_traces_df()
    except Exception:
        all_df_raw = None

    tops_df_raw: pd.DataFrame | None = tops_filtered
    if tops_df_raw is None:
        try:
            tops_df_raw = load_ten_story_traces_df()
        except Exception:
            tops_df_raw = None

    if all_df_raw is not None and not all_df_raw.empty:
        # Build per-language slices.
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

        # Stats table: filtered by lang_key selected above (consistent with other sections).
        all_scores_filtered = filter_all_traces_by_language(all_df_raw, lang_key)
        if all_scores_filtered is not None and not all_scores_filtered.empty:
            stats_tbl = _describe_faithfulness_scores(all_scores_filtered)
            if stats_tbl is not None:
                lang_label_map = {"all": "Keseluruhan", "en": "Bahasa Inggris", "id": "Bahasa Indonesia"}
                st.markdown(f"**Statistik Deskriptif: {lang_label_map.get(lang_key, lang_key)}**")
                st.dataframe(_format_stats_table(stats_tbl), use_container_width=True, hide_index=True)

        # Six distribution charts: 2 metrics x 3 language columns.
        CHART_METRICS = [
            ("ragas_standard_faithfulness", "RAGAS Standard Faithfulness"),
            ("fables_faithfulness", "FABLES Faithfulness"),
        ]
        LANG_COLS = [
            ("Keseluruhan", all_scores_all, tops_all),
            ("Bahasa Inggris", all_scores_en, tops_en),
            ("Bahasa Indonesia", all_scores_id, tops_id),
        ]

        for metric_col, metric_label in CHART_METRICS:
            st.markdown(f"**{metric_label}**")
            cols_chart = st.columns(3)
            
            # Determine color theme based on the metric type
            if "ragas" in metric_col:
                bar_col_val = "#3182CE"  # Modern slate blue
                kde_col_val = "#1A365D"  # Navy blue
            else:
                bar_col_val = "#805AD5"  # Modern amethyst purple
                kde_col_val = "#4A148C"  # Dark purple

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
                            _faithfulness_dist_chart_notebook_style(
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

    st.markdown("---")

    st.header("📦 Agregasi jumlah klaim per label (seluruh cerita di export terbaru)")
    st.caption(
        "Bagian ini menghitung jumlah klaim berdasarkan 4 label: FAITHFUL, UNFAITHFUL, PARTIAL_SUPPORT, CANT_VERIFY. "
        "Sumber klaim diambil dari Observations `fables_verify_all_claims` untuk seluruh trace pada CSV terbaru."
    )
    with st.spinner("Mengagregasi klaim dari Observations..."):
        per_trace, totals = _claim_label_counts_all_traces(lang_key)

    if totals is not None and not totals.empty:
        st.subheader("Total klaim (per bahasa dan keseluruhan)")
        st.dataframe(totals, use_container_width=True, hide_index=True)
    else:
        st.info("Total klaim tidak tersedia (Observations kosong atau tidak sinkron dengan CSV trace).")

    with st.expander("Detail per cerita (per trace)"):
        if per_trace is not None and not per_trace.empty:
            st.caption("Setiap baris mewakili 1 cerita (trace). Kolom UNKNOWN menandai label di luar 4 label utama.")
            disp = per_trace.sort_values(["language", "draft_title", "trace_id"]).reset_index(drop=True)
            st.dataframe(disp, use_container_width=True, hide_index=True)
        else:
            st.info("Detail per cerita tidak tersedia.")

    st.markdown("---")

    st.header("📜 Penelusuran Klaim & Jejak HTML")
    st.caption(
        "Konteks di HTML = daftar `contexts` yang sama dengan input **RAGAS Context Relevance** "
        "dan **FABLES** di agen kritik (termasuk chunk perencana `## Rencana Cerita` bila ada). "
        "Regenerasi: `python generate_faithfulness_images_10.py` dari root repo (lihat Streamlit/README.md)."
    )

    html_files = _filter_html_paths(html_files_all, lang_key)

    if html_files:
        file_names = [os.path.basename(f) for f in html_files]
        selected_file = st.selectbox(
            "Pilih Dokumen HTML Story:", file_names, label_visibility="collapsed"
        )
        iframe_h = st.slider(
            "Tinggi panel HTML (px)",
            min_value=400,
            max_value=2200,
            value=1000,
            step=100,
            key="faithfulness_iframe_height",
        )

        selected_path = os.path.join(html_folder, selected_file)

        try:
            with open(selected_path, encoding="utf-8") as f:
                html_content = f.read()
            with st.container(border=True):
                components.html(html_content, height=int(iframe_h), scrolling=True)
        except OSError as e:
            st.error(f"Gagal memuat file HTML: {e}")
    else:
        st.error(
            "Folder 'Images_Faithfulness_10' tidak ditemukan, tidak ada file HTML, "
            "atau filter bahasa menghapus semua file."
        )

    st.markdown("---")

    st.header("📝 Kesimpulan Skripsi")
    st.info("**Sistem Terbukti Faithful Secara Kondisional**")
    st.markdown(
        """
        Dari hasil klasifikasi di atas, didapatkan dua argumen utama untuk tesis:

        1. **Validasi Paradigma LLM-as-a-Judge:** Model cenderung **tinggi recall** pada kelas *Faithful* (lihat angka terkini di metrik & laporan), tetapi **precision** menurun ketika klaim koheren secara gramatikal tidak didukung penuh oleh konteks (false positive, termasuk penyesuaian manual di HTML).
        2. **Faktor Eksternal RAG & Retrieval:** Sebagian besar false positive tidak murni “bohong” tanpa dasar; pada sampel 10 jejak terbaru, contoh tajam ada di **Story 9** klaim 1 (retrieval arkeologi Indonesia vs proposisi Skotlandia). **Story 6** klaim multimodal memakai catatan **selaras sebagian** di HTML (bukan FP di matriks).
        """
    )

    st.markdown("---")
    _render_baseline_comparison_section()
    _render_faithfulness_methodology_section()


# ---------------------------------------------------------------------------
# Baseline comparison (appended)
# ---------------------------------------------------------------------------

def _render_baseline_comparison_section() -> None:
    """Standardized comparison: Faithfulness & Coherence — Baseline vs Agentic AI."""
    from scipy import stats as scipy_stats
    import numpy as np
    from lib.baseline_loader import load_baseline_df, load_current_df, summary_stats, METRIC_LABELS
    from lib.analysis_utils import (
        add_language_col,
        filter_by_language,
        language_filter_widget,
        distribution_chart,
        boxplot_chart,
        compute_significance,
        render_significance_table,
    )

    st.header("Perbandingan Baseline vs Agentic AI")
    st.markdown(
        "Perbandingan **Faithfulness** dan **Koherensi Naratif** antara sistem baseline "
        "dan sistem Agentic AI saat ini. Gunakan filter bahasa untuk analisis per segmen."
    )

    baseline_raw = load_baseline_df()
    current_raw = load_current_df()

    if baseline_raw is None or current_raw is None:
        st.warning(
            "Data baseline atau current tidak ditemukan. "
            "Pastikan CSV export tersedia di Eval_Data/Baselines/Traces/ dan Eval_Data/Traces/."
        )
        return

    # Add language column derived from input prefix
    baseline_raw = add_language_col(baseline_raw)
    current_raw = add_language_col(current_raw)

    # Language filter — applied globally to both datasets
    lang_key = language_filter_widget(key_suffix="faithfulness_comparison")
    baseline_df = filter_by_language(baseline_raw, lang_key)
    current_df = filter_by_language(current_raw, lang_key)

    b_n = len(baseline_df)
    c_n = len(current_df)
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Baseline n", b_n)
    col_b.metric("Agentic AI n", c_n)
    col_c.metric("Filter", lang_key.upper() if lang_key != "all" else "Semua")

    if b_n < 5 or c_n < 5:
        st.warning("Data terlalu sedikit setelah filter. Pilih filter 'Semua'.")
        return

    st.divider()

    # -------------------------------------------------------------------------
    # A. Distribusi & Perbandingan per Metrik
    # -------------------------------------------------------------------------
    st.subheader("A. Distribusi Skor")
    st.caption(
        "Histogram overlaid (Baseline = abu, Agentic AI = biru) dengan garis putus-putus menunjukkan mean. "
        "Boxplot memperlihatkan median, IQR, dan outlier."
    )

    METRICS = [
        ("fables_faithfulness", "FABLES Faithfulness (0-1)", 0.0, 1.0, 0.05),
        ("ragas_standard_faithfulness", "RAGAS Standard Faithfulness (0-1)", 0.0, 1.0, 0.05),
        ("geval_avg_raw", "G-Eval Coherence — Rata-rata Raw (1-5)", 1.0, 5.0, 0.2),
        ("educational_score", "Educational Score (1-5)", 1.0, 5.0, 0.2),
    ]

    for col_name, label, x_min, x_max, bin_step in METRICS:
        if col_name not in baseline_df.columns or col_name not in current_df.columns:
            continue
        b_series = baseline_df[col_name]
        c_series = current_df[col_name]

        if b_series.dropna().empty and c_series.dropna().empty:
            continue

        st.markdown(f"**{label}**")
        c1, c2 = st.columns(2)
        with c1:
            st.altair_chart(
                distribution_chart(b_series, c_series, label, x_min=x_min, x_max=x_max, bin_step=bin_step),
                use_container_width=True,
            )
        with c2:
            st.altair_chart(
                boxplot_chart(b_series, c_series, label, x_min=x_min, x_max=x_max),
                use_container_width=True,
            )

    st.divider()

    # -------------------------------------------------------------------------
    # B. Uji Signifikansi Statistik
    # -------------------------------------------------------------------------
    st.subheader("B. Uji Signifikansi Statistik")
    st.markdown(
        "**Mann-Whitney U test** (one-sided: Agentic AI > Baseline, distribusi tidak diasumsikan normal). "
        "**Cohen's d** sebagai effect size. "
        f"n Baseline = {b_n}, n Agentic AI = {c_n} "
        f"({'filter: ' + lang_key.upper() if lang_key != 'all' else 'keseluruhan'})."
    )

    SIG_METRICS = [
        ("FABLES Faithfulness", "fables_faithfulness"),
        ("RAGAS Standard Faithfulness", "ragas_standard_faithfulness"),
        ("G-Eval Coherence (avg raw, 1-5)", "geval_avg_raw"),
        ("Educational Score", "educational_score"),
    ]

    sig_rows = []
    for label, col_name in SIG_METRICS:
        if col_name not in baseline_df.columns or col_name not in current_df.columns:
            continue
        result = compute_significance(baseline_df[col_name], current_df[col_name], label)
        if result:
            sig_rows.append(result)

    render_significance_table(sig_rows)

    st.divider()

    # -------------------------------------------------------------------------
    # C. Ringkasan Statistik
    # -------------------------------------------------------------------------
    st.subheader("C. Ringkasan Statistik Deskriptif")
    focus_metrics = ["fables_faithfulness", "ragas_standard_faithfulness", "geval_avg_raw", "educational_score"]
    b_stats = summary_stats(baseline_df, focus_metrics)
    c_stats = summary_stats(current_df, focus_metrics)

    b_stats = b_stats.rename(columns={"Mean": "Baseline Mean", "Std": "Baseline Std", "N": "Baseline N"})
    c_stats = c_stats.rename(columns={"Mean": "Current Mean", "Std": "Current Std", "N": "Current N"})

    combined = b_stats[["Metric", "Baseline N", "Baseline Mean", "Baseline Std"]].merge(
        c_stats[["Metric", "Current N", "Current Mean", "Current Std"]],
        on="Metric",
        how="outer",
    )
    combined["Current Mean"] = pd.to_numeric(combined["Current Mean"], errors="coerce")
    combined["Baseline Mean"] = pd.to_numeric(combined["Baseline Mean"], errors="coerce")
    combined["Delta Mean"] = (combined["Current Mean"] - combined["Baseline Mean"]).round(4)
    combined["Delta Mean"] = combined["Delta Mean"].apply(lambda x: f"{x:+.4f}" if pd.notna(x) else "N/A")
    st.dataframe(combined, use_container_width=True, hide_index=True)

    st.divider()

    # -------------------------------------------------------------------------
    # D. Distribusi Jumlah Klaim (FABLES)
    # -------------------------------------------------------------------------
    if "fables_claims_total" in baseline_df.columns and "fables_claims_total" in current_df.columns:
        st.subheader("D. Distribusi Jumlah Klaim (FABLES)")
        st.caption(
            "Jumlah klaim diambil dari output span `fables_faithfulness` (export Observations). "
            "RAGAS strict memasukkan semua klaim (total), sedangkan FABLES 2×2 mengecualikan "
            "CANT_VERIFY dan PARTIAL_SUPPORT."
        )

        def _as_int_sum(s: pd.Series) -> int:
            v = pd.to_numeric(s, errors="coerce").dropna()
            if v.empty:
                return 0
            return int(v.sum())

        def _pct(x: int, denom: int) -> str:
            if denom <= 0:
                return "0.00%"
            return f"{(x / denom) * 100:.2f}%"

        def _label_breakdown_row(df: pd.DataFrame, system_label: str) -> dict:
            total = _as_int_sum(df.get("fables_claims_total", pd.Series([], dtype=float)))
            faithful = _as_int_sum(df.get("fables_claims_faithful", pd.Series([], dtype=float)))
            unfaithful = _as_int_sum(df.get("fables_claims_unfaithful", pd.Series([], dtype=float)))
            partial = _as_int_sum(df.get("fables_claims_partial_support", pd.Series([], dtype=float)))
            cant_verify = _as_int_sum(df.get("fables_claims_cant_verify", pd.Series([], dtype=float)))
            evaluated = faithful + unfaithful

            return {
                "Sistem": system_label,
                "Total klaim": total,
                "FAITHFUL": f"{faithful} ({_pct(faithful, total)})",
                "UNFAITHFUL": f"{unfaithful} ({_pct(unfaithful, total)})",
                "PARTIAL_SUPPORT": f"{partial} ({_pct(partial, total)})",
                "CANT_VERIFY": f"{cant_verify} ({_pct(cant_verify, total)})",
                "Klaim dievaluasi (2×2)": f"{evaluated} ({_pct(evaluated, total)})",
            }

        st.subheader("D1. Komposisi 4 label FABLES (sum dan persentase)")
        st.caption("Persentase dihitung dari total klaim (fables_claims_total) setelah filter bahasa.")
        lbl_tbl = pd.DataFrame(
            [
                _label_breakdown_row(baseline_df, "Baseline"),
                _label_breakdown_row(current_df, "Agentic AI"),
            ]
        )
        st.dataframe(lbl_tbl, use_container_width=True, hide_index=True)

        def _sum_mean_rows(label: str, s_base: pd.Series, s_cur: pd.Series) -> pd.DataFrame:
            b = pd.to_numeric(s_base, errors="coerce").dropna()
            c = pd.to_numeric(s_cur, errors="coerce").dropna()
            return pd.DataFrame(
                [
                    {
                        "Metrik": label,
                        "Baseline n": int(b.count()),
                        "Baseline sum": float(b.sum()) if not b.empty else 0.0,
                        "Baseline mean": float(b.mean()) if not b.empty else 0.0,
                        "Agentic n": int(c.count()),
                        "Agentic sum": float(c.sum()) if not c.empty else 0.0,
                        "Agentic mean": float(c.mean()) if not c.empty else 0.0,
                    }
                ]
            )

        st.markdown("**Ringkasan (sum dan mean) jumlah klaim setelah filter bahasa**")
        sum_tbls = [_sum_mean_rows("Klaim Total (dipakai RAGAS strict)", baseline_df["fables_claims_total"], current_df["fables_claims_total"])]
        if "fables_claims_evaluated" in baseline_df.columns and "fables_claims_evaluated" in current_df.columns:
            sum_tbls.append(
                _sum_mean_rows(
                    "Klaim Dievaluasi (faithful+unfaithful, dipakai FABLES 2×2)",
                    baseline_df["fables_claims_evaluated"],
                    current_df["fables_claims_evaluated"],
                )
            )
        summary_claims = pd.concat(sum_tbls, ignore_index=True)
        summary_claims["Baseline sum"] = summary_claims["Baseline sum"].map(lambda x: f"{x:.0f}")
        summary_claims["Agentic sum"] = summary_claims["Agentic sum"].map(lambda x: f"{x:.0f}")
        summary_claims["Baseline mean"] = summary_claims["Baseline mean"].map(lambda x: f"{x:.2f}")
        summary_claims["Agentic mean"] = summary_claims["Agentic mean"].map(lambda x: f"{x:.2f}")
        st.dataframe(summary_claims, use_container_width=True, hide_index=True)

        def _metric_box(title: str, s: pd.Series) -> None:
            v = pd.to_numeric(s, errors="coerce").dropna()
            if v.empty:
                st.metric(title, "N/A")
            else:
                st.metric(title, f"{float(v.mean()):.2f}", f"n={int(v.count())}")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _metric_box("Baseline mean klaim total", baseline_df["fables_claims_total"])
        with c2:
            _metric_box("Agentic mean klaim total", current_df["fables_claims_total"])
        if "fables_claims_evaluated" in baseline_df.columns and "fables_claims_evaluated" in current_df.columns:
            with c3:
                _metric_box("Baseline mean klaim dievaluasi", baseline_df["fables_claims_evaluated"])
            with c4:
                _metric_box("Agentic mean klaim dievaluasi", current_df["fables_claims_evaluated"])

        st.markdown("**Klaim Total (semua klaim, dipakai RAGAS strict)**")
        cc1, cc2 = st.columns(2)
        with cc1:
            st.altair_chart(
                distribution_chart(
                    baseline_df["fables_claims_total"],
                    current_df["fables_claims_total"],
                    "Jumlah Klaim Total",
                    x_min=0.0,
                    bin_step=1.0,
                ),
                use_container_width=True,
            )
        with cc2:
            st.altair_chart(
                boxplot_chart(
                    baseline_df["fables_claims_total"],
                    current_df["fables_claims_total"],
                    "Jumlah Klaim Total",
                    x_min=0.0,
                ),
                use_container_width=True,
            )

        if "fables_claims_evaluated" in baseline_df.columns and "fables_claims_evaluated" in current_df.columns:
            st.markdown("**Klaim Dievaluasi (faithful + unfaithful, dipakai FABLES 2×2)**")
            cc3, cc4 = st.columns(2)
            with cc3:
                st.altair_chart(
                    distribution_chart(
                        baseline_df["fables_claims_evaluated"],
                        current_df["fables_claims_evaluated"],
                        "Jumlah Klaim Dievaluasi (FABLES 2×2)",
                        x_min=0.0,
                        bin_step=1.0,
                    ),
                    use_container_width=True,
                )
            with cc4:
                st.altair_chart(
                    boxplot_chart(
                        baseline_df["fables_claims_evaluated"],
                        current_df["fables_claims_evaluated"],
                        "Jumlah Klaim Dievaluasi (FABLES 2×2)",
                        x_min=0.0,
                    ),
                    use_container_width=True,
                )



# ---------------------------------------------------------------------------
# Methodology / PRD section (appended)
# ---------------------------------------------------------------------------

_FABLES_EXTRACT_PROMPT = """\
FABLES Claim Extraction (Kim et al., 2024; arXiv:2404.01261v2 — Appendix B)

Task: Extract ALL verifiable real-world statements from the educational story into atomic claims.

What to extract:
- Scientific facts, phenomena; educational concepts; historical facts; properties of real entities
- Real-world claims even when spoken by fictional characters

Mandatory rules:
1. Each claim must be fully understood without additional context — replace pronouns with entity names.
2. Place claims in temporal, locational, or causal context when possible.
3. Maximum 2 sentences per claim.
4. Separate claims with '- ' prefix on a new line.

SKIP purely fictional events with no real-world factual content.
If no verifiable claims: reply exactly with: tidak ada
"""

_FABLES_VERIFY_PROMPT = """\
FABLES Claim Verification (Kim et al., 2024; arXiv:2404.01261v2 — §2 Label Scheme)

Given: research context + one claim from an educational story.
Task: Choose ONE faithfulness label.

LABELS (exact token on last line):
- FAITHFUL — claim accurately reflects facts supported by context.
- UNFAITHFUL — claim misrepresents or contradicts context.
- PARTIAL_SUPPORT — partially supported; goes beyond context.
- CANT_VERIFY — insufficient evidence; topic not covered.

Output: 1–2 sentence reasoning, then last line = one exact token.
"""


def _render_faithfulness_methodology_section() -> None:
    """PRD-style methodology section for FABLES and RAGAS."""
    st.header("📋 Metodologi Evaluasi Faithfulness (PRD)")

    st.subheader("FABLES Faithfulness (Kim et al., 2024)")
    st.markdown("""
**Referensi:** Kim et al., 2024; arXiv:2404.01261v2

| Parameter | Value |
|-----------|-------|
| Framework | Claim-level faithfulness verification |
| Phase 1 | Claim extraction — LLM extracts ≤10 atomic factual claims |
| Phase 2 | Per-claim verification — LLM assigns label per claim vs. contexts |
| Labels | FAITHFUL / UNFAITHFUL / PARTIAL_SUPPORT / CANT_VERIFY |
| Score formula | `fables_faithfulness = faithful / (faithful + unfaithful)` |
| Strict formula | `ragas_standard_faithfulness = faithful / total_claims` |
| Max claims | 10 (capped for cost efficiency) |
| Timing | Finalize only — after APPROVE decision |
| Routing impact | None — logging & thesis analysis only |
""")

    with st.expander("Default Prompt: FABLES Claim Extraction"):
        st.code(_FABLES_EXTRACT_PROMPT, language="markdown")

    with st.expander("Default Prompt: FABLES Claim Verification"):
        st.code(_FABLES_VERIFY_PROMPT, language="markdown")

    st.divider()

    st.subheader("RAGAS — Answer Relevancy & Context Relevance")
    st.markdown("""
| Parameter | Value |
|-----------|-------|
| Framework | RAGAS (Retrieval-Augmented Generation Assessment) |
| Metrics | `AnswerRelevancy` + `ContextRelevance` |
| Scale | 0.0–1.0 per metric |
| Timeout | 90 seconds per metric |
| Retries | 3 per metric |
| Timing | Finalize only |
| Context source | Planner plan + web research answers + LightRAG KG chunks |
| Routing impact | None — logging only |
""")
