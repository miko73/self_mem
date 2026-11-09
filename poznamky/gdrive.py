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


def read_bytes(file_id):
    """Binární obsah souboru (např. fotky)."""
    return _api(f'/drive/v3/files/{urllib.parse.quote(file_id)}',
                {'alt': 'media'}, raw=True)


def write_text(file_id, mime_type, text):
    """Přepíše obsah souboru; markdown se u Google Docu převede zpět."""
    if mime_type == DOC_MIME:
        content_type = 'text/markdown'
    else:
        content_type = mime_type or 'text/plain'
    _api(f'/upload/drive/v3/files/{urllib.parse.quote(file_id)}',
         {'uploadType': 'media'}, method='PATCH',
         body=text.encode('utf-8'), content_type=content_type)


# ------------------------------------------- úložiště dokumentů (složky)

# Kořen pro cesty typu „stavy_meridel/plyn“ – výchozí je „Můj disk“.
DOCS_ROOT_ID = os.environ.get('GDRIVE_DOCS_ROOT_ID', 'root')
FOLDER_MIME = 'application/vnd.google-apps.folder'
_folder_cache = {}


def _q(value):
    """Escapování hodnoty pro dotaz q= v Drive API."""
    return value.replace('\\', '\\\\').replace("'", "\\'")


def _child_folder(parent_id, name, create):
    key = (parent_id, name)
    if key in _folder_cache:
        return _folder_cache[key]
    j = _api('/drive/v3/files', {
        'q': (f"'{_q(parent_id)}' in parents and name = '{_q(name)}' "
              f"and mimeType = '{FOLDER_MIME}' and trashed = false"),
        'fields': 'files(id)', 'pageSize': '1',
    })
    files = j.get('files', [])
    if files:
        fid = files[0]['id']
    elif create:
        body = json.dumps({'name': name, 'mimeType': FOLDER_MIME,
                           'parents': [parent_id]}).encode('utf-8')
        fid = _api('/drive/v3/files', {'fields': 'id'}, method='POST',
                   body=body, content_type='application/json')['id']
    else:
        return None
    _folder_cache[key] = fid
    return fid


def folder_by_path(path, create=True):
    """ID složky podle cesty od DOCS_ROOT_ID; chybějící složky založí."""
    fid = DOCS_ROOT_ID
    for part in [p for p in path.split('/') if p]:
        fid = _child_folder(fid, part, create)
        if fid is None:
            return None
    return fid


def list_subfolders(path):
    """Názvy podsložek dané cesty (abecedně); neexistující cesta → []."""
    fid = folder_by_path(path, create=False)
    if not fid:
        return []
    j = _api('/drive/v3/files', {
        'q': (f"'{_q(fid)}' in parents and mimeType = '{FOLDER_MIME}' "
              "and trashed = false"),
        'fields': 'files(id,name)', 'orderBy': 'name', 'pageSize': '100',
    })
    return [f['name'] for f in j.get('files', [])]


def upload_file(folder_id, name, data, mime_type):
    """Nahraje binární soubor do složky, vrátí metadata (id, webViewLink)."""
    boundary = 'selfmem' + os.urandom(8).hex()
    meta = json.dumps({'name': name, 'parents': [folder_id]})
    body = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8'
            f'\r\n\r\n{meta}\r\n--{boundary}\r\nContent-Type: {mime_type}'
            '\r\n\r\n').encode('utf-8') + data + f'\r\n--{boundary}--'.encode()
    return _api('/upload/drive/v3/files',
                {'uploadType': 'multipart', 'fields': 'id,name,webViewLink'},
                method='POST', body=body,
                content_type=f'multipart/related; boundary={boundary}')


def move_file(file_id, folder_id, new_name=None):
    """Přesune soubor do jiné složky (případně přejmenuje)."""
    fid = urllib.parse.quote(file_id)
    parents = _api(f'/drive/v3/files/{fid}',
                   {'fields': 'parents'}).get('parents', [])
    params = {'addParents': folder_id, 'fields': 'id,name,webViewLink'}
    old = [p for p in parents if p != folder_id]
    if old:
        params['removeParents'] = ','.join(old)
    body = json.dumps({'name': new_name} if new_name else {}).encode('utf-8')
    return _api(f'/drive/v3/files/{fid}', params, method='PATCH', body=body,
                content_type='application/json')
