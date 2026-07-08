# Faithfulness sampling (data terbaru) vs Images_Faithfulness_10

## Ringkasan

Dokumen ini mengambil sampling dari data trace terbaru (folder `Eval_Data/Traces/`) untuk workflow `StoryGenerationWorkflow` (Agentic AI), lalu membandingkannya dengan kumpulan HTML visualisasi pada `Images_Faithfulness_10/` sebagai data lama.

Fokus perbandingan:

- `fables_faithfulness` (faithfulness level-trace)
- `geval_coherence_normalized` (GEval level-trace)
- Jumlah klaim dan distribusi 4 label FABLES: `FAITHFUL`, `UNFAITHFUL`, `PARTIAL_SUPPORT`, `CANT_VERIFY`

## Sumber data

- **Trace export (terbaru yang dipakai)**: `Eval_Data/Traces/exports_1777657958855-lf-traces-export-cmiotu4on0006s007ssffnxlo.csv`
- **Data lama (10 file HTML)**: `Images_Faithfulness_10/*.html`

## Definisi sampling

- **Skor utama**: `fables_faithfulness` (skor level-trace).
  - Kolom `Faithfulness` pada export berisi nilai kosong (`""`) untuk seluruh baris, sehingga tidak dipakai.
- **Kriteria sampling**:
  - Sampling dilakukan **per bahasa** (EN dan ID) sehingga total trace sampling = 10.
  - Untuk masing-masing bahasa:
    - **Prioritas utama**: `fables_faithfulness`, lalu `ragas_standard_faithfulness`
    - **Prioritas sampingan**: `geval_coherence_normalized` (hanya untuk tie-break)
    - **min (2)**: 2 trace dengan nilai terendah berdasarkan urutan prioritas di atas
    - **median (1)**: 1 trace yang paling dekat ke median untuk `fables_faithfulness`, lalu `ragas_standard_faithfulness`, lalu `geval_coherence_normalized`
    - **max (2)**: 2 trace dengan nilai tertinggi berdasarkan urutan prioritas di atas

Catatan: pada export ini, median dan maksimum sama-sama bernilai `1.0` karena banyak skor yang sama (ties).

## Hasil sampling (data terbaru, 10 trace)

### EN (5 trace)

| subset | trace_id | fables_faithfulness | ragas_standard_faithfulness | geval_coherence_raw | claims_total_new | new_F | new_U | new_P | new_CV | match di Images_Faithfulness_10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| min | `008acc0c69156cfa6b41d704be559dfd` | 0.81315 | 0.74375 | 5 | 12 | 9 | 2 | 1 | 0 | `Images_Faithfulness_10/story_05_EN_SKOR_RENDAH.html` |
| min | `d9c3d07ec4b353dda2e009675f2c3fab` | 0.9 | 0.9 | 4.8 | 10 | 9 | 1 | 0 | 0 | tidak ada |
| median | `b9d4c31ba88cbe9a2a25255b9f0a23c8` | 1.0 | 0.9474 | 4.4 | 19 | 18 | 0 | 1 | 0 | tidak ada |
| max | `da803e21e5a8469c971d0bef5380ce6d` | 1.0 | 1.0 | 4.8 | 3 | 3 | 0 | 0 | 0 | tidak ada |
| max | `6b08ccdcfdc2b16e2f8428eed9a22902` | 1.0 | 1.0 | 4.8 | 20 | 20 | 0 | 0 | 0 | tidak ada |

### ID (5 trace)

| subset | trace_id | fables_faithfulness | ragas_standard_faithfulness | geval_coherence_raw | claims_total_new | new_F | new_U | new_P | new_CV | match di Images_Faithfulness_10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| min | `0ed7034ea53c0c3a0d52c79785713ca4` | 0.6667 | 0.6667 | 4 | 6 | 4 | 2 | 0 | 0 | tidak ada |
| min | `3188c12432f8641d9dc8ae0900fcc1b7` | 0.8706285714285713 | 0.8706285714285713 | 4.8 | 17 | 15 | 2 | 0 | 0 | `Images_Faithfulness_10/story_10_ID_SKOR_RENDAH.html` |
| median | `b866c66ab2f43a8ae7c5b4fa5bc7fd6f` | 1.0 | 1.0 | 4 | 7 | 7 | 0 | 0 | 0 | tidak ada |
| max | `e47ebbd6ee5534bf3aa60ed2e4809f6e` | 1.0 | 1.0 | 5 | 3 | 3 | 0 | 0 | 0 | tidak ada |
| max | `6069a9bcab2aad38b2893bda7c9a3dc6` | 1.0 | 1.0 | 5 | 20 | 20 | 0 | 0 | 0 | tidak ada |

