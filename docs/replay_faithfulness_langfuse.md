# Replay FABLES / RAGAS ke trace Langfuse (tanpa regenerasi cerita)

## Ringkasan

Skrip [`scripts/replay_faithfulness_langfuse.py`](../scripts/replay_faithfulness_langfuse.py) **secara default** hanya menjalankan ulang **FABLES** (ekstraksi klaim + verifikasi): **tidak** menjalankan `ragas_answer_relevancy` maupun `ragas_context_relevance`. Default memakai **`generation-update` / `span-update` in-place** pada **tiga id kanonik** (SPAN `fables_faithfulness` + dua generasi) — id dipilih sebagai **observasi paling awal** per nama bila ada duplikat (replay buruk sebelumnya sering menambah saudara kedua; pembaruan harus mengenai **original**, bukan duplikat terbaru).

Cerita (jawaban) diambil dari **`fables_verify_all_claims`** (`user_input`). **`contexts`** dari observasi itu bila ada; jika tidak, fallback ke span `ragas_context_relevance` / `fables_faithfulness` / `ragas_answer_relevancy` — lihat [`replay_faithfulness_io.py`](../scripts/lib/replay_faithfulness_io.py).

Opsi **`--full-ragas-replay`** mengembalikan perilaku lama: Answer Relevancy + Context Relevance + FABLES, induk = SPAN `critic_agent`, dan penghapusan seluruh set `OBS_NAMES_TO_REPLACE`.

**`--replace-fables-block`** (bersama **`--delete-old`**) menghapus seluruh blok FABLES di bawah SPAN **`ragas_evaluation`** yang sama dengan struktur asli: **`fables_faithfulness`** + **`fables_extract_claims`** + **`fables_verify_all_claims`**, lalu menjalankan FABLES lagi dengan **SPAN `fables_faithfulness` baru** (induk replay = `ragas_evaluation`). Payload cerita/konteks tetap diambil dari export seperti mode default. Tanpa `--delete-old`, skrip memperingatkan karena observasi lama akan bertumpuk.

**Menghindari dobel data:** Mode lama **`--fables-recreate-leaves` + `--delete-old`** menghapus leaf lalu membuat generasi **baru** — rawan duplikat jika `DELETE` meleset (id dari JSONL tidak sinkron dengan server). Default **in-place** tidak membuat id baru. Untuk blok baru di bawah RAGAS, gunakan **`--fetch-live --delete-old --replace-fables-block`** bila perlu.

**Timeline:** **Secara default** payload memakai **`startTime` / `endTime` dari export observasi** (JSONL atau hasil `--fetch-live`) untuk ketiga observasi FABLES. Gunakan **`--fables-timeline-wall-clock`** bila Anda sengaja ingin timestamp wall clock saat replay. **`--fables-update-in-place`** hanya penanda opsional (perilaku default sudah in-place); **`--fetch-live`** tetap disarankan jika export lokal ketinggalan.

**Penting — durasi di UI:** Pada **Langfuse upstream**, merge ingestion menandai **`start_time` observasi sebagai immutable** terhadap isi update (nilai di ClickHouse tidak diganti oleh `startTime` di update). Jika **`endTime`** dari replay lebih baru daripada nilai lama di merge, UI bisa menampilkan **start lama + finish baru** → durasi sangat panjang. Skrip menghindari fallback **`endTime` = sekarang** bila `startTime` sudah diisi, memakai timeline export yang **direkonsiliasi** (anak tidak melampaui span), dan saat export ada **tidak** memakai wall clock di detik “selesai” replay. Tetap: **`--fables-update-in-place` saja tidak memperbaiki** `start_time` yang sudah rusak di server tanpa **replace** atau **patch worker** (`start_time` dikeluarkan dari immutable di `worker/src/services/IngestionService/index.ts` pada build Anda bila ada).

**Skor FABLES:** `fables_faithfulness` dan `ragas_standard_faithfulness` ditulis **hanya di level trace** (bukan `observationId` pada span), agar tidak muncul sebagai badge pada span di UI.

