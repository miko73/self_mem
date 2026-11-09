# Poznámky

Jednoduchý osobní poznámkový blok – Flask + SQLite + PWA.
Návrh viz [../NAVRH.md](../NAVRH.md).

## Lokální spuštění

```powershell
pip install -r requirements.txt
python app.py
```

Běží na http://127.0.0.1:5000. Bez nastaveného `NOTES_PASSWORD_HASH`
se použije dočasné heslo `dev` (vypíše se do konzole).

Testy (proti běžícímu serveru): `python e2e_test.py`

## Záložka 🤖 AI (poznámky z Google Drive)

Záložka zobrazuje a edituje soubory ve složce na Google Drive
(poznámky ukládané z AI relací). Google dokumenty se čtou a ukládají
jako markdown (převod dělá Google).

### Jednorázové propojení

1. Na https://console.cloud.google.com vytvořit projekt a povolit
   **Google Drive API** (APIs & Services → Library).
2. **OAuth consent screen**: typ External, vyplnit název, uložit
   a poté **Publish app** (jinak refresh token vyprší po 7 dnech).
3. **Credentials → Create Credentials → OAuth client ID**, typ
   **Desktop app**. Zkopírovat Client ID a Client secret.
4. Lokálně spustit:

```powershell
python google_auth_setup.py
```

Skript otevře prohlížeč a po povolení uloží `google_auth.json` vedle
`app.py`. Soubor je v `.gitignore` – **do gitu nepatří**.

5. Na PythonAnywhere nahrát `google_auth.json` do
   `/home/miko73/self_mem/poznamky` (Files tab) a kliknout **Reload**.

Jinou složku lze nastavit env proměnnou `GDRIVE_FOLDER_ID`
(výchozí je složka „AI poznámky“). Místo souboru jdou použít i env
proměnné `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`,
`GDRIVE_REFRESH_TOKEN` (ve WSGI souboru).

## Záložka 📷 Foto (vstup z kamery)

Vyfocená fotka se uloží na Google Drive do složky `vstup/`, Claude ji
rozpozná a přesune podle kategorie (definice v `kamera.py`, `KATEGORIE`):

| Co je na fotce | Cílová složka |
|---|---|
| elektroměr | `stavy_meridel/el_en` |
| vodoměr | `stavy_meridel/voda` |
| plynoměr | `stavy_meridel/plyn` |
| osobní váha | `osobni/hmotnost/<osoba>` – aplikace se zeptá, kdo se vážil (nabídne existující podsložky) |

Soubor se přejmenuje na např. `2026-11-08_0712_plyn_12345.678m3.jpg`,
odečtená hodnota se uloží i do databáze (tabulka `kamera`). Když si AI
není jistá (< 70 %) nebo jde o něco jiného, fotka zůstane ve `vstup/`
a zařadí se ručně tlačítkem. Chybějící složky se založí automaticky.

- Cesty se počítají od kořene „Můj disk“; jiný kořen = env proměnná
  `GDRIVE_DOCS_ROOT_ID` (ID složky).
- AI klíč: při prvním otevření záložky aplikace vyzve k zadání API klíče
  z https://platform.claude.com (předplatné claude.ai v cizích aplikacích
  použít nejde). Klíč se ověří a uloží do `anthropic_key.txt` vedle
  databáze; alternativně env proměnná `ANTHROPIC_API_KEY`.
- Na PythonAnywhere: `pip3 install --user anthropic`.

## Nasazení na PythonAnywhere (free)

### Krok 1 – účet

Založit účet na https://www.pythonanywhere.com (free, bez karty).

### Krok 2 – kód a hash hesla

V **Consoles → Bash**:

```bash
git clone https://github.com/miko73/self_mem.git
pip3 install --user flask anthropic
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('MOJE-HESLO'))"
```

Vypsaný hash si zkopírovat.

### Krok 3 – web app

**Web → Add a new web app → Manual configuration → Python 3.12**
(nebo nejvyšší nabízená). Poté v sekci **Code** nastavit:

- Source code: `/home/miko73/self_mem/poznamky`

### Krok 4 – WSGI soubor

Kliknout na **WSGI configuration file** a celý obsah nahradit.
**Pozor: žádný řádek nesmí začínat mezerou** (jinak `IndentationError`):

```python
import os, sys

sys.path.insert(0, '/home/miko73/self_mem/poznamky')
os.environ['NOTES_PASSWORD_HASH'] = 'sem-vlozit-hash-z-kroku-2'

from app import app as application
```

### Krok 5 – spuštění

Tlačítko **Reload** → aplikace běží na https://miko73.pythonanywhere.com.

### Aktualizace po změně kódu

```bash
cd ~/self_mem && git pull
```
a na záložce Web kliknout **Reload**.

### Důležité u free účtu

- 1× za 3 měsíce kliknout na **Run until 3 months from today** (Web tab),
  jinak se aplikace uspí.
- Databáze je soubor `poznamky/notes.db` – záloha = stáhnout tento soubor
  (Files tab).

## Instalace na mobil (PWA)

Na Androidu otevřít adresu v Chrome → menu ⋮ → **Přidat na plochu**
(„Instalovat aplikaci“). Na iPhonu v Safari → Sdílet → **Přidat na plochu**.
