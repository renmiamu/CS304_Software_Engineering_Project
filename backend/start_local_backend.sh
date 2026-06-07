#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "[ERROR] 未找到 docker compose / docker-compose" >&2
  exit 1
fi

echo "[1/4] 启动数据库相关容器 (PostgreSQL/Redis/Elasticsearch)..."
"${COMPOSE_CMD[@]}" up -d gsk_pg redis es01

POSTGRES_USER="${POSTGRES_USER:-shl1}"
POSTGRES_DB="${POSTGRES_DB:-sustech_db}"

wait_for_postgres() {
  local retries=60
  until docker exec gsk_pg pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      echo "[ERROR] PostgreSQL 启动超时" >&2
      return 1
    fi
    sleep 2
  done
}

wait_for_redis() {
  local retries=60
  until docker exec gsk_redis redis-cli ping 2>/dev/null | grep -q "PONG"; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      echo "[ERROR] Redis 启动超时" >&2
      return 1
    fi
    sleep 2
  done
}

wait_for_es() {
  local retries=90
  until curl -fsS "http://localhost:9200" >/dev/null 2>&1; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      echo "[ERROR] Elasticsearch 启动超时" >&2
      return 1
    fi
    sleep 2
  done
}

echo "[2/4] 等待 PostgreSQL 就绪..."
wait_for_postgres

echo "[3/4] 等待 Redis 与 Elasticsearch 就绪..."
wait_for_redis
wait_for_es

if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

export SUSTECH_ASSISTANT_DATABASE_URL="${SUSTECH_ASSISTANT_DATABASE_URL:-postgresql+psycopg2://shl1:123456@localhost:5432/sustech_db}"
export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-${REDIS_HOST_PORT:-16379}}"
export REDIS_DB="${REDIS_DB:-0}"
export ES_HOST="${ES_HOST:-http://localhost:9200}"
export PYTHONPATH="$SCRIPT_DIR"

echo "[4/4] 启动本机 uvicorn (app.main:app)..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${UVICORN_PORT:-8000}" --reload
