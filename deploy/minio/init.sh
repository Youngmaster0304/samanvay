#!/bin/sh
# Start MinIO on Render's assigned $PORT, then create the bucket if missing.
# Free Render services have no persistent disk: every boot starts empty, so
# bucket creation must run each time (uploads themselves live only for the
# lifetime of the instance; source metadata lives in Postgres).
set -eu

: "${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required}"
: "${MINIO_BUCKET:=samanvay}"

PORT="${PORT:-9000}"

minio server /bitnami/minio/data --address ":${PORT}" --console-address ":9001" &
MINIO_PID=$!

until curl -sf "http://localhost:${PORT}/minio/health/live" >/dev/null 2>&1; do
  if ! kill -0 "${MINIO_PID}" 2>/dev/null; then
    echo "minio exited before becoming healthy" >&2
    exit 1
  fi
  sleep 1
done

mc alias set local "http://localhost:${PORT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
mc mb --ignore-existing "local/${MINIO_BUCKET}"
echo "minio ready on :${PORT}, bucket '${MINIO_BUCKET}' present"

wait "${MINIO_PID}"
