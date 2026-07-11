# -*- coding: utf-8 -*-
"""Poznámky – jednoduchý osobní poznámkový blok (Flask + SQLite).

Spuštění lokálně:   python app.py
Vygenerování hashe: python app.py hash mojeheslo
"""
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('NOTES_DB', BASE_DIR / 'notes.db'))
try:
    LOCAL_TZ = ZoneInfo('Europe/Prague')
except ZoneInfoNotFoundError:
    LOCAL_TZ = None  # bez tzdata (Windows) → systémová časová zóna

app = Flask(__name__)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,      # lokální běh přes `python app.py` to vypne
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,   # 30 dní
    MAX_CONTENT_LENGTH=1024 * 1024,  # 1 MB na požadavek stačí
)


def _load_secret_key():
    """SECRET_KEY z env, jinak vygenerovat a uložit vedle DB (přežije restart)."""
    key = os.environ.get('NOTES_SECRET_KEY')
    if key:
        return key
    key_file = DB_PATH.parent / 'secret_key.txt'
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_hex(32)
    key_file.write_text(key)
    return key


app.secret_key = _load_secret_key()

PASSWORD_HASH = os.environ.get('NOTES_PASSWORD_HASH', '')


# ---------------------------------------------------------------- databáze

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript((BASE_DIR / 'schema.sql').read_text(encoding='utf-8'))


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


# --------------------------------------------------- verze stavu + protokol

def device_name():
    """Hrubá identifikace zařízení z User-Agent pro protokol změn."""
    ua = request.user_agent.string or ''
    if 'Android' in ua:
        system = 'Android'
    elif 'iPhone' in ua or 'iPad' in ua:
        system = 'iPhone/iPad'
    elif 'Windows' in ua:
        system = 'Windows'
    elif 'Mac' in ua:
        system = 'Mac'
    elif 'Linux' in ua:
        system = 'Linux'
    else:
        system = 'neznámé'
    if 'Edg' in ua:
        browser = 'Edge'
    elif 'Chrome' in ua:
        browser = 'Chrome'
    elif 'Firefox' in ua:
        browser = 'Firefox'
    elif 'Safari' in ua:
        browser = 'Safari'
    else:
        browser = 'prohlížeč'
    return f'{system} · {browser}'


def get_version(db):
    row = db.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
    return row['value'] if row else 0


def log_change(db, action, note_id=None, summary=''):
    """Zapíše změnu do protokolu a zvýší číslo verze (bez commitu)."""
    cur = db.execute("UPDATE meta SET value = value + 1 WHERE key = 'version'")
    if cur.rowcount == 0:
        db.execute("INSERT INTO meta (key, value) VALUES ('version', 1)")

    ts = now_iso()
    dev = device_name()
    if action == 'scratch':
        # autosave chodí každou chvíli – záznamy od téhož zařízení
        # mladší 10 minut se slučují do jednoho
        last = db.execute(
            'SELECT id, ts, device, action FROM changelog '
            'ORDER BY id DESC LIMIT 1').fetchone()
        if last and last['action'] == 'scratch' and last['device'] == dev:
            age = (datetime.fromisoformat(ts)
                   - datetime.fromisoformat(last['ts'])).total_seconds()
            if age < 600:
                db.execute('UPDATE changelog SET ts = ? WHERE id = ?',
                           (ts, last['id']))
                return
    db.execute(
        'INSERT INTO changelog (ts, device, action, note_id, summary) '
        'VALUES (?, ?, ?, ?, ?)', (ts, dev, action, note_id, summary))


# ---------------------------------------------------------------- auth + CSRF

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('auth'):
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def check_csrf():
    if request.method == 'POST':
        token = session.get('csrf_token')
        if not token or request.form.get('csrf_token') != token:
            abort(400, 'Neplatný CSRF token.')


@app.context_processor
def inject_csrf():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return {'csrf_token': session['csrf_token']}


@app.template_filter('localdt')
def localdt(iso_str):
    """ISO UTC řetězec → 'd. m. YYYY HH:MM' v pražském čase."""
    try:
        dt = datetime.fromisoformat(iso_str).astimezone(LOCAL_TZ)
        return f'{dt.day}. {dt.month}. {dt.year} {dt:%H:%M}'
    except (ValueError, TypeError):
        return iso_str


