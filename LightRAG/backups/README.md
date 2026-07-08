# LightRAG storage backups

Snapshots of `data/rag_storage` for **LightRAG-en** and **LightRAG-id** (JSON/GraphML state used by the thesis stack).

## Naming convention

| Pattern | Meaning |
|--------|---------|
| `lightrag_pre_100pertanyaan_<YYYYMMDD>/` | Snapshot **before** running the 100-question experiment (50 ID + 50 EN). Contains `lightrag-en/rag_storage/` and `lightrag-id/rag_storage/`. |
| `lightrag_post_100pertanyaan_<YYYYMMDD>/` | Optional: snapshot **after** that experiment (same inner layout). |
| `lightrag_from_docker_<YYYYMMDD>[_HHMM]/` | Snapshot taken **from running containers** via `docker compose cp` (see script below). Same folder layout as above. |

Use `_HHMM` before `/` if you need more than one snapshot per day, e.g. `lightrag_pre_100pertanyaan_20260412_1430`.

## Backup from Docker (containers)

`docker-compose.yml` bind-mounts `rag_storage` from the host, so host copies usually match the container. To archive **explicitly from Docker** (what the API process actually sees):

```bash
cd LightRAG
./scripts/backup_lightrag_from_docker.sh [bundle_name]
```

- Default bundle name: `lightrag_from_docker_YYYYMMDD_HHMM`
- Writes `lightrag-en/rag_storage/` and `lightrag-id/rag_storage/` plus `BACKUP_SOURCE.txt`

**Full stack (large, ~2+ GB compressed):** Neo4j + Qdrant + Redis named volumes:

```bash
./scripts/backup_lightrag_from_docker.sh --with-volumes [bundle_name]
```

Adds `volumes/neo4j_data.tar.gz`, `qdrant_data.tar.gz`, `redis_data.tar.gz`. Volume names assume containers from this compose file (`lightrag_neo4j_data`, etc.).

## Current bundles (examples)

- `lightrag_pre_100pertanyaan_20260412/` — host `cp` of `data/rag_storage` (pre-experiment naming).
- `lightrag_from_docker_20260412/` — same layout, copied with `docker compose cp` from `lightrag_en` / `lightrag_id`.

The Streamlit dashboard (`Streamlit/`) defaults to the latest `lightrag_pre_100pertanyaan_*` bundle; use **Override path** or pick another folder under `backups/` if you compare against `lightrag_from_docker_*`.
