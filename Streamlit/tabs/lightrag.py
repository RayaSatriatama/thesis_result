"""LightRAG storage before/after comparison tab."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from lib.lightrag_stats import (
    ExtendedKGStats,
    RagStorageStats,
    load_extended_kg_stats,
    load_rag_storage_stats,
)
from lib.paths import (
    default_before_backup_label,
    list_before_backup_choices,
    lightrag_live_rag_storage,
    resolve_locale_rag_dir,
)

_LABEL_BEFORE = "Sebelum (backup)"
_LABEL_AFTER = "Sesudah (live)"

# Urutan baris tabel & diagram (dokumen)
_DOC_ROW_ORDER: list[str] = [
    "Total dokumen",
    "WikiEval v1",
    "WikiEval v2",
    "WikiEval total",
    "unknown_source",
    "Dokumen lain (non-WikiEval path)",
    "Total chunks (sum chunks_count)",
]

# Label pendek untuk sumbu diagram (sumbu Y tidak penuh teks teknis)
_DOC_CHART_LABEL: dict[str, str] = {
    "Total dokumen": "Total dokumen terindeks",
    "WikiEval v1": "WikiEval konteks v1",
    "WikiEval v2": "WikiEval konteks v2",
    "WikiEval total": "WikiEval (v1+v2+lain)",
    "unknown_source": "Tanpa path sumber jelas",
    "Dokumen lain (non-WikiEval path)": "Injeksi agen / non-WikiEval",
    "Total chunks (sum chunks_count)": "Total chunk (Σ chunks_count)",
}

_KG_ROW_ORDER: list[str] = [
    "VDB entities (embedding data[])",
    "VDB relationships (data[])",
    "VDB chunks (data[])",
    "KV full_entities (keys)",
    "KV full_relations (keys)",
    "GraphML nodes (<node id=)",
    "GraphML edges (<edge source=)",
]

_KG_CHART_LABEL: dict[str, str] = {
    "VDB entities (embedding data[])": "Entitas (vektor VDB)",
    "VDB relationships (data[])": "Relasi (vektor VDB)",
    "VDB chunks (data[])": "Chunk (vektor VDB)",
    "KV full_entities (keys)": "Grup entitas (KV)",
    "KV full_relations (keys)": "Grup relasi (KV)",
    "GraphML nodes (<node id=)": "Node di GraphML",
    "GraphML edges (<edge source=)": "Edge di GraphML",
}


def _comparison_table_doc(before: RagStorageStats, after: RagStorageStats) -> pd.DataFrame:
    b = before.to_row_dict()
    a = after.to_row_dict()
    rows = []
    for key in _DOC_ROW_ORDER:
        if key not in b or key not in a:
            continue
        bv, av = b[key], a[key]
        if isinstance(bv, int) and isinstance(av, int):
            rows.append(
                {
                    "Metrik": key,
                    "Sebelum": bv,
                    "Sesudah": av,
                    "Selisih": av - bv,
                }
            )
    return pd.DataFrame(rows)


def _comparison_table_kg(before: ExtendedKGStats, after: ExtendedKGStats) -> pd.DataFrame:
    b = before.to_row_dict()
    a = after.to_row_dict()
    rows = []
    for key in _KG_ROW_ORDER:
        if key not in b or key not in a:
            continue
        bv, av = b[key], a[key]
        if isinstance(bv, int) and isinstance(av, int) and bv >= 0 and av >= 0:
            rows.append(
                {
                    "Metrik": key,
                    "Sebelum": bv,
                    "Sesudah": av,
                    "Selisih": av - bv,
                }
            )
    return pd.DataFrame(rows)


def _long_df_for_chart(
    table: pd.DataFrame,
    label_map: dict[str, str],
) -> pd.DataFrame:
    if table.empty:
        return pd.DataFrame(columns=["Metrik_lensa", "Periode", "Nilai"])
    rows: list[dict[str, str | int]] = []
    for _, r in table.iterrows():
        mk = str(r["Metrik"])
        label = label_map.get(mk, mk)
        rows.append(
            {"Metrik_lensa": label, "Periode": _LABEL_BEFORE, "Nilai": int(r["Sebelum"])}
        )
        rows.append(
            {"Metrik_lensa": label, "Periode": _LABEL_AFTER, "Nilai": int(r["Sesudah"])}
        )
    df = pd.DataFrame(rows)
    order_labels = [label_map.get(k, k) for k in table["Metrik"].tolist()]
    df["Metrik_lensa"] = pd.Categorical(
        df["Metrik_lensa"], categories=order_labels, ordered=True
    )
    df["Periode"] = pd.Categorical(
        df["Periode"], categories=[_LABEL_BEFORE, _LABEL_AFTER], ordered=True
    )
    return df.sort_values(["Metrik_lensa", "Periode"])


def _dumbbell_chart(df: pd.DataFrame, title: str) -> alt.Chart | None:
    """Garis menghubungkan Sebelum→Sesudah; titik berwarna. Tanpa yOffset."""
    if df.empty:
        return None
    n_met = int(df["Metrik_lensa"].nunique())
    h = min(max(n_met * 44 + 100, 220), 560)
    y_order = list(df["Metrik_lensa"].cat.categories)

    base = alt.Chart(df)
    connector = base.mark_line(color="#64748b", strokeWidth=2.5).encode(
        x=alt.X(
            "Nilai:Q",
            title="Jumlah",
            scale=alt.Scale(zero=True, nice=True),
            axis=alt.Axis(format="~s", labelFontSize=12, titleFontSize=13),
        ),
        y=alt.Y(
            "Metrik_lensa:N",
            sort=y_order,
            title=None,
            axis=alt.Axis(
                labelFontSize=12,
                labelLimit=320,
                title=None,
            ),
        ),
        detail="Metrik_lensa:N",
    )
    points = base.mark_circle(size=200, stroke="white", strokeWidth=2).encode(
        x="Nilai:Q",
        y=alt.Y("Metrik_lensa:N", sort=y_order),
        color=alt.Color(
            "Periode:N",
            title="",
            scale=alt.Scale(
                domain=[_LABEL_BEFORE, _LABEL_AFTER],
                range=["#1d4ed8", "#15803d"],
            ),
            legend=alt.Legend(
                orient="bottom",
                direction="horizontal",
                labelFontSize=12,
                symbolSize=100,
                titleFontSize=12,
            ),
        ),
        tooltip=[
            alt.Tooltip("Metrik_lensa:N", title="Metrik"),
            alt.Tooltip("Periode:N", title="Sumber data"),
            alt.Tooltip("Nilai:Q", title="Nilai", format=","),
        ],
    )
    chart = (
        (connector + points)
        .properties(
            width=720,
            height=h,
            padding={"left": 8, "right": 12, "top": 16, "bottom": 56},
            title=alt.TitleParams(text=title, anchor="start", fontSize=15, dy=-8),
        )
        .configure_view(stroke=None)
        .configure_title(fontWeight="normal")
    )
    return chart


def _metrics_headline_doc(before: RagStorageStats, after: RagStorageStats) -> None:
    d = after.total_docs - before.total_docs
    w = after.wikieval_total - before.wikieval_total
    o = after.other_docs - before.other_docs
    c1, c2, c3 = st.columns(3)
    c1.metric("Total dokumen (live)", f"{after.total_docs:,}", delta=f"{d:+,} vs backup")
    c2.metric("WikiEval di KG (v1+v2+…)", f"{after.wikieval_total:,}", delta=f"{w:+,}")
    c3.metric("Non-WikiEval / injeksi agen", f"{after.other_docs:,}", delta=f"{o:+,}")


def _metrics_headline_kg(before: ExtendedKGStats, after: ExtendedKGStats) -> None:
    if before.graphml_nodes < 0 or after.graphml_nodes < 0:
        return
    dn = after.graphml_nodes - before.graphml_nodes
    de = after.graphml_edges - before.graphml_edges
    dv = after.vdb_entities - before.vdb_entities
    c1, c2, c3 = st.columns(3)
    c1.metric("Node GraphML (live)", f"{after.graphml_nodes:,}", delta=f"{dn:+,}")
    c2.metric("Edge GraphML (live)", f"{after.graphml_edges:,}", delta=f"{de:+,}")
    c3.metric("Entitas VDB (live)", f"{after.vdb_entities:,}", delta=f"{dv:+,}")


def _doc_int(stat: RagStorageStats | None, key: str) -> int | None:
    if stat is None or stat.error:
        return None
    v = stat.to_row_dict().get(key)
    return int(v) if isinstance(v, int) else None


def _kg_int(stat: ExtendedKGStats | None, key: str) -> int | None:
    if stat is None or stat.error:
        return None
    v = stat.to_row_dict().get(key)
    if isinstance(v, int) and v >= 0:
        return v
    return None


def _wide_id_en_doc_table(
    bid: RagStorageStats | None,
    ben: RagStorageStats | None,
    lid: RagStorageStats | None,
    len_: RagStorageStats | None,
) -> pd.DataFrame:
    rows = []
    for key in _DOC_ROW_ORDER:
        id_b = _doc_int(bid, key)
        en_b = _doc_int(ben, key)
        id_l = _doc_int(lid, key)
        en_l = _doc_int(len_, key)
        sel = (
            (id_l - en_l)
            if id_l is not None and en_l is not None
            else None
        )
        rows.append(
            {
                "Metrik": key,
                "ID backup": id_b,
                "EN backup": en_b,
                "ID live": id_l,
                "EN live": en_l,
                "Selisih live (ID−EN)": sel,
            }
        )
    return pd.DataFrame(rows)


def _wide_id_en_kg_table(
    bid: ExtendedKGStats | None,
    ben: ExtendedKGStats | None,
    lid: ExtendedKGStats | None,
    len_: ExtendedKGStats | None,
) -> pd.DataFrame:
    rows = []
    for key in _KG_ROW_ORDER:
        id_b = _kg_int(bid, key)
        en_b = _kg_int(ben, key)
        id_l = _kg_int(lid, key)
        en_l = _kg_int(len_, key)
        sel = (
            (id_l - en_l)
            if id_l is not None and en_l is not None
            else None
        )
        rows.append(
            {
                "Metrik": key,
                "ID backup": id_b,
                "EN backup": en_b,
                "ID live": id_l,
                "EN live": en_l,
                "Selisih live (ID−EN)": sel,
            }
        )
    return pd.DataFrame(rows)


def _long_id_en_for_chart(
    wide: pd.DataFrame,
    label_map: dict[str, str],
    metric_keys: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, str | int]] = []
    for _, r in wide.iterrows():
        mk = str(r["Metrik"])
        if mk not in metric_keys:
            continue
        ml = label_map.get(mk, mk)
        pairs = [
            ("Backup", "ID", "ID backup"),
            ("Backup", "EN", "EN backup"),
            ("Live", "ID", "ID live"),
            ("Live", "EN", "EN live"),
        ]
        for periode, bahasa, col in pairs:
            v = r[col]
            if pd.notna(v) and v is not None:
                rows.append(
                    {
                        "Metrik_lensa": ml,
                        "Bahasa": bahasa,
                        "Periode": periode,
                        "Nilai": int(v),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=["Metrik_lensa", "Bahasa", "Periode", "Nilai"])
    df = pd.DataFrame(rows)
    order_labels = [label_map.get(k, k) for k in metric_keys]
    df["Metrik_lensa"] = pd.Categorical(
        df["Metrik_lensa"], categories=order_labels, ordered=True
    )
    df["Bahasa"] = pd.Categorical(df["Bahasa"], categories=["ID", "EN"], ordered=True)
    df["Periode"] = pd.Categorical(
        df["Periode"], categories=["Backup", "Live"], ordered=True
    )
    return df.sort_values(["Periode", "Metrik_lensa", "Bahasa"])


def _id_en_grouped_bar_chart(df: pd.DataFrame, title: str) -> alt.Chart | None:
    """Batang berpasangan ID vs EN; dua kolom Backup | Live."""
    if df.empty:
        return None
    y_order = list(df["Metrik_lensa"].cat.categories)
    n_met = len(y_order)
    h = min(max(n_met * 40 + 80, 200), 480)

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=2)
        .encode(
            x=alt.X(
                "Nilai:Q",
                title="Jumlah",
                scale=alt.Scale(zero=True, nice=True),
                axis=alt.Axis(format="~s", labelFontSize=11),
            ),
            y=alt.Y("Metrik_lensa:N", sort=y_order, title=None, axis=alt.Axis(labelFontSize=11)),
            color=alt.Color(
                "Bahasa:N",
                title="Instance",
                scale=alt.Scale(domain=["ID", "EN"], range=["#c2410c", "#1d4ed8"]),
                legend=alt.Legend(orient="bottom", direction="horizontal"),
            ),
            yOffset=alt.YOffset("Bahasa:N", sort=["ID", "EN"]),
            column=alt.Column(
                "Periode:N",
                sort=["Backup", "Live"],
                header=alt.Header(titleOrient="bottom", labelFontSize=12),
            ),
            tooltip=[
                alt.Tooltip("Metrik_lensa:N", title="Metrik"),
                alt.Tooltip("Periode:N", title="Sumber"),
                alt.Tooltip("Bahasa:N", title="Bahasa"),
                alt.Tooltip("Nilai:Q", title="Nilai", format=","),
            ],
        )
        .properties(width=320, height=h, title=alt.TitleParams(text=title, anchor="start", fontSize=14))
        .configure_view(stroke=None)
        .configure_facet(spacing=28)
    )
    return chart


def _render_id_en_cross_comparison(
    selected_bundle_root: Path | None,
    custom_before_root: str | None,
) -> None:
    st.markdown("### Pembandingan Indonesia (ID) vs English (EN)")
    st.caption(
        "Satu baseline untuk **kedua** bahasa: angka **backup** dari folder yang sama (sidebar); "
        "**live** dari `LightRAG-id` vs `LightRAG-en`. Kolom *Selisih live* = ID − EN."
    )

    bid = _resolve_before_rag_dir(selected_bundle_root, custom_before_root, "id")
    ben = _resolve_before_rag_dir(selected_bundle_root, custom_before_root, "en")

    after_id = load_rag_storage_stats(lightrag_live_rag_storage("id"))
    after_en = load_rag_storage_stats(lightrag_live_rag_storage("en"))

    before_id = load_rag_storage_stats(bid) if bid else None
    before_en = load_rag_storage_stats(ben) if ben else None
    if before_id is not None and before_id.error:
        before_id = None
    if before_en is not None and before_en.error:
        before_en = None

    ext_id_b = load_extended_kg_stats(bid) if bid else None
    ext_en_b = load_extended_kg_stats(ben) if ben else None
    if ext_id_b is not None and ext_id_b.error:
        ext_id_b = None
    if ext_en_b is not None and ext_en_b.error:
        ext_en_b = None

    ext_id_l = load_extended_kg_stats(lightrag_live_rag_storage("id"))
    ext_en_l = load_extended_kg_stats(lightrag_live_rag_storage("en"))

    # Ringkasan live ID vs EN
    c1, c2, c3, c4 = st.columns(4)
    if not after_id.error and not after_en.error:
        c1.metric("Total dokumen (ID live)", f"{after_id.total_docs:,}")
        c2.metric("Total dokumen (EN live)", f"{after_en.total_docs:,}")
        c3.metric(
            "Node GraphML (ID live)",
            f"{ext_id_l.graphml_nodes:,}"
            if not ext_id_l.error and ext_id_l.graphml_nodes >= 0
            else "—",
        )
        c4.metric(
            "Node GraphML (EN live)",
            f"{ext_en_l.graphml_nodes:,}"
            if not ext_en_l.error and ext_en_l.graphml_nodes >= 0
            else "—",
        )
    else:
        c1.info("Data live ID/EN tidak lengkap untuk ringkasan.")

    st.markdown("#### Tabel: dokumen (ID vs EN)")
    tbl_doc = _wide_id_en_doc_table(
        before_id,
        before_en,
        None if after_id.error else after_id,
        None if after_en.error else after_en,
    )
    st.dataframe(
        tbl_doc,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID backup": st.column_config.NumberColumn(format="%d"),
            "EN backup": st.column_config.NumberColumn(format="%d"),
            "ID live": st.column_config.NumberColumn(format="%d"),
            "EN live": st.column_config.NumberColumn(format="%d"),
            "Selisih live (ID−EN)": st.column_config.NumberColumn(format="%d"),
        },
    )

    _DOC_CHART_KEYS = [
        "Total dokumen",
        "WikiEval total",
        "Dokumen lain (non-WikiEval path)",
        "Total chunks (sum chunks_count)",
    ]
    long_doc = _long_id_en_for_chart(tbl_doc, _DOC_CHART_LABEL, _DOC_CHART_KEYS)
    ch_doc = _id_en_grouped_bar_chart(
        long_doc,
        "Dokumen: batang berpasangan ID vs EN (Backup | Live)",
    )
    if ch_doc is not None:
        st.caption(
            "**Diagram:** dua kolom = snapshot **Backup** vs **Live**; warna **oranye = ID**, **biru = EN**."
        )
        st.altair_chart(ch_doc, use_container_width=True)

    st.markdown("#### Tabel: KG / VDB / GraphML (ID vs EN)")
    tbl_kg = _wide_id_en_kg_table(ext_id_b, ext_en_b, ext_id_l, ext_en_l)
    st.dataframe(
        tbl_kg,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID backup": st.column_config.NumberColumn(format="%d"),
            "EN backup": st.column_config.NumberColumn(format="%d"),
            "ID live": st.column_config.NumberColumn(format="%d"),
            "EN live": st.column_config.NumberColumn(format="%d"),
            "Selisih live (ID−EN)": st.column_config.NumberColumn(format="%d"),
        },
    )

    _KG_CHART_KEYS = [
        "GraphML nodes (<node id=)",
        "GraphML edges (<edge source=)",
        "VDB entities (embedding data[])",
        "VDB relationships (data[])",
    ]
    long_kg = _long_id_en_for_chart(tbl_kg, _KG_CHART_LABEL, _KG_CHART_KEYS)
    ch_kg = _id_en_grouped_bar_chart(
        long_kg,
        "KG & vektor: batang berpasangan ID vs EN (Backup | Live)",
    )
    if ch_kg is not None:
        st.caption("Empat metrik utama untuk membandingkan **skala graf** antar bahasa.")
        st.altair_chart(ch_kg, use_container_width=True)

    st.markdown("---")


def _resolve_before_rag_dir(
    bundle_root: Path | None,
    custom_before_root: str | None,
    locale: str,
) -> Path | None:
    if custom_before_root and custom_before_root.strip():
        root = Path(custom_before_root.strip()).expanduser()
        if not root.is_dir():
            return None
        d = resolve_locale_rag_dir(root, locale)
        if d is not None:
            return d
        nested = root / f"lightrag-{locale}" / "rag_storage"
        if (nested / "kv_store_doc_status.json").is_file():
            return nested
        if (root / "kv_store_doc_status.json").is_file():
            return root
        return None
    if bundle_root is None:
        return None
    return resolve_locale_rag_dir(bundle_root, locale)


def _render_locale_block(
    locale_label: str,
    locale_code: str,
    before_dir: Path | None,
    caption_before: str,
    caption_after: str,
) -> None:
    st.subheader(locale_label)

    if before_dir is None:
        st.warning("Tidak ada folder rag_storage yang valid untuk snapshot **Sebelum**.")
        before_doc = RagStorageStats(
            0, 0, 0, 0, 0, 0, 0, "", error="Path baseline tidak ditemukan"
        )
        before_ext = ExtendedKGStats(
            -1, -1, -1, -1, -1, -1, -1, "", error="Path baseline tidak ditemukan"
        )
    else:
        before_doc = load_rag_storage_stats(before_dir)
        if before_doc.error:
            st.error(f"{before_doc.error} — `{before_doc.source_path}`")
        before_ext = load_extended_kg_stats(before_dir)

    after_dir = lightrag_live_rag_storage(locale_code)
    after_doc = load_rag_storage_stats(after_dir)
    if after_doc.error:
        st.error(f"{after_doc.error} — `{after_doc.source_path}`")
    after_ext = load_extended_kg_stats(after_dir)

    st.markdown(
        """
