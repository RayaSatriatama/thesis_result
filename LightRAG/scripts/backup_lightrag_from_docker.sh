#!/usr/bin/env bash
# Backup LightRAG data by copying from running Docker containers (not only host bind mounts).
# Usage:
#   ./scripts/backup_lightrag_from_docker.sh [bundle_name]
#   ./scripts/backup_lightrag_from_docker.sh --with-volumes [bundle_name]
#
# Default bundle: lightrag_from_docker_YYYYMMDD_HHMM
# Layout (same as Streamlit / backups README):
#   backups/<bundle>/lightrag-en/rag_storage/
#   backups/<bundle>/lightrag-id/rag_storage/
# With --with-volumes also:
#   backups/<bundle>/volumes/neo4j_data.tar.gz qdrant_data.tar.gz redis_data.tar.gz

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="$ROOT/docker-compose.yml"
WITH_VOLUMES=0
ARGS=()
for a in "$@"; do
  if [[ "$a" == "--with-volumes" ]]; then
    WITH_VOLUMES=1
  else
    ARGS+=("$a")
  fi
done

if [[ ${#ARGS[@]} -gt 0 ]]; then
  BUNDLE="${ARGS[0]}"
else
  BUNDLE="lightrag_from_docker_$(date +%Y%m%d_%H%M)"
fi

OUT="$ROOT/backups/$BUNDLE"
mkdir -p "$OUT/lightrag-en" "$OUT/lightrag-id"

if [[ ! -f "$COMPOSE" ]]; then
  echo "Missing $COMPOSE" >&2
  exit 1
fi

echo "== Bundle: $BUNDLE"
echo "== Copy rag_storage from containers lightrag_en / lightrag_id -> $OUT"

docker compose -f "$COMPOSE" cp lightrag-en:/app/data/rag_storage "$OUT/lightrag-en/"
docker compose -f "$COMPOSE" cp lightrag-id:/app/data/rag_storage "$OUT/lightrag-id/"

META="$OUT/BACKUP_SOURCE.txt"
{
  echo "source=docker_compose_cp"
  echo "timestamp=$(date -Iseconds)"
  echo "compose=$COMPOSE"
  echo "services=lightrag-en,lightrag-id paths=/app/data/rag_storage"
} >"$META"

if [[ "$WITH_VOLUMES" -eq 1 ]]; then
  VOL="$OUT/volumes"
  mkdir -p "$VOL"
  echo "== Archiving named volumes (Neo4j, Qdrant, Redis) -> $VOL/*.tar.gz (may take several minutes)"
  docker run --rm \
    -v lightrag_neo4j_data:/source:ro \
    -v "$VOL:/out" \
    alpine tar czf /out/neo4j_data.tar.gz -C /source .
  docker run --rm \
    -v lightrag_qdrant_data:/source:ro \
    -v "$VOL:/out" \
    alpine tar czf /out/qdrant_data.tar.gz -C /source .
  docker run --rm \
    -v lightrag_redis_data:/source:ro \
    -v "$VOL:/out" \
    alpine tar czf /out/redis_data.tar.gz -C /source .
  {
    echo "volumes_archived=neo4j_data,qdrant_data,redis_data"
    echo "volume_names=lightrag_neo4j_data,lightrag_qdrant_data,lightrag_redis_data"
  } >>"$META"
fi

echo "Done: $OUT"
ls -la "$OUT/lightrag-en/rag_storage" | head -5
ls -la "$OUT/lightrag-id/rag_storage" | head -5
