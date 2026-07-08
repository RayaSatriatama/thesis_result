# Streamlit dashboard (Faithfulness & LightRAG)

Modular Streamlit app for thesis metrics: **Faithfulness** (FABLES / RAGAS, confusion matrix, HTML claim viewer), **WikiEval** EDA (mirror `notebooks/01_analisis_dataset_wikieval.ipynb`), and **LightRAG** before/after comparison using `kv_store_doc_status.json`.

**FABLES** metrics follow **Kim et al. (2024), [arXiv:2404.01261v2](https://arxiv.org/abs/2404.01261)** (four claim labels: Faithful, Unfaithful, Partial support, Can't verify; the 2×2 matrix excludes Partial support and Can't verify, per §4). See `lib/faithfulness_metrics.py`.

**RAGAS-style** confusion in the Faithfulness tab uses **every** claim: **pred positive = `FAITHFUL` only**; **`UNFAITHFUL` + `PARTIAL_SUPPORT` + `CANT_VERIFY`** are **pred negative** (aligned with strict trace score `ragas_standard_faithfulness`, faithful / total).

## Setup

Use a virtual environment (project root or any venv):

```bash
cd Streamlit
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install streamlit pandas altair
```

## Run

```bash
cd Streamlit
streamlit run app.py
```

Paths resolve relative to the **Skripsi repo root** (parent of `Streamlit/`): `Images_Faithfulness_10/`, `LightRAG/LightRAG-en|id/data/rag_storage/`, `LightRAG/backups/`.

## WikiEval tab

- Tab **WikiEval** memuat `dataset/wikiEval_all.json` (50 item EN). Logika disalin dari **`notebooks/01_analisis_dataset_wikieval.ipynb`**: validasi skema, missing summary, deduplikasi, statistik panjang kata, tipe pertanyaan, boxplot kualitas jawaban, cosine/Jaccard antara `context_v1` vs `context_v2`, dan diagram tambahan (scatter, 10 cosine terendah).
- Implementasi data: `lib/wikieval_dataset.py`; UI: `tabs/wikieval.py` (visualisasi **Altair**). Jika JSON belum ada, tab menampilkan pesan dan petunjuk export dari HuggingFace `vibrantlabsai/WikiEval`.

## Faithfulness tab & HTML assets

- **Bahasa:** radio **Semua / Bahasa Indonesia / Bahasa Inggris** menyaring metrik klaim (subset jejak), daftar HTML (`*_ID_*` vs `*_EN_*`), dan statistik skor trace — selaras urutan **EN story_01–05** lalu **ID story_06–10** di `generate_faithfulness_images_10.py`. `story_idx` di `lib/faithfulness_metrics.py` mempertahankan nomor cerita untuk `MANUAL_HALLUCINATED`, `MANUAL_GT_FAITHFUL` (GT positif tanpa mengubah label `PARTIAL_SUPPORT` di HTML), dan `FABLES_VERDICT_OVERRIDE`.
- **Skor Faithfulness (trace):** tabel ringkas **n, mean, median, std, min, Q25, Q75, max** untuk `ragas_standard_faithfulness`, `fables_faithfulness`, dan rata-rata keduanya; tiga diagram distribusi (Altair) selaras **B. Faithfulness** di `notebooks/02_analisis_evaluasi_model.ipynb` — histogram **bins≈20**, warna **darkorchid**, grid terang, plus **KDE** (setara `sns.histplot(..., kde=True)`). **Kesimpulan** skripsi ditampilkan **paling bawah** setelah panel HTML.
- The tab embeds pre-generated files under repo root **`Images_Faithfulness_10/*.html`** (and optional PNGs). Each file shows **the full critic `contexts` list** from Langfuse observation **`ragas_context_relevance`** (same strings passed to **RAGAS Context Relevance** and **FABLES**, including the planner chunk `## Rencana Cerita ...` when present), plus field **`user_input`** (`story_question`). **True-positive FAITHFUL** claims always have **highlight + `Ref:Klaim N`** in the context column; **`MANUAL_GT_FAITHFUL`** claims where the model verdict is not `FAITHFUL` (e.g. `PARTIAL_SUPPORT`) get the same **Ref** + context highlight plus a **“Koreksi audit (false negative)”** box and an extended verdict badge (**FALSE NEGATIVE (GT: FAITHFUL)**). **False positives** (manual overlay) include an **“Evaluasi manual vs konteks”** paragraph tying the error to planner vs KG vs web chunks. Use the **slider** “Tinggi panel HTML” to avoid a cramped iframe.
- **10-trace cohort (Apr 2026):** see `docs/faithfulness_manual_reaudit.md` for trace IDs ↔ story index and manual FP/TN notes. Metrics use `lib/faithfulness_metrics.py` (`MANUAL_HALLUCINATED`, `MANUAL_GT_FAITHFUL`, `FABLES_VERDICT_OVERRIDE` ↔ `generate_faithfulness_images_10.py`). Context highlights: TF-IDF argmax, optional `tfidf_anchor_override` in the generator.
- **Regenerate** after exporting new observations (`Eval_Data/Agentic-AI-LightRAG/Observations/*.jsonl`) and traces CSV (`Eval_Data/Agentic-AI-LightRAG/Traces/*.csv`). From repo root (venv recommended):

```bash
pip install html2image pillow scikit-learn pandas  # if not already in your env
python generate_faithfulness_images_10.py
```

- **Manual text dump** (full contexts per trace): `python dump_claims_for_review.py` → `manual_review_dump.txt`.

## LightRAG tab & backups

- **Sesudah (live):** reads current `LightRAG/LightRAG-en/data/rag_storage` and `LightRAG/LightRAG-id/data/rag_storage`.
- **Sebelum (baseline):** sidebar lists `data/backups/lightrag_storage_backup_*` first, then `LightRAG/backups/*`. Default is **`lightrag_storage_backup_init_100_context`** when present (flat `lightrag-en/` and `lightrag-id/` layout; see that folder’s `README.txt`). The tab opens with **ID vs EN** wide tables (ID backup | EN backup | ID live | EN live | Selisih live) and **grouped bar charts** (two facets: Backup / Live), then per-locale tabs with dumbbell Sebelum→live charts.
- For snapshots taken **from Docker**, run [`LightRAG/scripts/backup_lightrag_from_docker.sh`](../LightRAG/scripts/backup_lightrag_from_docker.sh) and select that bundle or set **Override path**.

Override the bundle root via the sidebar **Override path** if needed (folder containing `lightrag-en/rag_storage` and `lightrag-id/rag_storage`, or a single `rag_storage` directory).

**Important:** Take a new backup before overwriting `rag_storage` if you need a faithful “Sebelum” snapshot for the experiment.

## Layout

| Path | Role |
|------|------|
| `app.py` | Entry: tabs + sidebar |
| `tabs/faithfulness.py` | Faithfulness UI |
| `tabs/wikieval.py` | WikiEval EDA (notebook 01) |
| `tabs/lightrag.py` | LightRAG ID/EN nested tabs |
| `lib/paths.py` | Repo-relative paths |
| `lib/wikieval_dataset.py` | Load / clean / similarity WikiEval |
| `lib/faithfulness_metrics.py` | Confusion-matrix metrics from Observations + manual FP map (sinkron `generate_faithfulness_images_10.py`) |
| `lib/lightrag_stats.py` | Metrics from `kv_store_doc_status.json` |
