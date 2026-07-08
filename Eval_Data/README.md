# Eval_Data

- **`Traces/`** — Export trace Langfuse (CSV/JSON/JSONL) untuk sampling dan metrik agregat.
- **`Observations/`** — Export observasi (JSONL) dipakai dashboard Streamlit, `calc_f1.py`, dan skrip replay faithfulness.
- **`Baselines/`** — Export trace + observasi untuk dataset evaluasi baseline (`BaselineWikiEvalWorkflow`). Struktur identik dengan dataset utama, dengan `Baselines/Traces` dan `Baselines/Observations`.

## Backup

Sebelum operasi yang mengubah data atau menulis ulang ke Langfuse:

```bash
python scripts/backup_eval_data.py
```

Output: `Eval_Data/backups/pre-faithfulness-replay_<timestamp>/` berisi salinan `Traces/` dan `Observations/`.

Untuk juga menyertakan dataset baseline gunakan flag `--include-baselines`; folder backup akan berisi `Baselines/Traces/` dan `Baselines/Observations/` di dalamnya:

```bash
python scripts/backup_eval_data.py --include-baselines
```

`scripts/incremental_fables_verify.py` dan `scripts/replay_faithfulness_langfuse.py` keduanya memanggil utilitas ini di awal run kecuali diberi `--skip-backup`.

## Verifikasi inkremental pada dataset baseline

`scripts/incremental_fables_verify.py` bekerja apa adanya pada `Eval_Data/Baselines` selama observation directory diarahkan ke `Eval_Data/Baselines/Observations`. Urutan pemakaian standar (mengacu pada batch terakhir 100 trace `BaselineWikiEvalWorkflow`):

```bash
python scripts/backup_eval_data.py --include-baselines

python scripts/incremental_fables_verify.py \
  --trace-id <pilot_id> \
  --observations-dir Eval_Data/Baselines/Observations \
  --dry-run --skip-backup --no-snapshot

python scripts/incremental_fables_verify.py \
  --trace-id <pilot_id> \
  --observations-dir Eval_Data/Baselines/Observations \
  --skip-backup --no-snapshot

python scripts/incremental_fables_verify.py \
  --auto-discover \
  --observations-dir Eval_Data/Baselines/Observations \
  --exclude-trace-id <pilot_id> \
  --skip-backup --no-snapshot \
  --write-summary output/incremental_baselines_batch_summary.json

python scripts/incremental_fables_verify.py \
  --trace-id $(python -c "import json; print(' '.join(json.load(open('output/baseline_trace_ids_100.json'))))") \
  --fetch-live --skip-backup --no-snapshot --reorder-spans-only \
  --write-summary output/reorder_baselines_100_summary.json

python scripts/audit_baseline_post_batch.py \
  --ids output/baseline_trace_ids_100.json \
  --output output/audit_baselines_post_batch.json
```

Skrip `scripts/audit_baseline_post_batch.py` memvalidasi tiap trace: tidak ada generation `fables_verify_all_claims*` duplikat, jumlah verdict gabungan = jumlah klaim di `fables_extract_claims`, serta urutan key 9-prefix di `ragas_evaluation.scores` dan `critic_agent.ragas_scores`. File id trace baseline 100 entry dapat di-generate dari `Eval_Data/Baselines/Observations/*.jsonl` (kumpulan unik `traceId`).

## Impor ulang ke Langfuse (setelah hapus trace)

Jika trace sudah dihapus di cloud tetapi Anda punya backup JSONL (`Traces/` + `Observations/`):

```bash
python scripts/import_langfuse_backup_ingestion.py --dry-run
python scripts/import_langfuse_backup_ingestion.py --backup-root Eval_Data/backups/pre-faithfulness-replay_<UTC>
# Restrict to trace ids from a Langfuse traces CSV (union with --trace-id if both given):
python scripts/import_langfuse_backup_ingestion.py --dry-run --backup-root Eval_Data/backups/pre-faithfulness-replay_<UTC> --traces-csv path/to/exports_....csv
```

Impor mengirim ulang **skor** dari kolom datar di baris trace JSONL (`score-create`). Detail dan batasan: [docs/replay_faithfulness_langfuse.md](../docs/replay_faithfulness_langfuse.md).

## Replay RAGAS + FABLES

Lihat [docs/replay_faithfulness_langfuse.md](../docs/replay_faithfulness_langfuse.md).

Pada export JSONL, `fables_verify_all_claims` sering **tidak** berisi array `contexts`; parser replay mengambil `contexts` dari span `ragas_context_relevance` / `fables_faithfulness` / `ragas_answer_relevancy` pada trace yang sama.

Replay default: **in-place** pada span + generasi FABLES **kanonik** (paling awal per nama jika ada duplikat); butuh hierarki `ragas_evaluation` → `fables_faithfulness`. Untuk perilaku lama **hapus leaf lalu generasi baru**: `--fables-recreate-leaves --delete-old`. Untuk **mengganti seluruh blok** FABLES: `--replace-fables-block --delete-old` (+ `--fetch-live` jika id export tidak sinkron). **`--fables-update-in-place`** opsional (default sudah in-place). `start_time` pada Langfuse standar mungkin tetap salah sampai replace atau patch worker (lihat doc). Skor FABLES dari skrip replay: level trace. Tanpa hierarki yang memadai, gunakan `--full-ragas-replay` atau perbaiki export / `--fetch-live`.

Restore batch dari backup + CSV: [docs/traces_restore_after_bad_replay.md](../docs/traces_restore_after_bad_replay.md).

Export **`Traces/*.jsonl`** dipakai untuk **mengembalikan nama trace + input/output** level trace (mis. `StoryGenerationWorkflow`) setelah replay; pastikan file trace export berisi trace id yang sama.
