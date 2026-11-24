# self_mem – sada jednoduchých osobních aplikací

Malé webové aplikace pro osobní použití, dostupné z počítače i mobilu
(PWA). Společný vzor: Flask + SQLite + server-renderované HTML, hosting
na Google Cloud VM `pg-free` (Caddy + gunicorn, [deploy/gcp/](deploy/gcp/README.md));
dříve PythonAnywhere free. Detaily v [NAVRH.md](NAVRH.md).

| Aplikace | Popis | Stav |
|---|---|---|
| [poznamky/](poznamky/) | Poznámkový blok | MVP hotové |