**English:** Default FABLES replay is **in-place** updates on the **earliest** (canonical) span + two generations per name; `--fables-recreate-leaves --delete-old` is the legacy delete-and-recreate path; `--replace-fables-block --delete-old` removes the whole FABLES subtree and recreates under `ragas_evaluation`; `--full-ragas-replay` restores full RAGAS + FABLES under `critic_agent`. FABLES times default to the **export** timeline; use `--fables-timeline-wall-clock` for “now”. **Note:** vanilla Langfuse may keep immutable `start_time` on update unless the worker is patched (see above).

## Prasyarat

- Variabel lingkungan seperti aplikasi: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `OPENROUTER_API_KEY` (sama dengan inisialisasi RAGAS di [`CriticAgent`](../src/workflows/story_agent/agents/critic/agent.py)).
- Paket: `ragas`, `langfuse`, `httpx`, `openai`. Opsi `--traces-csv` memakai modul `csv` standar (tanpa pandas).

## Backup (wajib sebelum menulis ke Langfuse)

Dari root repositori:

```bash
python scripts/backup_eval_data.py
```

Menyalin `Eval_Data/Traces/` dan `Eval_Data/Observations/` ke `Eval_Data/backups/pre-faithfulness-replay_<UTC>/`.

Skrip replay menjalankan backup ini secara default kecuali `--skip-backup`.

## Menjalankan replay

Simulasi tanpa menulis ke Langfuse:

```bash
python scripts/replay_faithfulness_langfuse.py --dry-run
```

Pilot satu trace (disarankan sebelum batch):

```bash
python scripts/replay_faithfulness_langfuse.py --dry-run --skip-backup --limit 1
# lalu tanpa --dry-run, misalnya:
python scripts/replay_faithfulness_langfuse.py --skip-backup --limit 1 --write-summary output/pilot_replay.json
```

Replay sungguhan **default (in-place)** setelah backup: menghapus skor duplikat FABLES (API v2), lalu memperbarui tiga observasi kanonik tanpa `DELETE` observasi. **`--delete-old` saja** tidak menghapus leaf pada mode ini — gunakan **`--fables-recreate-leaves --delete-old`** jika Anda sengaja ingin path hapus+generasi baru.

```bash
python scripts/replay_faithfulness_langfuse.py --write-summary output/faithfulness_replay_summary.json
```

Hanya beberapa trace:

```bash
python scripts/replay_faithfulness_langfuse.py --trace-id <id1> <id2> --delete-old
```

Batasi ke ID yang ada di CSV export trace:

```bash
python scripts/replay_faithfulness_langfuse.py --traces-csv Eval_Data/Traces/exports_....csv --limit 5 --delete-old
```

Ambil observasi **langsung dari API** (disarankan jika export lokal tidak lengkap):

```bash
python scripts/replay_faithfulness_langfuse.py --fetch-live --delete-old
```

Ganti seluruh blok FABLES (hapus span + generasi, lalu buat ulang span + FABLES baru), pilot satu trace:

```bash
python scripts/replay_faithfulness_langfuse.py --trace-id 6abf564970aa95d360d7e92e42f8f9e9 --replace-fables-block --delete-old
```

## Penempatan span pada trace lama

[`LangfuseClient`](../src/workflows/story_agent/integrations/langfuse_client.py) memakai `set_faithfulness_replay_trace` (trace + parent dinormalisasi ke 32/16 hex). Untuk **generasi** pada replay, klien mengirim **`POST /api/public/ingestion`** bertipe `generation-create` dengan **`parentObservationId`** eksplisit ke SPAN `fables_faithfulness`, karena jalur SDK OpenTelemetry + `trace_context` menandai observasi dengan `langfuse.internal.as_root` sehingga di UI bisa tampil **sejajar dengan root trace** (bukan anak yang benar).

Pada **`--replace-fables-block`**, SPAN `fables_faithfulness` **baru** dibuat lewat **`span-create`** ingestion (bukan `start_span` SDK) supaya ID observasi 16-digit dikenal; lalu `generation-create` memakai parent itu (bukan `ragas_evaluation`). Tanpa itu, generasi FABLES akan tampil **rata** di bawah RAGAS (duplikat + salah hierarki).

