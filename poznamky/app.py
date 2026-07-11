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
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


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
    row = db.execute('SELECT body FROM scratchpad WHERE id = 1').fetchone()
    return render_template('index.html', notes=notes,
                           scratch_body=row['body'] if row else '')


@app.post('/scratchpad')
@login_required
def save_scratchpad():
    db = get_db()
    db.execute(
        'INSERT OR REPLACE INTO scratchpad (id, body, updated_at) '
        'VALUES (1, ?, ?)',
        (request.form.get('body', ''), now_iso()))
    db.commit()
    return {'ok': True, 'saved': localdt(now_iso())}


@app.route('/new', methods=['GET', 'POST'])
@login_required
def new_note():
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if not body:
            flash('Poznámka nemůže být prázdná.')
        else:
            db = get_db()
            cur = db.execute(
                'INSERT INTO notes (title, body, created_at, updated_at) '
                'VALUES (?, ?, ?, ?)',
                (request.form.get('title', '').strip(), body,
                 now_iso(), now_iso()))
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
        if not body:
            flash('Poznámka nemůže být prázdná.')
        else:
            db = get_db()
            db.execute(
                'UPDATE notes SET title = ?, body = ?, updated_at = ? '
                'WHERE id = ?',
                (request.form.get('title', '').strip(), body,
                 now_iso(), note_id))
            db.commit()
            return redirect(url_for('show_note', note_id=note_id))
    return render_template('edit.html', note=note)


@app.post('/note/<int:note_id>/delete')
@login_required
def delete_note(note_id):
    get_note_or_404(note_id)
    db = get_db()
    db.execute('DELETE FROM notes WHERE id = ?', (note_id,))
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
