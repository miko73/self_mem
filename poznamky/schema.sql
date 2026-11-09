CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS changelog (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    device  TEXT NOT NULL DEFAULT '',
    action  TEXT NOT NULL,            -- create / update / delete / scratch
    note_id INTEGER,
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS scratchpad (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    body       TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

-- vstup z kamery: fotky nahrané na Drive a jejich zařazení
CREATE TABLE IF NOT EXISTS kamera (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,              -- ISO 8601 UTC
    file_id   TEXT NOT NULL,              -- ID souboru na Google Drive
    nazev     TEXT NOT NULL DEFAULT '',
    kategorie TEXT NOT NULL DEFAULT '',   -- el_en / voda / plyn / vaha / jine
    hodnota   TEXT NOT NULL DEFAULT '',   -- odečtená hodnota („12345.678“)
    jistota   REAL,
    popis     TEXT NOT NULL DEFAULT '',
    osoba     TEXT NOT NULL DEFAULT '',
    slozka    TEXT NOT NULL DEFAULT '',   -- cesta na Drive, kde fotka leží
    odkaz     TEXT NOT NULL DEFAULT '',   -- webViewLink
    stav      TEXT NOT NULL               -- ceka / ceka_osoba / zarazeno
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT DEFAULT '',
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