**Default:** `parent_span_id` = id SPAN **`fables_faithfulness`** di bawah **`ragas_evaluation` pertama** (urutan waktu di export). **`--full-ragas-replay`:** induk = SPAN **`critic_agent`** (generasi tetap lewat ingestion bila `parent_span_id` diset).

[`RagasEvaluator.run(..., fables_replay_only=True)`](../src/workflows/story_agent/agents/critic/eval_ragas.py) tidak membuka span `ragas_evaluation` / `fables_faithfulness` baru. Skor FABLES memakai `observation_id` ke SPAN `fables_faithfulness` yang sama.

## Penghapusan observasi dan skor lama

**Mode default FABLES (in-place), dengan atau tanpa `--delete-old`:**

- Jika **`--delete-old`**: tetap **`DELETE` skor** bernama **`fables_faithfulness`** dan **`ragas_standard_faithfulness`** (API v2) untuk mengurangi pil duplikat; **tidak** ada `DELETE` observasi leaf kecuali Anda memakai **`--fables-recreate-leaves`** atau **`--replace-fables-block`**.

**`--fables-recreate-leaves` + `--delete-old`:** `DELETE` untuk **`fables_extract_claims`** dan **`fables_verify_all_claims`** di bawah SPAN `fables_faithfulness` target, lalu replay membuat generasi baru (legacy).

**Mode `--replace-fables-block` + `--delete-old`:** sama seperti hapus skor FABLES di atas, lalu `DELETE` untuk **`fables_faithfulness`**, **`fables_extract_claims`**, dan **`fables_verify_all_claims`** yang merupakan keturunan SPAN **`ragas_evaluation`** target (urutan hapus: observasi yang lebih baru dulu, agar generasi hilang sebelum span induk).

**Mode `--full-ragas-replay` + `--delete-old`:** daftar hapus penuh seperti sebelumnya (`ragas_evaluation`, `ragas_answer_relevancy`, `ragas_context_relevance`, `fables_faithfulness`, `fables_extract_claims`, `fables_verify_all_claims`). Skor tidak dihapus otomatis di mode ini.

Jika host Anda tidak mendukung **v2** scores API, langkah hapus skor bisa gagal (peringatan di log); hapus skor duplikat manual di UI bila perlu.

**Duplikat dari replay lama** (mis. blok `ragas_evaluation` / generasi datar di akhir trace): tidak dihapus otomatis oleh mode default. Bersihkan di UI Langfuse atau hapus observasi orphan secara manual.

## Nama trace + input/output level trace (`StoryGenerationWorkflow`)

Replay menambah observasi FABLES; **nama trace** di daftar trace bisa tampak mengikuti observasi terakhir. Setelah run sukses, skrip mengirim **`trace-create`** ingestion (upsert) agar **nama, `input`, dan `output` di level trace** kembali seperti export asli (biasanya **`StoryGenerationWorkflow`** + prompt + JSON `final_story`).

- Upsert memakai **timestamp ingestion “sekarang”** (bukan timestamp lama dari export), supaya pembaruan trace menang atas observasi eval terbaru di tampilan daftar trace (menghindari baris yang tampak seperti input/output `fables_verify_all_claims`).
- Hanya field workflow yang dipakai (bukan kolom skor datar di baris export) — lihat `slim_trace_row_for_restore` di `scripts/lib/replay_faithfulness_io.py`.

- Sumber default: `Eval_Data/Traces/*.jsonl` (baris dengan `id` = trace id).
- Jika tidak ada baris lokal dan Anda memakai **`--fetch-live`**, skrip mengambil metadata dari **`GET /api/public/traces/{traceId}`**.
- Matikan dengan **`--no-restore-trace`**.

### Perbaikan cepat tanpa menjalankan RAGAS lagi

Jika trace di cloud masih menampilkan JSON metrik di kolom input/output, kirim ulang metadata trace dari JSONL lokal:

```bash
python scripts/replay_faithfulness_langfuse.py --skip-backup --restore-trace-metadata-only --trace-id "<trace_id>"
```

