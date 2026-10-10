#!/usr/bin/env bash
# Nightly backup of the Sadhana Report database only. Keeps 14 days.
# Cron (as user vishnuvahan):  30 2 * * * /home/vishnuvahan/sadhana/deploy/backup.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/home/vishnuvahan/sadhana}"
BACKUP_DIR="${BACKUP_DIR:-/home/vishnuvahan/backups/sadhna}"
KEEP_DAYS=14

# The connection string lives in .env; pg_dump accepts it as-is.
DATABASE_URL="$(grep -E '^DATABASE_URL=' "$APP_DIR/.env" | head -n 1 | cut -d= -f2- | tr -d "'\"")"
if [ -z "$DATABASE_URL" ]; then
    echo "DATABASE_URL not found in $APP_DIR/.env" >&2
    exit 1
fi

umask 077
mkdir -p "$BACKUP_DIR"
target="$BACKUP_DIR/sadhna_db-$(date +%Y-%m-%d_%H%M).sql.gz"
pg_dump --no-owner --dbname="$DATABASE_URL" | gzip > "$target.tmp"
mv "$target.tmp" "$target"

find "$BACKUP_DIR" -name 'sadhna_db-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
echo "Backup written: $target"
