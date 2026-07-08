# Manual re-audit of false-positive overlays (vs critic `contexts`)

Re-checked flagged claims against the **full** `contexts` list in `Images_Faithfulness_10` HTML (same as RAGAS/FABLES input). Overlays and `MANUAL_HALLUCINATED` in `Streamlit/lib/faithfulness_metrics.py` must stay in sync with `generate_faithfulness_images_10.py`.

## Cohort April 2026 (10 traces — setelah refresh Langfuse)

Urutan = `traces_to_run` dari `generate_faithfulness_images_10.py` (sampling `sampling_expert.get_latest_trace_df()`). Observations terbaru dipakai: `Eval_Data/Observations/*.jsonl` (mtime).

| Story | Trace ID | Bahasa | Kategori | Catatan audit singkat |
|-------|----------|--------|----------|------------------------|
| 01 | `45492ab588212aa547c6b58f90382ed0` | EN | SKOR TINGGI | Tidak ditambah FP manual pada audit ini. |
| 02 | `52625d964bdcdc05a3f627031fd1d82d` | EN | SKOR TINGGI | — |
| 03 | `1a8da16ce073ef44f854dfc3f5ab61b2` | EN | SKOR SEDANG | — |
| 04 | `470b2951081041b0d274418855feaf8b` | EN | SKOR RENDAH | Klaim 8 (DNA): `tfidf_anchor_override` **gi=32** (kalimat KG *genetic barcoding*), bukan gi=36 (*sister species* saja). |
| 05 | `008acc0c69156cfa6b41d704be559dfd` | EN | SKOR RENDAH | Gempa Hormozgan: klaim **3–4** `UNFAITHFUL` (beda angka magnitudo utama vs sumber); **8** tetap `PARTIAL_SUPPORT` di export, tetapi **`MANUAL_GT_FAITHFUL`** (bukti mendukung) → **FN** di matriks. Di HTML (`story_05_EN_SKOR_RENDAH.html`): badge **PARTIAL_SUPPORT — FALSE NEGATIVE (GT: FAITHFUL)**, kotak **Koreksi audit (false negative)**, highlight konteks + **Ref:Klaim 8** (sama jangkar kalimat global seperti Klaim 7). |
| 06 | `fb1de18543c10f743fcdf53f13dee1ab` | ID | SKOR TINGGI | Klaim 2 **benar** (jangkar ke Rencana [0] klimaks). Klaim 6: **`PARTIAL_SUPPORT`** (override `FABLES_VERDICT_OVERRIDE`: konteks “ide masakan”, bukan “resep” literal); catatan audit tetap di HTML. |
| 07 | `32ce238e5589908aa32270e04f34ecb9` | ID | SKOR TINGGI | — |
| 08 | `519e0ec0815923810ca011413dff38bf` | ID | SKOR SEDANG | — |
| 09 | `075106eeab95af03c5fe26ba4196921b` | ID | SKOR RENDAH | **FP manual:** klaim 1 saja (Skotlandia vs retrieval arkeologi ID). Klaim 5 **benar** menurut audit ulang (bukan FP). **TN:** banyak `CANT_VERIFY` + `PARTIAL_SUPPORT` klaim 6 — overlay hijau di HTML. |
| 10 | `3188c12432f8641d9dc8ae0900fcc1b7` | ID | SKOR RENDAH | Roanoke & Tar River → SAL: lihat **audit detail Story 10** di bawah; TN **6** & **8** (1900 vs fakta **1911**); jangkar **1** & **7** ke riset. |

**Metode ground truth FP:** verifikator LLM menandai FAITHFUL, tetapi klaim tidak terdukung kuat oleh **chunk riset / KG**; frasa yang sama boleh muncul di **Rencana Cerita [0]** — untuk tesis, itu tetap dihitung false positive terhadap bukti eksternal.

**Jangkar TF-IDF (highlight `Ref:Klaim N`):** default = argmax cosine TF-IDF per kalimat. Jika perlu, isi `tfidf_anchor_override` di `generate_faithfulness_images_10.py` (indeks kalimat global).

**Override label FABLES:** `FABLES_VERDICT_OVERRIDE` di `Streamlit/lib/faithfulness_metrics.py` (dipakai juga generator HTML + `calc_f1.py`).

**Matriks RAGAS-style (`compute_bundle_ragas`):** semua klaim masuk 2×2; **pred positif = `FAITHFUL` saja**; **`UNFAITHFUL` + `PARTIAL_SUPPORT` + `CANT_VERIFY`** = pred negatif (selaras `ragas_standard_faithfulness` = faithful / total).

### Story 10 — Roanoke and Tar River Railroad & Seaboard Air Line (trace `3188c12432f8641d9dc8ae0900fcc1b7`)

Pertanyaan pengguna: kapan **merger penuh** R&TRR ke jaringan SAL dan apa yang terjadi setelahnya. Fakta di **konteks [1], [2], KG [4]–[5]**: penggabungan **penuh** ke SAL pada **1911**; SAL sebagai entitas korporat terkait pembentukan **1900** (19 jalur di [2]).