**Cara membaca analisis ini**

1. **Sebelum** = snapshot baseline dari folder backup (mis. injeksi awal WikiEval). **Sesudah** = isi `rag_storage` pada instance ini *sekarang* (setelah retrieval, injeksi agen, dll.).
2. **Dokumen** = satu entri di `kv_store_doc_status.json` per dokumen yang masuk LightRAG. WikiEval v1/v2 mengikuti pola path `wikieval/.../v1|v2`. Angka lain biasanya dari injeksi pipeline.
3. **KG / VDB / GraphML** = ringkasan dari *file export* lokal (bukan langsung dari UI Neo4j). Node/edge GraphML sejajar dengan struktur graf yang dipakai LightRAG untuk analisis offline.
        """
    )
    st.caption(caption_before)
    st.caption(caption_after)

    st.markdown("---")
    st.markdown("#### 1. Indeks dokumen (`kv_store_doc_status`)")

    if before_dir and not before_doc.error and not after_doc.error:
        st.success(
            "Fokus: **apakah jumlah dokumen dan injeksi non-WikiEval bertambah** setelah eksperimen?"
        )
        _metrics_headline_doc(before_doc, after_doc)
        tbl = _comparison_table_doc(before_doc, after_doc)
        st.dataframe(
            tbl,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Sebelum": st.column_config.NumberColumn(format="%d"),
                "Sesudah": st.column_config.NumberColumn(format="%d"),
                "Selisih": st.column_config.NumberColumn(format="%d"),
            },
        )
        df_chart = _long_df_for_chart(tbl, _DOC_CHART_LABEL)
        ch = _dumbbell_chart(
            df_chart,
            "Perbandingan dokumen: garis menghubungkan backup → live",
        )
        if ch is not None:
            st.caption(
                "**Diagram:** titik **biru** = backup, **hijau** = live. Garis menunjukkan arah perubahan pada metrik yang sama."
            )
            st.altair_chart(ch, use_container_width=True)
    else:
        st.info("Data dokumen tidak lengkap (Sebelum atau Sesudah error).")

    with st.expander("Path file (debug)"):
        if before_dir and not before_doc.error:
            st.code(before_doc.source_path, language="text")
        if not after_doc.error:
            st.code(after_doc.source_path, language="text")

    st.markdown("---")
    st.markdown("#### 2. Knowledge graph & vektor (export file)")

    st.success(
        "Fokus: **skala graf dan indeks vektor** (node/edge GraphML, entitas & relasi di VDB) "
        "membesar atau mengecil setelah eksperimen."
    )

    if before_dir and not before_ext.error and not after_ext.error:
        _metrics_headline_kg(before_ext, after_ext)
        tbl_kg = _comparison_table_kg(before_ext, after_ext)
        if tbl_kg.empty:
            st.warning("Tidak ada metrik KG dengan file lengkap di kedua sisi.")
        else:
            st.dataframe(
                tbl_kg,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Sebelum": st.column_config.NumberColumn(format="%d"),
                    "Sesudah": st.column_config.NumberColumn(format="%d"),
                    "Selisih": st.column_config.NumberColumn(format="%d"),
                },
            )
            df_kg = _long_df_for_chart(tbl_kg, _KG_CHART_LABEL)
            ch_kg = _dumbbell_chart(
                df_kg,
                "Perbandingan KG & VDB: backup → live",
            )
            if ch_kg is not None:
                st.caption(
                    "Metrik ini dihitung dari JSON VDB + `graph_chunk_entity_relation.graphml` di folder yang sama."
                )
                st.altair_chart(ch_kg, use_container_width=True)
    else:
        st.info("Data KG tidak lengkap (Sebelum atau Sesudah error / file hilang).")

    st.markdown("---")
    st.caption(
        "Baseline disarankan: `data/backups/lightrag_storage_backup_init_100_context` "
        "(lihat `README.txt` di folder tersebut)."
    )


def render_lightrag_tab(
    selected_bundle_root: Path | None,
    custom_before_root: str | None = None,
) -> None:
    st.header("Analisis LightRAG: Sebelum vs Sesudah")
    st.markdown(
        """
