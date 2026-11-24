#!/usr/bin/env bash
# Aktualizace IP na DuckDNS (prazdne ip= -> DuckDNS pouzije adresu odesilatele).
set -euo pipefail
# shellcheck disable=SC1091
source /etc/duckdns.env
# token predavame pres stdin (curl -K -), aby nebyl videt v seznamu procesu
result=$(printf 'url = "https://www.duckdns.org/update?domains=%s&token=%s&ip="\n' \
    "$DUCKDNS_SUBDOMAIN" "$DUCKDNS_TOKEN" | curl -fsS --max-time 20 -K -)
if [[ "$result" != "OK" ]]; then
    echo "DuckDNS odpovedel: $result" >&2
    exit 1
fi
