"""WikiEval EDA tab — konten dari notebooks/01_analisis_dataset_wikieval.ipynb (Altair)."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.paths import repo_root, wikieval_json_path
from lib.wikieval_dataset import build_wikieval_state


def _hist_with_mean(
    df: pd.DataFrame,
    col: str,
    title: str,
    color: str,
    *,
    x_title: str = "Jumlah Kata",
    max_bins: int = 15,
) -> alt.Chart:
    mu = float(df[col].mean())
    base = alt.Chart(df)
    bars = base.mark_bar(color=color, opacity=0.75, stroke="white").encode(
        alt.X(f"{col}:Q", bin=alt.Bin(maxbins=max_bins), title=x_title),
        y=alt.Y("count()", title="Frekuensi"),
    )
    rule = alt.Chart(pd.DataFrame({"m": [mu]})).mark_rule(
        color="black", strokeDash=[4, 4], size=2
    ).encode(x="m:Q")
    return (
        (bars + rule)
        .properties(title=title, height=260)
        .configure_view(strokeWidth=0, fill="#fafafa")
        .configure_axis(grid=True, gridColor="#e0e0e0")
    )


def _hist_kde_sim(
    df: pd.DataFrame,
    col: str,
    title: str,
    color: str,
    *,
    max_bins: int = 12,
) -> alt.Chart:
    mu = float(df[col].mean())
    hist = df[[col]].copy()
    bars = (
        alt.Chart(hist)
        .mark_bar(color=color, opacity=0.75)
        .encode(
            alt.X(f"{col}:Q", bin=alt.Bin(maxbins=max_bins), title="Skor"),
            y=alt.Y("count()", title="Frekuensi"),
        )
    )
    rule = alt.Chart(pd.DataFrame({"m": [mu]})).mark_rule(
        color="black", strokeDash=[4, 4]
    ).encode(x="m:Q")
    if len(hist) < 2:
        layered = bars + rule
    else:
        lo = float(hist[col].min())
        hi = float(hist[col].max())
        span = hi - lo
        bw = max(span * 0.15, 0.02) if span > 0 else 0.05
        kde = (
            alt.Chart(hist)
            .transform_density(
                col,
                as_=[col, "density"],
                groupby=[],
                extent=[max(0, lo - 0.05), min(1.0, hi + 0.05)],
                bandwidth=bw,
            )
            .mark_line(color="#222", strokeWidth=1.5)
            .encode(x=f"{col}:Q", y=alt.Y("density:Q", axis=None))
        )
        layered = alt.layer(bars + rule, kde).resolve_scale(y="independent")
    return (
        layered.properties(title=title, height=280)
        .configure_view(strokeWidth=0, fill="#fafafa")
        .configure_axis(grid=True, gridColor="#e0e0e0")
    )


def render_wikieval_tab() -> None:
    st.header("📚 WikiEval — EDA Dataset")
    st.markdown(
        """
        Eksplorasi data **WikiEval (Bahasa Inggris)** untuk landasan QA-based story generation.
        Alur dan metrik mengikuti **`notebooks/01_analisis_dataset_wikieval.ipynb`**.

        | Sumber | Keterangan |
        |--------|------------|
        | `dataset/wikiEval_all.json` | 50 item ground truth (7 kolom inti) |
        """
    )

    state, err = build_wikieval_state(wikieval_json_path())

    if err or state is None:
        st.error(err or "Tidak dapat memuat WikiEval.")
        st.info(
            "Export dataset dari HuggingFace `vibrantlabsai/WikiEval` ke `dataset/wikiEval_all.json` "
            "(lihat Bab 4.1 / notebook 01)."
        )
        return

    rel = state.json_path.relative_to(repo_root())
    st.caption(f"Dimuat dari `{rel}` (encoding={state.encoding}).")

    st.subheader("1. Validasi skema & pra-pemrosesan")
    c1, c2, c3 = st.columns(3)
    c1.metric("Item mentah", str(state.raw_count))
    c2.metric("Invalid skema", str(len(state.invalid_schema_df)))
    c3.metric("Setelah deduplikasi", str(state.preprocess.final_count))
    st.caption(
        f"Duplikat dihapus: **{state.preprocess.dup_removed}** "
        f"(dari {state.preprocess.cleaned_count} baris bersih)."
    )

    if len(state.invalid_schema_df):
        st.warning("Terdapat baris yang tidak memenuhi skema minimal.")
        st.dataframe(state.invalid_schema_df.head(20), use_container_width=True)
    else:
        st.success("Semua item memenuhi skema minimal (kolom wajib + tipe `context_*`).")

    with st.expander("Ringkasan missing value (sebelum / sesudah cleaning)"):
        st.dataframe(state.preprocess.ringkas_pp, use_container_width=True, hide_index=True)

    st.subheader("2. Statistik panjang kata (word count)")
    desc = state.df_src[["kata_tanya", "kata_jawab", "kata_ctx_v1", "kata_ctx_v2"]].describe().round(1)
    st.dataframe(desc, use_container_width=True)

    st.markdown("**Distribusi panjang teks** (histogram + garis mean — setara notebook).")
    specs = [
        ("kata_tanya", "Pertanyaan", "#4c72b0"),
        ("kata_jawab", "Jawaban referensi", "#dd8452"),
        ("kata_ctx_v1", "Konteks V1 (LightRAG)", "#55a868"),
        ("kata_ctx_v2", "Konteks V2 (diperkaya)", "#c44e52"),
    ]
    r1c1, r1c2 = st.columns(2)
    r2c1, r2c2 = st.columns(2)
    charts = [r1c1, r1c2, r2c1, r2c2]
    for col_ch, (col, title, color) in zip(charts, specs):
        with col_ch:
            st.altair_chart(
                _hist_with_mean(state.df_src, col, title, color),
                use_container_width=True,
            )

    st.subheader("2.1 Tipe pertanyaan & pengayaan konteks V1→V2")
    tc1, tc2 = st.columns(2)
    with tc1:
        tdf = state.types_df.copy()
        bar = (
            alt.Chart(tdf)
            .mark_bar()
            .encode(
                x=alt.X("Jumlah:Q", title="Frekuensi"),
                y=alt.Y("Tipe:N", sort="-x", title=None),
                color=alt.Color("Tipe:N", legend=None, scale=alt.Scale(scheme="category10")),
            )
            .properties(title="Distribusi tipe pertanyaan (cognitive types)", height=320)
            .configure_view(strokeWidth=0, fill="#fafafa")
            .configure_axis(grid=True, gridColor="#e0e0e0")
        )
        st.altair_chart(bar, use_container_width=True)

    with tc2:
        max_val = max(
            int(state.df_src["kata_ctx_v1"].max()),
            int(state.df_src["kata_ctx_v2"].max()),
            1,
        )
        line_df = pd.DataFrame({"x": [0, max_val], "y": [0, max_val]})
        line = (
            alt.Chart(line_df)
            .mark_line(color="#c44e52", strokeDash=[4, 4], strokeWidth=2)
            .encode(x="x:Q", y="y:Q")
        )
        pts = (
            alt.Chart(state.df_src)
            .mark_circle(size=70, color="#4c72b0", opacity=0.65)
            .encode(
                x=alt.X("kata_ctx_v1:Q", title="Jumlah kata konteks V1"),
                y=alt.Y("kata_ctx_v2:Q", title="Jumlah kata konteks V2"),
            )
        )
        mean_up = state.df_src["selisih_ctx"].mean()
        mean_ratio = state.df_src["rasio_ctx"].mean()
        pct_extra = (
            f"{(float(mean_ratio) - 1) * 100:.0f}%"
            if pd.notna(mean_ratio)
            else "n/a"
        )
        title = (
            f"Pengayaan konteks LightRAG — rata-rata +{mean_up:.0f} kata "
            f"(~{pct_extra} dari rasio V2/V1 rata-rata)"
        )
        st.altair_chart(
            (pts + line).properties(title=title, height=320).configure_view(
                strokeWidth=0, fill="#fafafa"
            ),
            use_container_width=True,
        )
    mr = state.df_src["rasio_ctx"].mean()
    mr_s = f"{float(mr):.2f}×" if pd.notna(mr) else "n/a"
    st.caption(
        f"Rata-rata lonjakan V1→V2: **+{state.df_src['selisih_ctx'].mean():.1f}** kata; "
        f"rasio rata-rata V2/V1: **{mr_s}**."
    )

    st.subheader("2.2 Perbandingan jumlah kata antar kualitas jawaban")
    box_df = pd.DataFrame(
        {
            "Ground Truth (Asli)": state.df_src["kata_jawab"],
            "Jawaban tak berdasar (Ungrounded)": state.df_src["kata_ungrounded"],
            "Jawaban buruk (Poor)": state.df_src["kata_buruk"],
        }
    )
    melted = box_df.melt(var_name="Kategori", value_name="Jumlah kata")
    box = (
        alt.Chart(melted)
        .mark_boxplot(extent="min-max", ticks=True)
        .encode(
            x=alt.X("Kategori:N", title=None, axis=alt.Axis(labelAngle=-25)),
            y=alt.Y("Jumlah kata:Q", title="Jumlah kata"),
            color=alt.Color(
                "Kategori:N",
                legend=None,
                scale=alt.Scale(
                    domain=list(box_df.columns),
                    range=["#55a868", "#c44e52", "#8172b3"],
                ),
            ),
        )
        .properties(height=340, title="Perbandingan jumlah kata antar kualitas jawaban")
        .configure_view(strokeWidth=0, fill="#fafafa")
    )
    st.altair_chart(box, use_container_width=True)

    st.subheader("3. Kemiripan Context V1 vs V2")
    st.markdown(
        """
        **Cosine similarity** (frekuensi token) dan **Jaccard** (himpunan token unik), plus panjang konteks.
        """
    )
    df_sim = state.df_sim
    if df_sim.empty:
        st.warning("Data kosong — analisis kemiripan dilewati.")
        return

    sim_cols = [
        "sim_kosinus",
        "sim_jaccard",
        "panjang_ctx_v1",
        "panjang_ctx_v2",
        "delta_panjang",
        "rasio_panjang_v2_v1",
    ]
    st.dataframe(df_sim[sim_cols].describe().round(3), use_container_width=True)

    s1, s2 = st.columns(2)
    with s1:
        st.altair_chart(
            _hist_kde_sim(df_sim, "sim_kosinus", "Distribusi cosine similarity", "#4c72b0"),
            use_container_width=True,
        )
    with s2:
        st.altair_chart(
            _hist_kde_sim(df_sim, "sim_jaccard", "Distribusi Jaccard similarity", "#55a868"),
            use_container_width=True,
        )

    s3, s4 = st.columns(2)
    with s3:
        sc1 = (
            alt.Chart(df_sim)
            .mark_circle(size=80)
            .encode(
                x=alt.X("sim_kosinus:Q", title="Cosine similarity"),
                y=alt.Y("sim_jaccard:Q", title="Jaccard similarity"),
                color=alt.Color(
                    "delta_panjang:Q",
                    scale=alt.Scale(scheme="blueorange"),
                    title="Δ panjang",
                ),
            )
            .properties(title="Cosine vs Jaccard (warna = delta panjang)", height=300)
            .configure_view(strokeWidth=0, fill="#fafafa")
        )
        st.altair_chart(sc1, use_container_width=True)

    with s4:
        batas = max(df_sim["panjang_ctx_v1"].max(), df_sim["panjang_ctx_v2"].max(), 1)
        line2 = (
            alt.Chart(pd.DataFrame({"x": [0, batas], "y": [0, batas]}))
            .mark_line(color="black", strokeDash=[4, 4], opacity=0.5)
            .encode(x="x:Q", y="y:Q")
        )
        sc2 = (
            alt.Chart(df_sim)
            .mark_circle(size=80, color="#dd8452", opacity=0.75)
            .encode(
                x=alt.X("panjang_ctx_v1:Q", title="Panjang context V1 (kata)"),
                y=alt.Y("panjang_ctx_v2:Q", title="Panjang context V2 (kata)"),
            )
        )
        st.altair_chart(
            (sc2 + line2)
            .properties(title="Perbandingan panjang context (garis y = x)", height=300)
            .configure_view(strokeWidth=0, fill="#fafafa"),
            use_container_width=True,
        )

    st.markdown("**5 item paling mirip / paling berbeda** (cosine).")
    top5 = df_sim.sort_values("sim_kosinus", ascending=False)[
        ["index_item", "source", "sim_kosinus", "sim_jaccard", "delta_panjang", "question"]
    ].head(5)
    bot5 = df_sim.sort_values("sim_kosinus", ascending=True)[
        ["index_item", "source", "sim_kosinus", "sim_jaccard", "delta_panjang", "question"]
    ].head(5)
    tcol, bcol = st.columns(2)
    with tcol:
        st.caption("Paling mirip")
        st.dataframe(top5, use_container_width=True, hide_index=True)
    with bcol:
        st.caption("Paling berbeda")
        st.dataframe(bot5, use_container_width=True, hide_index=True)

    low_sim = df_sim.sort_values("sim_kosinus", ascending=True).head(10).copy()
    low_sim["label"] = low_sim["source"].astype(str).str.slice(0, 36)
    bar_low = (
        alt.Chart(low_sim)
        .mark_bar(color="#c44e52")
        .encode(
            x=alt.X("sim_kosinus:Q", title="Cosine similarity"),
            y=alt.Y("label:N", sort="-x", title="Source (truncated)"),
        )
        .properties(title="10 item dengan cosine similarity terendah", height=360)
        .configure_view(strokeWidth=0, fill="#fafafa")
    )
    st.altair_chart(bar_low, use_container_width=True)