`--dry-run` untuk cek sumber baris. Tanpa JSONL lokal, `--fetch-live` hanya mengambil **isi trace saat ini** di server (kalau sudah “salah”, tidak memperbaiki dari cerita asli).

**English:** Use `--restore-trace-metadata-only` to re-upsert story prompt + `final_story` from `Eval_Data/Traces` without LLM calls.

## Setelah replay

- Observasi **`critic_agent`** (keluaran `ragas_scores` di metadata) **tidak** diperbarui otomatis oleh skrip; yang diperbarui adalah run RAGAS/FABLES baru di bawah trace yang sama. Untuk konsistensi penuh di UI, pertimbangkan patch manual atau alur ekspor terpisah.
- Ekspor ulang observasi ke `Eval_Data/Observations/` agar selaras dengan Streamlit / `calc_f1.py`, misalnya dengan [`scripts/export_langfuse_traces.py`](../scripts/export_langfuse_traces.py) per trace atau batch.
- Regenerasi HTML faithfulness jika diperlukan: `python generate_faithfulness_images_10.py`.

## Opsi: backup lalu hapus trace di Langfuse (bukan hanya observasi)

Karena **API publik biasanya tidak bisa menghapus satu observasi** tanpa menghapus trace, strategi bersih adalah: **simpan salinan dulu**, lalu **`DELETE` trace** di Langfuse. Trace hilang dari project; **data lokal + export** tetap Anda pegang.

### 1. Backup lokal (`Eval_Data`)

```bash
python scripts/backup_eval_data.py
```

Menyalin `Eval_Data/Traces/` dan `Eval_Data/Observations/` ke `Eval_Data/backups/pre-faithfulness-replay_<UTC>/`.

### 2. (Disarankan) Export penuh dari cloud per trace / batch

Agar isi trace terbaru (termasuk yang belum ada di JSONL lama):

```bash
python scripts/export_langfuse_traces.py --trace-id "<trace_id>" --with-observations
```

Atau batch ke folder `output/` sesuai opsi skrip.

### 3. Hapus trace lewat API publik

Autentikasi: **Basic** `LANGFUSE_PUBLIC_KEY` : `LANGFUSE_SECRET_KEY` (sama seperti skrip lain).

**Satu trace:**

```bash
curl -sS -X DELETE \
  -u "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" \
  "${LANGFUSE_HOST%/}/api/public/traces/${TRACE_ID}"
```

**Beberapa trace sekaligus** (hingga 1000 id per request, lihat dokumentasi Langfuse):

```bash
curl -sS -X DELETE \
  -u "${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"traceIds":["<id1>","<id2>"]}' \
  "${LANGFUSE_HOST%/}/api/public/traces"
```

**Efek:** semua **observasi dan skor** pada trace tersebut ikut dihapus di Langfuse. **Tidak bisa** “hapus observasi saja” lewat endpoint ini.

### 4. Setelah hapus — impor ulang dari backup JSONL

Skrip [`scripts/import_langfuse_backup_ingestion.py`](../scripts/import_langfuse_backup_ingestion.py) mengirim **`trace-create`** lalu **`span-create` / `generation-create`** (urutan parent → anak) ke **`POST /api/public/ingestion`**, memakai isi **`Traces/*.jsonl`** dan **`Observations/*.jsonl`** (sama seperti salinan `backup_eval_data.py`).

```bash
# Simulasi: jumlah event dan ukuran batch
python scripts/import_langfuse_backup_ingestion.py --dry-run

# Satu trace
python scripts/import_langfuse_backup_ingestion.py --trace-id "<trace_id>"

# Dari folder backup
python scripts/import_langfuse_backup_ingestion.py \
  --backup-root Eval_Data/backups/pre-faithfulness-replay_<UTC>

# Hanya trace yang tercantum di CSV export Langfuse (gabungan dengan --trace-id bila keduanya dipakai)
python scripts/import_langfuse_backup_ingestion.py --dry-run \
  --backup-root Eval_Data/backups/pre-faithfulness-replay_<UTC> \
  --traces-csv exports_....csv
```

