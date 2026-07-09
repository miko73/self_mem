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

## Nasazení na PythonAnywhere (free)

1. Založit účet na https://www.pythonanywhere.com (free, bez karty).
2. V **Consoles → Bash**:
   ```bash
   git clone https://github.com/<uzivatel>/self_mem.git
   pip3 install --user flask
   python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('MOJE-HESLO'))"
   ```
   Vypsaný hash si zkopírovat.
3. **Web → Add a new web app → Manual configuration → Python 3.12** (nebo nejvyšší nabízená).
4. V sekci **Code** nastavit:
   - Source code: `/home/<uzivatel>/self_mem/poznamky`
5. Kliknout na **WSGI configuration file** a obsah nahradit:
   ```python
   import os, sys

   sys.path.insert(0, '/home/<uzivatel>/self_mem/poznamky')
   os.environ['NOTES_PASSWORD_HASH'] = 'sem-vlozit-hash-z-kroku-2'

   from app import app as application
   ```
6. Tlačítko **Reload** → aplikace běží na `https://<uzivatel>.pythonanywhere.com`.

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
