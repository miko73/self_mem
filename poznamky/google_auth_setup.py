# -*- coding: utf-8 -*-
"""Jednorázové propojení s Google Drive – získání refresh tokenu.

Příprava (jednou, v https://console.cloud.google.com):
  1. Vytvořit projekt (nebo použít existující).
  2. APIs & Services → Library → povolit „Google Drive API".
  3. APIs & Services → OAuth consent screen → typ External, vyplnit název,
     přidat sebe jako test usera; poté Publish app (Production) – jinak
     refresh token vyprší po 7 dnech.
  4. APIs & Services → Credentials → Create Credentials → OAuth client ID
     → typ „Desktop app". Zkopírovat Client ID a Client secret.

Spuštění (lokálně na počítači s prohlížečem):
    python google_auth_setup.py

Skript otevře prohlížeč, po povolení přístupu uloží google_auth.json
vedle app.py. Tento soubor pak nahrát na server (PythonAnywhere: Files)
– NEPATŘÍ do gitu.
"""
import io
import json
import sys
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

AUTH_FILE = Path(__file__).resolve().parent / 'google_auth.json'
SCOPE = 'https://www.googleapis.com/auth/drive'
PORT = 8765
REDIRECT = f'http://127.0.0.1:{PORT}/'

_result = {}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _result['code'] = qs.get('code', [None])[0]
        _result['error'] = qs.get('error', [None])[0]
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        msg = ('Hotovo, okno můžeš zavřít.' if _result['code']
               else f'Chyba: {_result["error"]}')
        self.wfile.write(f'<h2>{msg}</h2>'.encode())

    def log_message(self, *args):
        pass


def main():
    client_id = input('Client ID: ').strip()
    client_secret = input('Client secret: ').strip()
    if not client_id or not client_secret:
        print('Client ID i secret jsou povinné.')
        sys.exit(1)

    auth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + \
        urllib.parse.urlencode({
            'client_id': client_id,
            'redirect_uri': REDIRECT,
            'response_type': 'code',
            'scope': SCOPE,
            'access_type': 'offline',
            'prompt': 'consent',
        })

    server = HTTPServer(('127.0.0.1', PORT), _Handler)
    server.timeout = 300
    print('Otevírám prohlížeč… (pokud se neotevře, otevři ručně):')
    print(auth_url)
    webbrowser.open(auth_url)
    server.handle_request()   # blokuje, dokud Google nepřesměruje zpět
    if not _result.get('code'):
        print(f'Nepřišel autorizační kód ({_result.get("error")}).')
        sys.exit(1)

    data = urllib.parse.urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'code': _result['code'],
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT,
    }).encode()
    with urllib.request.urlopen(
            urllib.request.Request('https://oauth2.googleapis.com/token',
                                   data=data), timeout=20) as r:
        tokens = json.loads(r.read())

    refresh = tokens.get('refresh_token')
    if not refresh:
        print('Google nevrátil refresh token – zkus to znovu '
              '(prompt=consent by ho měl vynutit).')
        sys.exit(1)

    AUTH_FILE.write_text(json.dumps({
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh,
    }, indent=2), encoding='utf-8')
    print(f'Uloženo do {AUTH_FILE}')
    print('Tento soubor nahraj na server vedle app.py (do gitu nepatří).')


if __name__ == '__main__':
    main()
