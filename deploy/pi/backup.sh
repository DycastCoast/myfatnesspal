#!/bin/sh
# Nightly copy of the diary. SQLite's backup API is safe while the app is writing.
# Keeps 30 days in ./backups, plus backups/latest.db for the PC to pull.
# cron (crontab -e):  15 3 * * *  /home/pi/myfatnesspal/backup.sh
set -eu
cd "$(dirname "$0")"
mkdir -p backups
day=$(date +%F)
python3 - "$day" <<'PY'
import sqlite3, sys
src = sqlite3.connect("file:data/myfatnesspal.db?mode=ro", uri=True)
dst = sqlite3.connect(f"backups/myfatnesspal-{sys.argv[1]}.db")
src.backup(dst)
dst.close(); src.close()
PY
cp "backups/myfatnesspal-$day.db" backups/latest.db
find backups -name 'myfatnesspal-*.db' -mtime +30 -delete
