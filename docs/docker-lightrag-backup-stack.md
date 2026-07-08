# LightRAG Docker — `lightrag_storage_backup_init_100_context`

## Purpose

Run a **second** LightRAG stack (EN + ID) that mounts the thesis baseline under:

`data/backups/lightrag_storage_backup_init_100_context`

(WikiEval **init 100 konteks** — byte-identical to the removed duplicate `lightrag_storage_backup_20260401_000000`.)

Uses **file-backed** storages so **Neo4j / Qdrant / Redis are not required** for this stack.

## Ports (host)

| Service   | URL                    |
|----------|-------------------------|
| English  | http://localhost:19631  |
| Indonesia| http://localhost:19632  |

Compose project: **`lightragbak_init100`** · Containers: **`lightrag_bak_init100_en`**, **`lightrag_bak_init100_id`**

Compose file: **`LightRAG/docker-compose.backup-init100.yml`**

## Commands

From `Skripsi/LightRAG`:

```bash
docker compose -f docker-compose.backup-init100.yml up -d --build
docker compose -f docker-compose.backup-init100.yml down
```

Health:

```bash
curl -s http://127.0.0.1:19631/health
curl -s http://127.0.0.1:19632/health
```

## Storage mode

Forces:

- `JsonKVStorage`
- `JsonDocStatusStorage`
- `NetworkXStorage`
- `NanoVectorDBStorage`

Matches flat `lightrag-en/` and `lightrag-id/` layout under the backup bundle.

## Embedding dimension

Set **`EMBEDDING_DIM=3072`** in compose to match `vdb_*.json` in the backup.

## Config

- `config.ini` ← `config.ini.example` (read-only)
- `LightRAG-en/.env` and `LightRAG-id/.env` (read-only)

## Notes

- Backup directory is mounted **read-write**; UI actions can change files on disk.
- For read-only experiments, copy the bundle and change volume paths in the compose file.