**Penting:** bila trace / observation dengan **id yang sama** masih ada di project, server bisa menolak atau menggabungkan tidak seperti yang Anda harapkan — untuk restore “bersih”, hapus trace di Langfuse dulu, lalu impor.

**English:** After deleting a trace in Langfuse, restore it from local exports with `import_langfuse_backup_ingestion.py`; use `--dry-run` first.

Skrip juga mengirim **`score-create`** dari **kolom skor datar** pada baris trace JSONL (mis. `ragas_answer_relevancy`, `fables_faithfulness`, …), termasuk membuka bungkus nilai berbentuk `[0.75]`. Matikan dengan **`--no-scores`**.

**Default penempatan (seperti badge di root trace / tabel utama):** skor impor adalah **level trace saja** (`traceId`, tanpa `observationId`). Ini selaras tampilan **StoryGenerationWorkflow** yang menampilkan skor di induk trace. Jika Anda sengaja ingin skor menempel pada satu observasi (nama kolom = nama span), gunakan **`--link-score-observations`**.

**Sumber (`source`) mode `auto`:** hampir semua metrik dari SDK proyek ini masuk sebagai **`API`**. Hanya kolom **`Faithfulness`** (jika ada di baris export) memakai **`EVAL`**. Paksa semua dengan **`--score-source API`** / **`EVAL`** bila perlu.

Impor **tidak** membuat skor sintetis (tidak menduplikasi `Faithfulness` / `ragas_faithfulness` / `geval_coherence*` dari kolom lain); hanya kolom yang benar-benar ada nilainya di JSONL trace yang dikirim.

Setelah impor observasi tanpa skor (atau skor salah sumber), kirim ulang hanya skor:

```bash
python scripts/import_langfuse_backup_ingestion.py --scores-only --trace-id "<trace_id>"
```

Skor dan trace+observation dikirim dalam **batch terpisah**; kegagalan skor memunculkan peringatan kecuali **`--strict-scores`**. Setiap skor memiliki **`id`** unik di body (disyaratkan beberapa deployment).

### Beda runtime vs impor

Saat **workflow** jalan, [`eval_ragas.py`](../src/workflows/story_agent/agents/critic/eval_ragas.py) boleh mengirim **`fables_faithfulness` / `ragas_standard_faithfulness`** dengan **`observation_id`** span **`fables_faithfulness`** (muncul sebagai pill di pohon di bawah span itu). **Impor dari JSONL** secara default **tidak** menyalin perilaku itu: skor ditulis ulang di **level trace** agar kolom tabel utama dan badge root konsisten dengan referensi UI Anda. Gunakan **`--link-score-observations`** hanya jika Anda memang ingin `observationId` pada impor.

### 5. Tanpa impor

- Trace **tidak** kembang sendiri; alternatif lain: **jalankan ulang workflow** aplikasi.
- Dataset analisis lokal (`Eval_Data`, file export) tetap dipakai untuk skripsi / Streamlit selama Anda tidak menghapus foldernya.

## Verifikasi Inkremental untuk Trace >10 Klaim

`RagasEvaluator._run_fables_faithfulness` di [`src/workflows/story_agent/agents/critic/eval_ragas.py`](../src/workflows/story_agent/agents/critic/eval_ragas.py) memotong klaim ke `MAX_CLAIMS = 10` pada saat verifikasi (lihat baris 705-713) — meski `fables_extract_claims.output.claims` mencatat **semua** klaim sebelum cap. Trace dengan 11+ klaim ekstrak hanya punya 10 verdicts. [`scripts/incremental_fables_verify.py`](../scripts/incremental_fables_verify.py) menambah verifikasi untuk klaim 11+ tanpa menyentuh data lama.

### Aturan Penamaan Generasi

- Klaim 1-10  -> `fables_verify_all_claims` (sudah ada, tidak diubah)
- Klaim 11-20 -> `fables_verify_all_claims_2` (baru)
- Klaim 21-30 -> `fables_verify_all_claims_3` (baru)
- Klaim 31-40 -> `fables_verify_all_claims_4` (baru), dst.