Perbandingan **baseline backup** dengan **penyimpanan live** per bahasa (ID / EN).
Di bawah: ringkasan **ID vs EN** sekaligus; lalu detail per bahasa di tab.
        """
    )

    _render_id_en_cross_comparison(selected_bundle_root, custom_before_root)

    st.markdown("### Detail per bahasa")
    tab_id, tab_en = st.tabs(
        ["Indonesia (50 pertanyaan)", "English (50 pertanyaan)"]
    )

    with tab_id:
        bdir = _resolve_before_rag_dir(
            selected_bundle_root, custom_before_root, "id"
        )
        if (
            custom_before_root
            and custom_before_root.strip()
            and bdir is None
        ):
            st.error(
                f"Override path tidak berisi `lightrag-id` yang valid: `{custom_before_root.strip()}`"
            )
        caption_b = (
            "**Backup:** snapshot baseline untuk `lightrag-id` (contoh folder `.../lightrag-id/` di `data/backups/`)."
        )
        caption_a = (
            "**Live:** `LightRAG/LightRAG-id/data/rag_storage/` setelah menjalankan eksperimen pada instance Indonesia."
        )
        _render_locale_block(
            "Bahasa Indonesia (`LightRAG-id`)",
            "id",
            bdir,
            caption_b,
            caption_a,
        )

    with tab_en:
        bdir = _resolve_before_rag_dir(
            selected_bundle_root, custom_before_root, "en"
        )
        if (
            custom_before_root
            and custom_before_root.strip()
            and bdir is None
        ):
            st.error(
                f"Override path tidak berisi `lightrag-en` yang valid: `{custom_before_root.strip()}`"
            )
        caption_b = "**Backup:** snapshot baseline untuk `lightrag-en`."
        caption_a = "**Live:** `LightRAG/LightRAG-en/data/rag_storage/`."
        _render_locale_block(
            "English (`LightRAG-en`)",
            "en",
            bdir,
            caption_b,
            caption_a,
        )


def render_lightrag_sidebar() -> tuple[Path | None, str]:
    """Returns (selected bundle root path, optional custom override text)."""
    st.header("LightRAG — baseline Sebelum")
    choices = list_before_backup_choices()
    label_to_path = {label: p for label, p in choices}

    if not choices:
        st.caption("Tidak ada backup di `data/backups/` atau `LightRAG/backups/`.")
        sel_path: Path | None = None
    else:
        labels = [c[0] for c in choices]
        default_l = default_before_backup_label(choices)
        idx = labels.index(default_l) if default_l in labels else 0
        picked = st.selectbox(
            "Sumber snapshot Sebelum",
            options=labels,
            index=idx,
            help=(
                "Default: `lightrag_storage_backup_init_100_context` jika ada (baseline WikiEval). "
                "Struktur flat `lightrag-en/` / `lightrag-id/` didukung."
            ),
        )
        sel_path = label_to_path[picked]

    custom = st.text_input(
        "Override path (opsional)",
        value="",
        placeholder="Contoh: .../data/backups/lightrag_storage_backup_init_100_context",
        help="Menggantikan pilihan di atas. Isi folder bundle (berisi lightrag-en & lightrag-id) atau satu rag_storage.",
    )
    if st.button("Muat ulang daftar backup"):
        st.rerun()

    return sel_path, custom
