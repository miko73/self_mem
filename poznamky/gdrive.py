# -*- coding: utf-8 -*-
"""Google Drive – přístup ke složce s poznámkami z AI relací.

Používá jen stdlib (urllib) a OAuth refresh token. Jednorázové získání
tokenu: python google_auth_setup.py (viz README).

Konfigurace (v tomto pořadí):
  1. env proměnné GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN
  2. soubor google_auth.json vedle tohoto modulu
     {"client_id": "...", "client_secret": "...", "refresh_token": "..."}

ID složky: env GDRIVE_FOLDER_ID (výchozí = složka „AI poznámky").
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
AUTH_FILE = BASE_DIR / 'google_auth.json'
FOLDER_ID = os.environ.get('GDRIVE_FOLDER_ID',
                           '1GqCbTce-jYRFnViT6bcklJef8Ww54GE1')

DOC_MIME = 'application/vnd.google-apps.document'
_API = 'https://www.googleapis.com'


class DriveError(Exception):
    """Chyba při komunikaci s Google Drive (zobrazí se uživateli)."""


def _load_auth():
    cid = os.environ.get('GDRIVE_CLIENT_ID')
    if cid:
        return {'client_id': cid,
                'client_secret': os.environ.get('GDRIVE_CLIENT_SECRET', ''),
                'refresh_token': os.environ.get('GDRIVE_REFRESH_TOKEN', '')}
    if AUTH_FILE.exists():
        try:
            return json.loads(AUTH_FILE.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
    return None


def is_configured():
    return _load_auth() is not None


def _fetch(req, raw=False):
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read()[:400].decode('utf-8', 'replace')
        raise DriveError(f'Google API vrátilo chybu {e.code}: {detail}')
    except OSError as e:
        raise DriveError(f'Nepodařilo se spojit s Google Drive: {e}')
    if raw:
        return body
    try:
        return json.loads(body)
    except ValueError:
        raise DriveError('Neplatná odpověď od Google API.')


_token_cache = {'value': None, 'expires': 0.0}


def _access_token():
    if _token_cache['value'] and time.time() < _token_cache['expires'] - 60:
        return _token_cache['value']
    auth = _load_auth()
    if not auth:
        raise DriveError('Google Drive není nakonfigurován.')
    data = urllib.parse.urlencode({
        'client_id': auth.get('client_id', ''),
        'client_secret': auth.get('client_secret', ''),
        'refresh_token': auth.get('refresh_token', ''),
        'grant_type': 'refresh_token',
    }).encode()
    j = _fetch(urllib.request.Request(
        'https://oauth2.googleapis.com/token', data=data, method='POST'))
    _token_cache['value'] = j['access_token']
    _token_cache['expires'] = time.time() + j.get('expires_in', 3600)
    return _token_cache['value']


def _api(path, params=None, method='GET', body=None, content_type=None,
         raw=False):
    url = _API + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Authorization', 'Bearer ' + _access_token())
    if content_type:
        req.add_header('Content-Type', content_type)
    return _fetch(req, raw=raw)


def is_editable(mime_type):
    """Soubory, které umíme zobrazit a upravit jako text."""
    return (mime_type == DOC_MIME or (mime_type or '').startswith('text/')
            or mime_type in ('application/json',))


def list_files():
    j = _api('/drive/v3/files', {
        'q': f"'{FOLDER_ID}' in parents and trashed = false",
        'fields': 'files(id,name,mimeType,modifiedTime)',
        'orderBy': 'modifiedTime desc',
        'pageSize': '100',
    })
    return j.get('files', [])


def get_meta(file_id):
    return _api(f'/drive/v3/files/{urllib.parse.quote(file_id)}', {
        'fields': 'id,name,mimeType,modifiedTime,webViewLink',
    })


def read_text(file_id, mime_type):
    """Obsah souboru jako text; Google Doc se exportuje do markdownu."""
    fid = urllib.parse.quote(file_id)
    if mime_type == DOC_MIME:
        data = _api(f'/drive/v3/files/{fid}/export',
                    {'mimeType': 'text/markdown'}, raw=True)
    else:
        data = _api(f'/drive/v3/files/{fid}', {'alt': 'media'}, raw=True)
    return data.decode('utf-8', 'replace')


def write_text(file_id, mime_type, text):
    """Přepíše obsah souboru; markdown se u Google Docu převede zpět."""
    if mime_type == DOC_MIME:
        content_type = 'text/markdown'
    else:
        content_type = mime_type or 'text/plain'
    _api(f'/upload/drive/v3/files/{urllib.parse.quote(file_id)}',
         {'uploadType': 'media'}, method='PATCH',
         body=text.encode('utf-8'), content_type=content_type)
