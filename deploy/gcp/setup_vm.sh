#!/usr/bin/env bash
# Instalace aplikace Poznamky na Ubuntu 24.04 VM (Caddy + gunicorn + systemd).
# Spousti 00-priprava-vm.ps1:  sudo bash setup_vm.sh <adresar-s-nahranymi-soubory>
# Adresar obsahuje tento skript, konfiguracni soubory a setup.env
# (DOMAIN, DUCKDNS_SUBDOMAIN, DUCKDNS_TOKEN, volitelne NOTES_PASSWORD).
# Skript je idempotentni - lze ho spustit opakovane.
set -euo pipefail

SRC="${1:?Chybi adresar s nahranymi soubory}"
REPO_URL="https://github.com/miko73/self_mem.git"
APP_DIR=/opt/self_mem
DATA_DIR=/var/lib/poznamky
ENV_FILE=/etc/poznamky.env

trap 'rm -rf "$SRC"' EXIT

[[ $EUID -eq 0 ]] || { echo "Spustte pres sudo." >&2; exit 1; }
# shellcheck disable=SC1091
source "$SRC/setup.env"
: "${DOMAIN:?}" "${DUCKDNS_SUBDOMAIN:?}" "${DUCKDNS_TOKEN:?}"

echo "== 1/7 Balicky"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3-venv sqlite3 git curl caddy

echo "== 2/7 Uzivatel a adresare"
id poznamky >/dev/null 2>&1 || useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin poznamky
install -d -o poznamky -g poznamky -m 700 "$DATA_DIR" "$DATA_DIR/backup"

echo "== 3/7 Kod aplikace"
if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$APP_DIR"
fi
[[ -d "$APP_DIR/venv" ]] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/poznamky/requirements.txt" gunicorn

echo "== 4/7 Konfigurace aplikace ($ENV_FILE)"
touch "$ENV_FILE"; chown root:poznamky "$ENV_FILE"; chmod 640 "$ENV_FILE"
grep -q '^NOTES_DB=' "$ENV_FILE" || echo "NOTES_DB=$DATA_DIR/notes.db" >> "$ENV_FILE"
if [[ -n "${NOTES_PASSWORD:-}" ]]; then
    HASH=$(printf '%s' "$NOTES_PASSWORD" | "$APP_DIR/venv/bin/python" -c \
        'import sys; from werkzeug.security import generate_password_hash as g; print(g(sys.stdin.read()))')
    sed -i '/^NOTES_PASSWORD_HASH=/d' "$ENV_FILE"
    # jednoduche uvozovky: hash obsahuje '$', systemd ho tak bere doslova
    echo "NOTES_PASSWORD_HASH='$HASH'" >> "$ENV_FILE"
    echo "   heslo nastaveno"
elif ! grep -q '^NOTES_PASSWORD_HASH=' "$ENV_FILE"; then
    echo "   heslo zatim nenastaveno - doplni ho 02-import-vm.ps1 z PythonAnywhere"
fi

echo "== 5/7 DuckDNS ($DOMAIN)"
umask 077
printf 'DUCKDNS_SUBDOMAIN=%s\nDUCKDNS_TOKEN=%s\n' "$DUCKDNS_SUBDOMAIN" "$DUCKDNS_TOKEN" > /etc/duckdns.env
chmod 600 /etc/duckdns.env
umask 022
install -m 755 "$SRC/duckdns.sh" /usr/local/bin/duckdns-update
install -m 755 "$SRC/backup.sh" /usr/local/bin/poznamky-backup
install -m 644 "$SRC/duckdns.service" "$SRC/duckdns.timer" \
               "$SRC/poznamky.service" "$SRC/poznamky-backup.service" "$SRC/poznamky-backup.timer" \
               /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now duckdns.timer
systemctl start duckdns.service
MYIP=$(curl -fsS -H 'Metadata-Flavor: Google' \
    'http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip')
for i in $(seq 1 30); do
    [[ "$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}')" == "$MYIP" ]] && break
    echo "   cekam na DNS $DOMAIN -> $MYIP ($i/30)"; sleep 10
done

echo "== 6/7 Aplikace a zalohy"
systemctl enable poznamky.service poznamky-backup.timer
systemctl restart poznamky.service
systemctl start poznamky-backup.timer

echo "== 7/7 Caddy (HTTPS)"
sed "s/__DOMAIN__/$DOMAIN/" "$SRC/Caddyfile" > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
systemctl enable caddy
systemctl reload-or-restart caddy

sleep 3
systemctl --no-pager --lines=0 status poznamky caddy | grep -E '●|Active:'
curl -fsS -o /dev/null -w '   lokalni test /login: HTTP %{http_code}\n' http://127.0.0.1:8000/login
echo "Hotovo: https://$DOMAIN"
