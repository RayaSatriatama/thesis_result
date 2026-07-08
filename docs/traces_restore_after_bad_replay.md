# Restore traces after a bad FABLES replay

**English / Indonesia:** If a batch replay created **duplicate** `fables_extract_claims` / `fables_verify_all_claims` siblings or overwrote the **wrong** observations, recover from a **backup taken before** that replay.

## 1. Pick a backup folder

Use a timestamped copy under `Eval_Data/backups/` from `backup_eval_data.py` **before** the bad run, e.g.:

`Eval_Data/backups/pre-faithfulness-replay_<UTC>/`

It must contain `Traces/*.jsonl` and `Observations/*.jsonl`.

## 2. Delete affected traces in Langfuse (usually required)

Re-ingesting the **same** trace and observation ids while rows still exist can merge badly. Delete those traces in the Langfuse UI or via the public API (see [replay_faithfulness_langfuse.md](replay_faithfulness_langfuse.md) § “backup lalu hapus trace”).

## 3. Import only the traces listed in your CSV

Your export file (e.g. `exports_1776067541017-lf-traces-export-....csv`) lists `id` values. Import from backup for **just** those ids:

```bash
python scripts/import_langfuse_backup_ingestion.py --dry-run \
  --backup-root Eval_Data/backups/pre-faithfulness-replay_<UTC> \
  --traces-csv exports_1776067541017-lf-traces-export-cmiotu4on0006s007ssffnxlo.csv
```

Review the dry-run counts, then run **without** `--dry-run`.

You can combine `--traces-csv` with repeatable `--trace-id`; the filter is the **union** of both sets (matching is case-insensitive).

## 4. After restore

- Re-export observations to `Eval_Data/Observations/` if Streamlit / local metrics must match cloud.
- For future replays, default mode is **in-place** on the **earliest** extract/verify observations; use `--fables-recreate-leaves` only when you intentionally want delete + new generations.
