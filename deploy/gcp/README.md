# Nasazení Poznámek na Google Cloud VM

Aplikace `poznamky/` běží na stejné bezplatné VM jako PostgreSQL pro mikoucto:

| Položka | Hodnota |
|---|---|
| Projekt / VM / zóna | `pg-free-michal` / `pg-free` / `us-central1-a` (e2-micro, Ubuntu 24.04) |
| Web | Caddy (HTTPS Let's Encrypt) → gunicorn `127.0.0.1:8000` → Flask |
| Adresa | `https://<subdoména>.duckdns.org` (IP se aktualizuje každých 5 min) |
| Kód | `/opt/self_mem` (git clone z GitHubu), venv `/opt/self_mem/venv` |
| Data | `/var/lib/poznamky/` – `notes.db`, `anthropic_key.txt`, `secret_key.txt`, `backup/` |
| Google Drive | `/opt/self_mem/poznamky/google_auth.json` |
| Konfigurace | `/etc/poznamky.env` (`NOTES_DB`, `NOTES_PASSWORD_HASH`, …), `/etc/duckdns.env` |
| Služby | `poznamky`, `caddy`, `duckdns.timer`, `poznamky-backup.timer` (denně 3:30, 14 záloh) |

Firewall otevírá pouze 80/443 (pravidlo `allow-web`, tag `web`). Port 5432
zůstává zavřený, PostgreSQL ani tunel mikoucto se nemění.

Všechny příkazy spouštějte v PowerShellu z kořene repozitáře. gcloud se hledá
stejně jako v mikoucto (včetně `C:\dev\mikoucto\tools\_download\gcloud-portable`)
a musí být přihlášený (`gcloud auth login`).

## 1. Příprava VM (PythonAnywhere dál běží)

1. Na https://www.duckdns.org se přihlaste, založte subdoménu (např. `mojepoznamky`)
   a zkopírujte **token**.
2. Spusťte:

   ```powershell
   .\deploy\gcp\00-priprava-vm.ps1 -Subdomena mojepoznamky
   ```

   Skript se zeptá na DuckDNS token a heslo do aplikace (Enter = převzít původní
   heslo z PythonAnywhere v kroku 3). Vytvoří pravidlo firewallu, nainstaluje
   Caddy, Python venv, gunicorn, systemd služby a zálohy. Lze ho spustit opakovaně.
3. Otevřete `https://mojepoznamky.duckdns.org` – musí se ukázat přihlášení
   s platným certifikátem (první vydání trvá 1–2 minuty).

## 2. Zmrazení a export z PythonAnywhere

1. PythonAnywhere → **Web** → **Disable** (od teď nevznikají nové zápisy).
2. **Consoles → Bash**:

   ```bash
   cd ~/self_mem/poznamky && python3 -c "import sqlite3;sqlite3.connect('notes.db').backup(sqlite3.connect('notes_export.db'))"
   ```

3. **Account → API token** – vytvořit a zkopírovat token.
4. Ve Windows:

   ```powershell
   .\deploy\gcp\01-export-pa.ps1
   ```

   Stáhne `notes_export.db`, `google_auth.json`, `anthropic_key.txt`,
   `secret_key.txt` a proměnné z WSGI souboru (hash hesla) do
   `%USERPROFILE%\poznamky-migrace` a vypíše počty řádků.

## 3. Import na VM

```powershell
.\deploy\gcp\02-import-vm.ps1
```

Skript zastaví aplikaci, případnou DB na VM odloží do `backup/`, nahraje data
s právy jen pro uživatele `poznamky`, převezme proměnné z WSGI, aplikaci spustí
a vypíše počty řádků – musí odpovídat kroku 2.

## 4. Ověření

- přihlášení původním heslem, poznámky, blok a protokol změn odpovídají PA,
- záložka 🤖 AI načte soubory z Google Drive,
- záložka 📷 Foto: testovací fotka se rozpozná a přesune na Drive,
- na mobilu odebrat starou PWA a znovu **Přidat na plochu** z nové adresy,
- `Test-NetConnection <IP VM> -Port 5432` musí selhat (port je zavřený).

Pak smažte `%USERPROFILE%\poznamky-migrace` (obsahuje tajné údaje).
Web app na PythonAnywhere nechte ~2 týdny vypnutou jako zálohu; **návrat zpět** =
na PA kliknout **Enable**. Potom ji smažte.

`poznamky/e2e_test.py` se proti produkci nespouští (zapisuje data a používá heslo `dev`).

## Aktualizace po změně kódu

Změny pushnout na GitHub (`master`) a spustit:

```powershell
.\deploy\gcp\03-aktualizace.ps1
```

## Provoz a diagnostika

```powershell
& 'C:\dev\mikoucto\gcloud.ps1' compute ssh michal_kocandrle@pg-free --project=pg-free-michal --zone=us-central1-a
```

```bash
systemctl status poznamky caddy duckdns.timer poznamky-backup.timer
journalctl -u poznamky -n 50        # chyby aplikace
journalctl -u caddy -n 50           # certifikát, HTTPS
free -m                             # RAM sdílená s PostgreSQL
ls -l /var/lib/poznamky/backup      # denní zálohy
```

Obnova ze zálohy: `sudo systemctl stop poznamky`, rozbalit
`gunzip -c backup/notes-YYYY-MM-DD.db.gz > notes.db` (jako `poznamky`), `sudo systemctl start poznamky`.

Změna hesla: znovu spustit `00-priprava-vm.ps1 -Subdomena … -BezFirewallu` a zadat
nové heslo (hash se uloží do `/etc/poznamky.env` v jednoduchých uvozovkách).

Po zastavení a spuštění VM se veřejná IP změní; DuckDNS ji do 5 minut aktualizuje.
Odchozí data free tieru jsou 1 GB/měsíc (náhledy fotek jdou přes server).