# ---------------------------------------------------------------- routy

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('auth'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        if PASSWORD_HASH and check_password_hash(
                PASSWORD_HASH, request.form.get('password', '')):
            session.permanent = True
            session['auth'] = True
            target = request.args.get('next', '')
            if not target.startswith('/'):
                target = url_for('index')
            return redirect(target)
        flash('Špatné heslo.')
    return render_template('login.html')


@app.post('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    db = get_db()
    notes = db.execute(
        'SELECT id, title, body, updated_at FROM notes '
        'ORDER BY updated_at DESC').fetchall()
    row = db.execute(
        'SELECT body, updated_at FROM scratchpad WHERE id = 1').fetchone()
    return render_template('index.html', notes=notes,
                           scratch_body=row['body'] if row else '',
                           scratch_ts=row['updated_at'] if row else '',
                           version=get_version(db))


@app.get('/version')
@login_required
def version():
    return {'v': get_version(get_db())}


@app.route('/log')
@login_required
def changelog():
    entries = get_db().execute(
        'SELECT * FROM changelog ORDER BY id DESC LIMIT 100').fetchall()
    return render_template('log.html', entries=entries)


@app.post('/scratchpad')
@login_required
def save_scratchpad():
    db = get_db()
    row = db.execute(
        'SELECT body, updated_at FROM scratchpad WHERE id = 1').fetchone()
    base = request.form.get('base')
    # ochrana proti přepsání změny z jiného zařízení (pokud klient poslal
    # base a nevyžádal si force)
    if (row and base is not None and not request.form.get('force')
            and base != row['updated_at']):
        return {'ok': False, 'server_body': row['body'],
                'ts': row['updated_at'], 'saved': localdt(row['updated_at']),
                'v': get_version(db)}, 409
    ts = now_iso()
    db.execute(
        'INSERT OR REPLACE INTO scratchpad (id, body, updated_at) '
        'VALUES (1, ?, ?)', (request.form.get('body', ''), ts))
    log_change(db, 'scratch')
    db.commit()
    return {'ok': True, 'saved': localdt(ts), 'ts': ts, 'v': get_version(db)}


@app.route('/new', methods=['GET', 'POST'])
@login_required
def new_note():
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if not body:
            flash('Poznámka nemůže být prázdná.')
        else:
            title = request.form.get('title', '').strip()
            db = get_db()
            cur = db.execute(
                'INSERT INTO notes (title, body, created_at, updated_at) '
                'VALUES (?, ?, ?, ?)', (title, body, now_iso(), now_iso()))
            log_change(db, 'create', cur.lastrowid,
                       title or body.splitlines()[0][:60])
            db.commit()
            return redirect(url_for('show_note', note_id=cur.lastrowid))
    return render_template('edit.html', note=None)


def get_note_or_404(note_id):
    note = get_db().execute(
        'SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
    if note is None:
        abort(404)
    return note


@app.route('/note/<int:note_id>')
@login_required
def show_note(note_id):
    return render_template('note.html', note=get_note_or_404(note_id))


@app.route('/note/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = get_note_or_404(note_id)
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        title = request.form.get('title', '').strip()
        if not body:
            flash('Poznámka nemůže být prázdná.')
        elif request.form.get('base') != note['updated_at']:
            # poznámka se mezitím změnila z jiného zařízení – nesahat na ni,
            # nechat uživateli jeho text a upozornit; opětovné Uložit
            # už projde (base se přenastaví na aktuální verzi)
            flash('Pozor: poznámka byla mezitím změněna z jiného zařízení. '
                  'Tvoje verze NENÍ uložena. Zkontroluj text – opětovné '
                  '„Uložit“ přepíše verzi ze serveru tímto textem.')
            draft = {'id': note_id, 'title': title, 'body': body,
                     'updated_at': note['updated_at']}
            return render_template('edit.html', note=draft)
        else:
            db = get_db()
            ts = now_iso()
            db.execute(
                'UPDATE notes SET title = ?, body = ?, updated_at = ? '
                'WHERE id = ?', (title, body, ts, note_id))
            log_change(db, 'update', note_id,
                       title or body.splitlines()[0][:60])
            db.commit()
            return redirect(url_for('show_note', note_id=note_id))
    return render_template('edit.html', note=note)


@app.post('/note/<int:note_id>/delete')
@login_required
def delete_note(note_id):
    note = get_note_or_404(note_id)
    db = get_db()
    db.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    log_change(db, 'delete', note_id,
               note['title'] or note['body'].splitlines()[0][:60])
    db.commit()
    flash('Poznámka smazána.')
    return redirect(url_for('index'))


# ---------------------------------------------------------------- start

init_db()

if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == 'hash':
        print(generate_password_hash(sys.argv[2]))
        sys.exit(0)
    # lokální vývoj běží po HTTP → Secure cookie by nefungovala
    app.config['SESSION_COOKIE_SECURE'] = False
    if not PASSWORD_HASH:
        _dev_pw = 'dev'
        PASSWORD_HASH = generate_password_hash(_dev_pw)
        print(f'NOTES_PASSWORD_HASH není nastaven – dočasné heslo: {_dev_pw}')
    app.run(host='0.0.0.0', port=5000, debug=True)
