# Návrh: Sada jednoduchých aplikací

Cíl: sada malých osobních aplikací, maximálně jednoduchých, dostupných
z jakéhokoli zařízení (Windows, Android, později iPhone) přes webový prohlížeč.

**První aplikace: Poznámky (poznámkový blok)**

---

## Principy pro celou sadu

1. **Web-first** – žádné nativní aplikace. Responzivní web + PWA
   (ikona na ploše mobilu, chová se jako appka).
2. **Jeden uživatel** – ochrana jedním heslem, žádná registrace/správa účtů.
3. **Žádný build systém** – čisté HTML/CSS/JS, server-renderované šablony.
4. **Jeden soubor = databáze** – SQLite, snadná záloha (zkopírovat soubor).
5. Každá další aplikace ze sady opakuje stejný vzor (stack, auth, deploy).

## Stack

| Vrstva | Volba | Proč |
|---|---|---|
| Backend | **Flask** (Python 3.12) | Jednoduchý, WSGI → funguje na PythonAnywhere free |
| Databáze | **SQLite** | Bez serveru, jeden soubor, na PA trvalý disk |
| Šablony | **Jinja2** (součást Flasku) | Server-rendered, žádný JS framework |
| Frontend | Responzivní HTML + minimum JS | Funguje všude |
| Mobil | **PWA** (manifest.json) | „Přidat na plochu“ na Androidu i iOS |
| Hosting | **PythonAnywhere free** | Zdarma, trvalý disk, HTTPS, bez karty |

Adresa: `https://<uzivatel>.pythonanywhere.com`

## Poznámky – fáze 1 (MVP)

### Funkce
- Vytvořit poznámku (titulek volitelný + text)
- Seznam poznámek řazený od nejnovější
- Zobrazit / upravit / smazat poznámku
- Přihlášení jedním heslem (session cookie, platnost ~30 dní)

### Datový model
```sql
CREATE TABLE notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT DEFAULT '',
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL,   -- ISO 8601 UTC
    updated_at TEXT NOT NULL
);
```

### Routy
| Metoda | Cesta | Akce |
|---|---|---|
| GET | `/` | seznam poznámek |
| GET/POST | `/new` | nová poznámka |
| GET | `/note/<id>` | detail |
| GET/POST | `/note/<id>/edit` | úprava |
| POST | `/note/<id>/delete` | smazání |
| GET/POST | `/login` | přihlášení heslem |

### UI
- Jedna sloupcová responzivní stránka (max-width ~600 px, na mobilu 100 %).
- Seznam: titulek (nebo první řádek textu) + datum, klik → detail.
- Nahoře tlačítko „+ Nová poznámka“.
- Žádné CSS frameworky – jeden ručně psaný `style.css` (~100 řádků).

### Bezpečnost
- Heslo uloženo jako hash (env proměnná / config mimo git).
- Vše za HTTPS (řeší PythonAnywhere).
- Session cookie `HttpOnly` + `Secure`.
- CSRF ochrana u POST formulářů (jednoduchý token v session).

## Struktura repozitáře

```
self_mem/
├── NAVRH.md
└── poznamky/
    ├── app.py            # celý Flask backend (jeden soubor)
    ├── schema.sql
    ├── templates/
    │   ├── base.html
    │   ├── index.html
    │   ├── note.html
    │   ├── edit.html
    │   └── login.html
    └── static/
        ├── style.css
        ├── manifest.json  # PWA
        └── icon.png
```

Další aplikace ze sady = další složka vedle `poznamky/`, stejný vzor.

## Fáze 2 (později, mimo MVP)

- Fulltextové hledání (SQLite FTS5)
- Štítky / kategorie
- Markdown rendering
- Export/záloha (stažení DB souboru)

## Deploy (PythonAnywhere)

1. Založit free účet na pythonanywhere.com
2. `git clone` repozitáře v konzoli PA
3. Web app → Manual config → Python 3.12 → WSGI soubor nasměrovat na `app.py`
4. Nastavit env proměnnou s hashem hesla
5. Aktualizace: `git pull` + tlačítko Reload

Pozn.: free účet vyžaduje 1× za 3 měsíce kliknout na „Run until 3 months
from today“, jinak se web uspí.
