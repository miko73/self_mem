# -*- coding: utf-8 -*-
"""End-to-end test proti běžícímu serveru (python app.py, heslo 'dev')."""
import io
import re
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://127.0.0.1:5000'
s = requests.Session()
failed = []


def check(name, cond, detail=''):
    print(('OK  ' if cond else 'FAIL') + f' {name}' + (f' – {detail}' if detail and not cond else ''))
    if not cond:
        failed.append(name)


def get_csrf(html):
    m = re.search(r'name="csrf_token" value="([0-9a-f]+)"', html)
    return m.group(1) if m else None


# 1. nepřihlášený uživatel je přesměrován na /login
r = s.get(BASE + '/', allow_redirects=False)
check('nepřihlášený → redirect na /login',
      r.status_code == 302 and '/login' in r.headers['Location'], f'{r.status_code}')

# 2. login stránka obsahuje CSRF token
r = s.get(BASE + '/login')
csrf = get_csrf(r.text)
check('login stránka + CSRF token', r.status_code == 200 and csrf is not None)

# 3. špatné heslo je odmítnuto
r = s.post(BASE + '/login', data={'password': 'spatne', 'csrf_token': csrf})
check('špatné heslo odmítnuto', 'Špatné heslo' in r.text)

# 4. POST bez CSRF tokenu → 400
r = s.post(BASE + '/login', data={'password': 'dev'})
check('POST bez CSRF → 400', r.status_code == 400, f'{r.status_code}')

# 5. správné heslo přihlásí
r = s.post(BASE + '/login', data={'password': 'dev', 'csrf_token': csrf})
check('přihlášení funguje', 'Nová' in r.text and r.url.rstrip('/') == BASE)

# 6. vytvoření poznámky
csrf = get_csrf(s.get(BASE + '/new').text)
r = s.post(BASE + '/new', data={
    'title': 'Testovací poznámka', 'body': 'První řádek\nDruhý řádek – ěščřžýáíé',
    'csrf_token': csrf})
m = re.search(r'/note/(\d+)$', r.url)
check('vytvoření poznámky → detail', m is not None and 'Testovací poznámka' in r.text, r.url)
note_id = m.group(1) if m else None

# 7. prázdná poznámka je odmítnuta
r = s.post(BASE + '/new', data={'title': 'x', 'body': '   ', 'csrf_token': csrf})
check('prázdná poznámka odmítnuta', 'nemůže být prázdná' in r.text)

# 8. poznámka je v seznamu
r = s.get(BASE + '/')
check('poznámka v seznamu', 'Testovací poznámka' in r.text)

# 9. úprava poznámky
r = s.post(f'{BASE}/note/{note_id}/edit', data={
    'title': 'Upravený titulek', 'body': 'Nový obsah', 'csrf_token': csrf})
check('úprava poznámky', 'Upravený titulek' in r.text and 'Nový obsah' in r.text)

# 10. XSS – obsah se escapuje
r = s.post(BASE + '/new', data={
    'title': '', 'body': '<script>alert(1)</script>', 'csrf_token': csrf})
check('XSS escapováno', '<script>alert(1)</script>' not in r.text
      and '&lt;script&gt;' in r.text)
xss_id = re.search(r'/note/(\d+)$', r.url).group(1)

# 11. poznámka bez titulku se v seznamu ukáže prvním řádkem těla
r = s.get(BASE + '/')
check('bez titulku → první řádek v seznamu', '&lt;script&gt;alert(1)&lt;/script&gt;' in r.text)

# 12. smazání (kontroluje zmizení testovacích poznámek, DB nemusí být prázdná)
for nid in (note_id, xss_id):
    s.post(f'{BASE}/note/{nid}/delete', data={'csrf_token': csrf})
r = s.get(BASE + '/')
check('smazání poznámek',
      'Upravený titulek' not in r.text and 'alert(1)' not in r.text)

# 12b. rychlý blok – uložení a načtení
r = s.post(BASE + '/scratchpad', data={'body': 'rozepsaný text ěščř',
                                       'csrf_token': csrf})
check('scratchpad: uložení vrací ok', r.status_code == 200 and r.json().get('ok'))
r = s.get(BASE + '/')
check('scratchpad: obsah se načte na hlavní stránce', 'rozepsaný text ěščř' in r.text)
r = s.post(BASE + '/scratchpad', data={'body': 'přepsáno', 'csrf_token': csrf})
r = s.get(BASE + '/')
check('scratchpad: přepsání obsahu',
      'přepsáno' in r.text and 'rozepsaný text' not in r.text)
r = s.post(BASE + '/scratchpad', data={'body': 'x'})
check('scratchpad: POST bez CSRF → 400', r.status_code == 400, f'{r.status_code}')

# 13. neexistující poznámka → 404
r = s.get(BASE + '/note/99999')
check('neexistující poznámka → 404', r.status_code == 404, f'{r.status_code}')

# 14. odhlášení
csrf = get_csrf(s.get(BASE + '/').text)
r = s.post(BASE + '/logout', data={'csrf_token': csrf}, allow_redirects=False)
r2 = s.get(BASE + '/', allow_redirects=False)
check('odhlášení', r.status_code == 302 and r2.status_code == 302)

# 15. statika + PWA soubory
for path in ('/static/style.css', '/static/manifest.json', '/static/sw.js',
             '/static/icon-192.png', '/static/icon-512.png'):
    r = s.get(BASE + path)
    check(f'statika {path}', r.status_code == 200, f'{r.status_code}')

print()
if failed:
    print(f'SELHALO: {len(failed)} testů: {failed}')
    sys.exit(1)
print('Všech 23 kontrol prošlo.')