Skrip mendeteksi suffix tertinggi dari generasi yang sudah ada (regex `^fables_verify_all_claims(?:_(\d+))?$`) lalu mulai dari `max + 1`.

### Anchoring Timestamp (Durasi Trace Tidak Berubah)

Setiap generasi baru dikirim dengan `start_time = end_time = endTime_generasi_terakhir_existing` (instant event di akhir window verifikasi asli). Pola sama dengan `_fables_times_for_replay` di [`eval_ragas.py`](../src/workflows/story_agent/agents/critic/eval_ragas.py:33-72). Karena `start_time` Langfuse upstream **immutable** untuk observasi yang sudah ada, observasi lama benar-benar tidak terpengaruh.

### Patch Output 3 SPAN (Tanpa Ubah Timestamp)

Tiga SPAN menampilkan ringkasan FABLES yang stale jika hanya generasi yang ditambahkan:

- `fables_faithfulness` (parent FABLES) - `output.fables_*`
- `ragas_evaluation` - `output.scores.fables_*` dan `output.fables_*` di top level
- `critic_agent` - `output.ragas_scores.fables_*`

Skrip melakukan patch surgical (hanya field FABLES; `decision`, `educational_score`, `answer_relevancy`, `context_relevance`, `chars`, `elapsed_seconds` di-preserve persis) lalu kirim `_ingestion_span_update` dengan `start_time` & `end_time` PERSIS sama dengan original dari export. Server menjaga `start_time` immutable; `endTime` yang dikirim sama -> durasi span tidak berubah.

### Skor Trace-Level dengan Snapshot

Sebelum overwrite skor, skrip GET `/api/public/v2/scores?traceId=<id>` lalu menulis snapshot ke `output/incremental_runs/<trace_id>_<UTC>.json`:

```json
{
  "trace_id": "...",
  "snapshot_at": "...",
  "before": {"scores": {...}, "summary": {...}},
  "after_planned": {"summary": {...}},
  "new_generations": [...]
}
```

Lalu skrip menulis skor baru di **level trace**:

- `fables_faithfulness = faithful / max(faithful + unfaithful, 1)` (Kim et al. §4 - exclude PARTIAL_SUPPORT, CANT_VERIFY)
- `ragas_standard_faithfulness = faithful / max(total, 1)` (semua label di denominator)

### Workflow yang Direkomendasikan

```bash
# 1. Pilot satu trace, dry-run dulu (no API writes)
python scripts/incremental_fables_verify.py --trace-id 70a003d021e7b986e53e2d2069347021 --dry-run

# 2. Pilot run nyata (--fetch-live disarankan agar id observasi sinkron dengan server)
python scripts/incremental_fables_verify.py --trace-id 70a003d021e7b986e53e2d2069347021 --fetch-live

# 3. Verifikasi di Langfuse UI: generasi baru muncul di bawah span fables_faithfulness,
#    durasi trace tidak melar, output 3 SPAN ter-update, skor benar.
# 4. Jika OK, jalankan batch untuk sisa trace yang punya klaim pending
python scripts/incremental_fables_verify.py --auto-discover --dry-run --limit 5
python scripts/incremental_fables_verify.py --auto-discover --fetch-live
```

### Risiko

- Skrip akan FAIL bila tidak menemukan kontainer konteks (`fables_verify_all_claims.input.contexts` atau `ragas_context_relevance.input.contexts`). Solusi: pakai `--fetch-live` agar payload diambil dari server.
- Trace yang sebelumnya pernah dijalankan dengan skrip incremental versi BUGGY (yang menamai generasi `fables_verify_all_claims_20`, dst.) akan menghitung verdicts dari generasi tersebut juga - jika sudah lengkap, skrip akan SKIP. Kebersihan nama harus dirapikan manual via UI bila perlu.

## Risiko

| Risiko | Mitigasi |
|--------|----------|
| Kuota / biaya LLM | `--limit`, pilot `--trace-id` |
| DELETE gagal | Lanjut tanpa `--delete-old` atau bersihkan manual di UI |
| `trace_context` tidak didukung versi SDK | Pastikan `langfuse==3.14.5` (lihat `requirements.txt`) |
