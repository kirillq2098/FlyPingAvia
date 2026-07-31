#!/usr/bin/env bash
# Safe SQLite online backup via sqlite3.Connection.backup() inside the app container.
# Does not stop the bot. Does not restore DB.
set -euo pipefail

CONTAINER="${FLYPING_CONTAINER:-flyping-app}"
SRC_IN_CONTAINER="${FLYPING_DB_PATH:-/app/data/flypingavia.db}"
OUT_DIR="${FLYPING_BACKUP_DIR:-/var/backups/flyping}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASENAME="flypingavia-${STAMP}.db"
TMP_IN_CONTAINER="/tmp/${BASENAME}"
OUT_FILE="${OUT_DIR}/${BASENAME}"

mkdir -p "$OUT_DIR"

docker exec "$CONTAINER" python -c "
import os, sqlite3, sys
src = ${SRC_IN_CONTAINER@Q}
out = ${TMP_IN_CONTAINER@Q}
if not os.path.isfile(src):
    print(f'missing db: {src}', file=sys.stderr)
    sys.exit(1)
conn = sqlite3.connect(src, timeout=30.0)
try:
    dst = sqlite3.connect(out)
    try:
        conn.backup(dst)
    finally:
        dst.close()
finally:
    conn.close()
print(out)
"

docker cp "${CONTAINER}:${TMP_IN_CONTAINER}" "$OUT_FILE"
docker exec "$CONTAINER" rm -f "$TMP_IN_CONTAINER"

# Optional gzip sibling for long-term retention
gzip -c "$OUT_FILE" > "${OUT_FILE}.gz"
# Keep uncompressed for quick integrity_check; remove if disk pressure
# (timer retains both; ops can prune)

ls -lh "$OUT_FILE" "${OUT_FILE}.gz"
echo "OK backup -> $OUT_FILE"