## Data lama: `Images_Faithfulness_10` (10 trace) dengan jumlah klaim dan distribusi 4 label

Tabel berikut mengambil dari HTML (jumlah klaim dan jumlah per label), lalu menambahkan `fables_faithfulness` dan `geval_coherence_normalized` dari export trace terbaru untuk trace id yang sama.

| trace_id | lang | bucket_old | claims_total | FAITHFUL | UNFAITHFUL | PARTIAL_SUPPORT | CANT_VERIFY | latest_fables_faithfulness | latest_geval_coherence_normalized |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `008acc0c69156cfa6b41d704be559dfd` | EN | RENDAH | 10 | 7 | 2 | 1 | 0 | 0.81315 | 0.94 |
| `470b2951081041b0d274418855feaf8b` | EN | RENDAH | 10 | 8 | 0 | 0 | 2 | 1.0 | 0.92 |
| `1a8da16ce073ef44f854dfc3f5ab61b2` | EN | SEDANG | 10 | 10 | 0 | 0 | 0 | 1.0 | 0.84 |
| `45492ab588212aa547c6b58f90382ed0` | EN | TINGGI | 8 | 8 | 0 | 0 | 0 | 1.0 | 0.96 |
| `52625d964bdcdc05a3f627031fd1d82d` | EN | TINGGI | 5 | 5 | 0 | 0 | 0 | 1.0 | 0.96 |
| `075106eeab95af03c5fe26ba4196921b` | ID | RENDAH | 10 | 2 | 0 | 1 | 7 | 1.0 | 0.94 |
| `3188c12432f8641d9dc8ae0900fcc1b7` | ID | RENDAH | 10 | 8 | 2 | 0 | 0 | 0.8706285714285713 | 0.92 |
| `519e0ec0815923810ca011413dff38bf` | ID | SEDANG | 6 | 6 | 0 | 0 | 0 | 1.0 | 0.9 |
| `32ce238e5589908aa32270e04f34ecb9` | ID | TINGGI | 8 | 8 | 0 | 0 | 0 | 1.0 | 0.96 |
| `fb1de18543c10f743fcdf53f13dee1ab` | ID | TINGGI | 8 | 7 | 0 | 1 | 0 | 1.0 | 0.98 |

## Perbandingan claims_total dan label counts: lama (HTML) vs baru (Eval_Data/Observations)

Bagian ini membandingkan `claims_total` serta distribusi 4 label yang diekstrak dari:

- **Lama**: HTML `Images_Faithfulness_10/*.html`
- **Baru**: `Eval_Data/Observations/exports_1777658021040-lf-observations-export-cmiotu4on0006s007ssffnxlo.jsonl` dengan agregasi semua generation `fables_verify_all_claims*` untuk tiap `traceId`

| trace_id | claims_old | claims_new | delta | old_F | old_U | old_P | old_CV | new_F | new_U | new_P | new_CV |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `008acc0c69156cfa6b41d704be559dfd` | 10 | 12 | 2 | 7 | 2 | 1 | 0 | 9 | 2 | 1 | 0 |
| `075106eeab95af03c5fe26ba4196921b` | 10 | 16 | 6 | 2 | 0 | 1 | 7 | 6 | 0 | 1 | 9 |
| `1a8da16ce073ef44f854dfc3f5ab61b2` | 10 | 25 | 15 | 10 | 0 | 0 | 0 | 25 | 0 | 0 | 0 |
| `3188c12432f8641d9dc8ae0900fcc1b7` | 10 | 17 | 7 | 8 | 2 | 0 | 0 | 15 | 2 | 0 | 0 |
| `32ce238e5589908aa32270e04f34ecb9` | 8 | 8 | 0 | 8 | 0 | 0 | 0 | 8 | 0 | 0 | 0 |
| `45492ab588212aa547c6b58f90382ed0` | 8 | 8 | 0 | 8 | 0 | 0 | 0 | 8 | 0 | 0 | 0 |
| `470b2951081041b0d274418855feaf8b` | 10 | 16 | 6 | 8 | 0 | 0 | 2 | 14 | 0 | 0 | 2 |
| `519e0ec0815923810ca011413dff38bf` | 6 | 6 | 0 | 6 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| `52625d964bdcdc05a3f627031fd1d82d` | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| `fb1de18543c10f743fcdf53f13dee1ab` | 8 | 8 | 0 | 7 | 0 | 1 | 0 | 8 | 0 | 0 | 0 |