| Klaim | Verdict FABLES | Audit |
|-------|----------------|--------|
| 1 | FAITHFUL | Proses integrasi bertahap: didukung **Rencana [0]** dan eksplisit di riset **[2]** (“dalam beberapa langkah”). Jangkar HTML: `tfidf_anchor_override` → kalimat riset [2], bukan hanya dialog Planner. |
| 2 | FAITHFUL | Anak perusahaan Seaboard and Roanoke: **[1], KG [4]–[6]**. |
| 3 | FAITHFUL | Terhubung di Boykins, Virginia: **[1], [2], KG**. |
| 4 | FAITHFUL | Akuisisi Murfreesboro 1893: **[1], KG [6]**. |
| 5 | FAITHFUL | Layanan Murfreesboro dihentikan 1897: **[1], KG [4]**. |
| 6 | UNFAITHFUL | **Benar negatif:** klaim menyatakan merger penuh **1900**; sumber memakai **1911**. Narasi klimaks **Planner [0]** bertentangan dengan fakta retrieval (common failure mode: tahun dari “SAL 1900” bercampur dengan tanggal merger jalur). |
| 7 | FAITHFUL | Akuisisi bertahap / pendahulu SAL termasuk **Raleigh & Gaston**: di **[3]** ada perjanjian Seaboard & Roanoke dengan **Raleigh & Gaston**; hubungan rantai ke R&TRR bersifat agregat (S&RR sebagai induk R&TRR). Jangkar diarahkan ke **[3]** agar tidak hanya mengutip Planner. |
| 8 | UNFAITHFUL | **Benar negatif:** sama seperti 6 — “1900 = selesai integrasi operasional di bawah bendera SAL” untuk R&TRR **tidak** didukung; merger penuh **1911**. |
| 9 | FAITHFUL | SAL jaringan besar terbentuk **1900**: **[2], [3]**. |
| 10 | FAITHFUL | SAL 1900 + **19** jalur: **[2]** (satu kalimat bersama klaim 9; override TF-IDF **gi** sama untuk 9 dan 10). |

**Bukan FP manual:** tidak ada klaim FAITHFUL yang ditandai halusinasi pada audit ini; **6** dan **8** adalah **UNFAITHFUL** yang **selaras bukti** (true negative). Catatan hijau “Evaluator Benar” di HTML: `correct_negative_claims` story **10** untuk klaim **6** dan **8**.

---

## Arsip — sampling sebelumnya (indeks cerita lama)

Bagian berikut mengacu ke **urutan 10 cerita lama** (sebelum resample CSV). Jangan memetakan nomor story langsung ke kohort baru tanpa cek trace ID.

## Story 4 (Dasypoda taxonomy) — relaxed FP

| Claim | Previous overlay | After re-audit |
|-------|------------------|----------------|
| 3 Taksonomi = ilmu klasifikasi | FP | **Removed** — bukan kutipan harfiah; didukung **inferensi** dari hierarki “taxonomic classification” (Kingdom→…) di konteks [1]; KG [2] menolak pertanyaan umum, bukan menyangkal klasifikasi spesies. |
| 4 Taksonomi & keanekaragaman hayati | FP | **Removed** — selain “biodiversity”, **Pesan Moral Planner [0]** (“observation… interconnected through evolutionary relationships”) mengikat pemahaman hubungan makhluk hidup. |
| 7 Kemiripan visual menyesatkan | FP | **Removed** — eksplisit di **Planner [0]** (“visual similarity can be misleading”). |
| 10 DNA / hubungan spesies | FP | **Removed** — didukung **KG [4]** (barcoding, sister species) dan **Planner** (“distinct genetic sequences” ↔ spesies terpisah namun erat terkait). |
| 1 Dr. Aris ahli entomologi | FP | **Removed** — **Planner [0]** menyebut “seasoned entomologist”; verifikasi terhadap seluruh `contexts` (termasuk rencana) mendukung FAITHFUL untuk fakta naratif tokoh. |
| 8 Sikat serbuk sari | FP | **Kept** — konteks “floral resources” tanpa frasa setara “rambut sikat”. |

## Story 7 (GPT-4) — corrected FP

| Claim | Previous overlay | After re-audit |
|-------|------------------|----------------|
| 7 Gambar bahan makanan → resep | FP | **Kept** — konteks menyebut makanan/masakan; **kata atau konsep “resep” tidak literal** di teks → tetap false positive vs konteks. |
| 2 Pemahaman + penalaran canggih | FP | **Kept** (alasan diperjelas) — “memahami/menulis lebih baik” ada; **“penalaran yang canggih”** tidak dikutip eksplisit. |

## Unchanged after re-audit

- **Story 2:** Klaim 3 (“tempat terbaik”) tetap FP.  
- **Story 5:** Klaim 3 (oranye di “kaki” vs inner hind legs) tetap FP (presisi morfologi).  
- **Stories 8–10:** FP tetap (planner vs KG; retrieval mismatch; durasi listrik).

Anchors `man_match` / `man4` (jika masih dipakai di revisi script): Story 4 — klaim 1 (entomologist), 3 (`taxonomic classification`), 4 (kalimat moral evolusi), 7, 10 (`distinct genetic sequences`). Story 7 klaim 7 **tanpa** anchor manual (tetap FP).

---

*Regenerasi HTML: `python generate_faithfulness_images_10.py` dari root repo Skripsi.*
