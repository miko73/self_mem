#!/usr/bin/env bash
# Denni konzistentni zaloha SQLite databaze, ponecha 14 poslednich.
set -euo pipefail
DB=/var/lib/poznamky/notes.db
DIR=/var/lib/poznamky/backup
[[ -f "$DB" ]] || exit 0
target="$DIR/notes-$(date +%Y-%m-%d).db"
sqlite3 "$DB" ".backup '$target'"
gzip -f "$target"
ls -1t "$DIR"/notes-*.db.gz | tail -n +15 | xargs -r rm --
