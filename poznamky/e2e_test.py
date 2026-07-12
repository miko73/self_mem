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


total = 0


def check(name, cond, detail=''):
    global total
    total += 1
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
r = s.post(BASE + '/scratchpad', data={'body': 'scratch-obsah-1 ěščř',
                                       'csrf_token': csrf})
check('scratchpad: uložení vrací ok', r.status_code == 200 and r.json().get('ok'))
r = s.get(BASE + '/')
check('scratchpad: obsah se načte na hlavní stránce', 'scratch-obsah-1 ěščř' in r.text)
r = s.post(BASE + '/scratchpad', data={'body': 'scratch-obsah-2', 'csrf_token': csrf})
r = s.get(BASE + '/')
check('scratchpad: přepsání obsahu',
      'scratch-obsah-2' in r.text and 'scratch-obsah-1' not in r.text)
r = s.post(BASE + '/scratchpad', data={'body': 'x'})
check('scratchpad: POST bez CSRF → 400', r.status_code == 400, f'{r.status_code}')

# 12b2. formátování rychlého bloku – sanitizace HTML
evil = ('<b>tučné</b><blockquote>odsazené</blockquote>'
        '<script>alert(99)</script>'
        '<a href="https://example.com/x">dobrý odkaz</a>'
        '<a href="javascript:alert(1)" onclick="alert(2)">zlý odkaz</a>'
        '<img src=x onerror="alert(3)">')
r = s.post(BASE + '/scratchpad', data={'body': evil, 'csrf_token': csrf})
t = s.get(BASE + '/').text
check('formátování: povolené tagy zůstávají',
      '<b>tučné</b>' in t and '<blockquote>odsazené</blockquote>' in t
      and '<a href="https://example.com/x">dobrý odkaz</a>' in t)
check('formátování: nebezpečné věci odstraněny',
      'alert(99)' not in t and 'javascript:' not in t
      and 'onclick' not in t and 'onerror' not in t and '<img' not in t
      and 'zlý odkaz' in t)

# 12c. verze stavu a konflikty rychlého bloku
v0 = s.get(BASE + '/version').json()['v']
r = s.post(BASE + '/scratchpad', data={'body': 'verze A', 'csrf_token': csrf})
ts_a = r.json()['ts']
check('version se změnou zvyšuje', s.get(BASE + '/version').json()['v'] > v0)
r = s.post(BASE + '/scratchpad',
           data={'body': 'verze B', 'csrf_token': csrf, 'base': ts_a})
check('scratchpad: uložení s aktuálním base projde', r.status_code == 200)
r = s.post(BASE + '/scratchpad',
           data={'body': 'verze C', 'csrf_token': csrf, 'base': ts_a})
check('scratchpad: zastaralý base → 409 + obsah serveru',
      r.status_code == 409 and r.json().get('server_body') == 'verze B',
      f'{r.status_code}')
r = s.post(BASE + '/scratchpad', data={'body': 'verze C', 'csrf_token': csrf,
                                       'base': ts_a, 'force': '1'})
check('scratchpad: force přepíše i při konfliktu', r.status_code == 200)

# 12d. konflikt při editaci poznámky
r = s.post(BASE + '/new', data={'title': 'Konfliktní', 'body': 'původní text',
                                'csrf_token': csrf})
conflict_id = re.search(r'/note/(\d+)$', r.url).group(1)
html = s.get(f'{BASE}/note/{conflict_id}/edit').text
old_base = re.search(r'name="base" value="([^"]*)"', html).group(1)
# „druhé zařízení“ mezitím poznámku upraví
s.post(f'{BASE}/note/{conflict_id}/edit',
       data={'title': 'Konfliktní', 'body': 'změna z druhého zařízení',
             'csrf_token': csrf, 'base': old_base})
# „první zařízení“ ukládá se zastaralým base
r = s.post(f'{BASE}/note/{conflict_id}/edit',
           data={'title': 'Konfliktní', 'body': 'změna z prvního zařízení',
                 'csrf_token': csrf, 'base': old_base})
check('edit: zastaralý base → varování, neuloženo',
      'mezitím změněna' in r.text
      and 'změna z druhého zařízení'
      in s.get(f'{BASE}/note/{conflict_id}').text)
# opětovné uložení (formulář už nese aktuální base) projde
new_base = re.search(r'name="base" value="([^"]*)"', r.text).group(1)
r = s.post(f'{BASE}/note/{conflict_id}/edit',
           data={'title': 'Konfliktní', 'body': 'změna z prvního zařízení',
                 'csrf_token': csrf, 'base': new_base})
check('edit: druhé uložení s novým base projde',
      'změna z prvního zařízení' in r.text)
s.post(f'{BASE}/note/{conflict_id}/delete', data={'csrf_token': csrf})

# 12e. protokol změn
r = s.get(BASE + '/log')
check('protokol: stránka funguje a obsahuje záznamy',
      r.status_code == 200 and 'vytvořeno' in r.text and 'smazáno' in r.text
      and 'Konfliktní' in r.text and 'rychlý blok' in r.text)

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
print(f'Všech {total} kontrol prošlo.')