### Daftar cerita yang perlu dilabeli ulang atau ditambahkan klaim

Bagian ini menandai trace pada `Images_Faithfulness_10/` yang jumlah klaimnya pada `Eval_Data/Observations` **lebih besar** daripada yang tampil di HTML lama. Untuk trace berikut, klaim tambahan perlu ditambahkan lalu dilabeli (tanpa asumsi label terlebih dahulu).

- **`story_05_EN_SKOR_RENDAH.html` (trace `008acc0c69156cfa6b41d704be559dfd`)**: klaim 10 -> 12 (tambah 2). Perubahan label counts: FAITHFUL 7 -> 9.
- **`story_09_ID_SKOR_RENDAH.html` (trace `075106eeab95af03c5fe26ba4196921b`)**: klaim 10 -> 16 (tambah 6). Perubahan label counts: FAITHFUL 2 -> 6, CANT_VERIFY 7 -> 9.
- **`story_03_EN_SKOR_SEDANG.html` (trace `1a8da16ce073ef44f854dfc3f5ab61b2`)**: klaim 10 -> 25 (tambah 15). Perubahan label counts: FAITHFUL 10 -> 25.
- **`story_10_ID_SKOR_RENDAH.html` (trace `3188c12432f8641d9dc8ae0900fcc1b7`)**: klaim 10 -> 17 (tambah 7). Perubahan label counts: FAITHFUL 8 -> 15.
- **`story_04_EN_SKOR_RENDAH.html` (trace `470b2951081041b0d274418855feaf8b`)**: klaim 10 -> 16 (tambah 6). Perubahan label counts: FAITHFUL 8 -> 14.
- **`story_06_ID_SKOR_TINGGI.html` (trace `fb1de18543c10f743fcdf53f13dee1ab`)**: jumlah klaim sama (8), tetapi distribusi label berubah di observasi baru: PARTIAL_SUPPORT 1 -> 0, FAITHFUL 7 -> 8. Perlu cek ulang klaim yang sebelumnya berlabel PARTIAL_SUPPORT.

## Perbandingan sampling terbaru dengan data lama

Jumlah trace sampling (terbaru) yang punya pasangan HTML di `Images_Faithfulness_10/` adalah 7 dari 10.

### 1) `008acc0c69156cfa6b41d704be559dfd` (EN, label HTML: SKOR RENDAH)

- **File**: `Images_Faithfulness_10/story_05_EN_SKOR_RENDAH.html`
- **Skor**: `fables_faithfulness = 0.81315`
- **GEval**: `geval_coherence_normalized = 0.94`
- **Jumlah klaim**: 10
- **Distribusi 4 label (dari HTML)**:
  - `FAITHFUL`: 7
  - `UNFAITHFUL`: 2
  - `PARTIAL_SUPPORT`: 1
  - `CANT_VERIFY`: 0

### 2) `075106eeab95af03c5fe26ba4196921b` (ID, label HTML: SKOR RENDAH)

- **File**: `Images_Faithfulness_10/story_09_ID_SKOR_RENDAH.html`
- **Skor**: `fables_faithfulness = 1.0`
- **GEval**: `geval_coherence_normalized = 0.94`
- **Jumlah klaim**: 10
- **Distribusi 4 label (dari HTML)**:
  - `FAITHFUL`: 2
  - `UNFAITHFUL`: 0
  - `PARTIAL_SUPPORT`: 1
  - `CANT_VERIFY`: 7

### 3) `fb1de18543c10f743fcdf53f13dee1ab` (ID, label HTML: SKOR TINGGI)

- **File**: `Images_Faithfulness_10/story_06_ID_SKOR_TINGGI.html`
- **Skor**: `fables_faithfulness = 1.0`
- **GEval**: `geval_coherence_normalized = 0.98`
- **Jumlah klaim**: 8
- **Distribusi 4 label (dari HTML)**:
  - `FAITHFUL`: 7
  - `UNFAITHFUL`: 0
  - `PARTIAL_SUPPORT`: 1
  - `CANT_VERIFY`: 0

## Catatan lanjutan

- Bila sampling perlu benar-benar spesifik subset tertentu (misal hanya trace dengan konfigurasi writer tertentu), marker filter perlu dipastikan dulu dari field `metadata` atau `tags` pada export. Pada export ini, `metadata.active_writers` bernilai `\"[\\\"text\\\"]\"` untuk seluruh trace.
