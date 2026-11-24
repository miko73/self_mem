#!/usr/bin/env bash
# Import dat z PythonAnywhere na VM. Spousti 02-import-vm.ps1:
#   sudo bash import_vm.sh <adresar-s-nahranymi-soubory>
set -euo pipefail
SRC="${1:?Chybi adresar s nahranymi soubory}"
DATA_DIR=/var/lib/poznamky
APP_DIR=/opt/self_mem/poznamky
ENV_FILE=/etc/poznamky.env
trap 'rm -rf "$SRC"' EXIT
[[ $EUID -eq 0 ]] || { echo "Spustte pres sudo." >&2; exit 1; }
[[ -f "$SRC/notes.db" ]] || { echo "Chybi notes.db" >&2; exit 1; }

check=$(sqlite3 "$SRC/notes.db" 'PRAGMA integrity_check;')
[[ "$check" == "ok" ]] || { echo "Databaze je poskozena: $check" >&2; exit 1; }

echo "== Zastavuji aplikaci"
systemctl stop poznamky.service

if [[ -f "$DATA_DIR/notes.db" ]]; then
    keep="$DATA_DIR/backup/notes-pred-importem-$(date +%Y%m%d-%H%M%S).db"
    mv "$DATA_DIR/notes.db" "$keep"
    echo "   puvodni DB na VM odlozena: $keep"
fi
rm -f "$DATA_DIR/notes.db-wal" "$DATA_DIR/notes.db-shm" "$DATA_DIR/notes.db-journal"

echo "== Kopiruji data"
install -o poznamky -g poznamky -m 600 "$SRC/notes.db" "$DATA_DIR/notes.db"
for f in anthropic_key.txt secret_key.txt; do
    if [[ -f "$SRC/$f" ]]; then
        install -o poznamky -g poznamky -m 600 "$SRC/$f" "$DATA_DIR/$f"; echo "   $f"
    fi
done
if [[ -f "$SRC/google_auth.json" ]]; then
    install -o root -g poznamky -m 640 "$SRC/google_auth.json" "$APP_DIR/google_auth.json"
    echo "   google_auth.json"
fi

if [[ -f "$SRC/poznamky.env" ]]; then
    echo "== Promenne z WSGI -> $ENV_FILE"
    while IFS= read -r line; do
        [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)= ]] || continue
        key="${BASH_REMATCH[1]}"
        [[ "$key" == "NOTES_DB" ]] && continue
        sed -i "/^${key}=/d" "$ENV_FILE"
        printf '%s\n' "$line" >> "$ENV_FILE"
        echo "   $key"
    done < "$SRC/poznamky.env"
fi

echo "== Startuji aplikaci"
systemctl start poznamky.service
sleep 3
systemctl --no-pager --lines=0 status poznamky | grep -E 'Active:'
curl -fsS -o /dev/null -w '   lokalni test /login: HTTP %{http_code}\n' http://127.0.0.1:8000/login

echo "== Pocty radku na VM"
for t in notes scratchpad changelog kamera; do
    printf '   %-11s %s\n' "$t" "$(sqlite3 "$DATA_DIR/notes.db" "SELECT COUNT(*) FROM $t;")"
done
