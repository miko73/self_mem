# -*- coding: utf-8 -*-
"""Vstup z kamery – AI rozpoznání fotky a určení cílové složky na Drive.

Klíč k Claude API (v tomto pořadí):
  1. env proměnná ANTHROPIC_API_KEY
  2. soubor anthropic_key.txt vedle databáze (uloží ho stránka nastavení)
"""
import base64
import json
import os
from pathlib import Path

import sys

try:
    import anthropic
    _NO_LIB = ''
except ImportError as e:   # bez knihovny poběží zbytek aplikace dál
    anthropic = None
    _NO_LIB = (f'Nelze načíst knihovnu anthropic ({e!r}; Python '
               f'{sys.version.split()[0]}, {sys.executable}).')

MODEL = 'claude-opus-5-5'
MIN_JISTOTA = 0.7          # pod touto hodnotou se fotka zařadí ručně
VSTUP_SLOZKA = 'vstup'     # sem se fotka uloží hned po vyfocení
VAHA_SLOZKA = 'osobni/hmotnost'

# Kategorie: klíč → cílová složka, popis pro model, jednotka.
# 'osoba': True = po rozpoznání se ještě zeptá, do které podsložky (kdo).
KATEGORIE = {
    'el_en': {'nazev': 'Elektroměr', 'slozka': 'stavy_meridel/el_en',
              'jednotka': 'kWh',
              'popis': 'elektroměr – odečti stav počítadla v kWh '
                       '(u dvoutarifního elektroměru stav aktuálně '
                       'zobrazeného tarifu)'},
    'voda': {'nazev': 'Vodoměr', 'slozka': 'stavy_meridel/voda',
             'jednotka': 'm3',
             'popis': 'vodoměr – odečti stav v m³ včetně desetinných míst '
                      '(červená kolečka/číslice jsou desetinná místa)'},
    'plyn': {'nazev': 'Plynoměr', 'slozka': 'stavy_meridel/plyn',
             'jednotka': 'm3',
             'popis': 'plynoměr – odečti stav v m³ včetně desetinných míst '
                      '(číslice za čárkou bývají v červeném poli)'},
    'vaha': {'nazev': 'Váha (hmotnost)', 'slozka': VAHA_SLOZKA,
             'jednotka': 'kg', 'osoba': True,
             'popis': 'displej osobní váhy – odečti hmotnost v kg'},
}

_KEY_FILE = None   # nastaví app.py (vedle databáze)


class AIError(Exception):
    """Chyba AI analýzy (zobrazí se uživateli)."""


def set_key_dir(directory):
    global _KEY_FILE
    _KEY_FILE = Path(directory) / 'anthropic_key.txt'


def get_key():
    key = os.environ.get('ANTHROPIC_API_KEY')
    if key:
        return key
    if _KEY_FILE and _KEY_FILE.exists():
        return _KEY_FILE.read_text(encoding='utf-8').strip() or None
    return None


def save_key(key):
    _KEY_FILE.write_text(key.strip(), encoding='utf-8')


def delete_key():
    if _KEY_FILE and _KEY_FILE.exists():
        _KEY_FILE.unlink()


def verify_key(key):
    """Ověří klíč (výpis modelů nic nestojí). Vrátí None nebo text chyby."""
    if anthropic is None:
        return _NO_LIB
    try:
        anthropic.Anthropic(api_key=key, max_retries=0,
                            timeout=20).models.list(limit=1)
    except anthropic.AuthenticationError:
        return 'Klíč je neplatný.'
    except anthropic.PermissionDeniedError:
        return 'Klíč nemá oprávnění k API.'
    except anthropic.APIConnectionError as e:
        return f'Nepodařilo se spojit s api.anthropic.com ({e.__cause__!r}).'
    except anthropic.APIStatusError as e:
        return f'Chyba API {e.status_code}: {e.message}'
    return None


_SCHEMA = {
    'type': 'object',
    'properties': {
        'kategorie': {'type': 'string', 'enum': [*KATEGORIE, 'jine']},
        'hodnota': {'type': 'string'},
        'jistota': {'type': 'number'},
        'popis': {'type': 'string'},
    },
    'required': ['kategorie', 'hodnota', 'jistota', 'popis'],
    'additionalProperties': False,
}


def _system_prompt():
    radky = '\n'.join(f'- {k}: {v["popis"]}' for k, v in KATEGORIE.items())
    return (
        'Třídíš fotky z mobilu do osobního archivu. Urči, co je na fotce, '
        'podle těchto kategorií:\n'
        f'{radky}\n'
        '- jine: cokoli jiného\n\n'
        'Pole odpovědi:\n'
        '- kategorie: klíč kategorie\n'
        '- hodnota: odečtená hodnota jako číslo s desetinnou tečkou bez '
        'jednotky (např. "12345.678"); prázdný řetězec, pokud nejde '
        'spolehlivě přečíst nebo jde o kategorii jine\n'
        '- jistota: 0 až 1, jak jistě sedí kategorie i hodnota; nejistou '
        'číslici raději přiznej nižší jistotou než hádej\n'
        '- popis: jedna krátká věta česky, co je na fotce'
    )


def classify(image_bytes, media_type):
    """Pošle fotku Claudovi, vrátí dict kategorie/hodnota/jistota/popis."""
    if anthropic is None:
        raise AIError(_NO_LIB)
    key = get_key()
    if not key:
        raise AIError('Chybí klíč k AI.')
    client = anthropic.Anthropic(api_key=key, timeout=120)
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            # při odmítnutí bezpečnostním filtrem zkusí API jiný model
            betas=['server-side-fallback-2026-07-01'],
            extra_body={'fallbacks': 'default'},
            output_config={'effort': 'low',
                           'format': {'type': 'json_schema',
                                      'schema': _SCHEMA}},
            system=_system_prompt(),
            messages=[{'role': 'user', 'content': [
                {'type': 'image', 'source': {
                    'type': 'base64', 'media_type': media_type,
                    'data': base64.standard_b64encode(image_bytes).decode()}},
                {'type': 'text', 'text': 'Zařaď tuto fotku.'},
            ]}],
        )
    except anthropic.AuthenticationError:
        raise AIError('Klíč k AI je neplatný – zadej ho znovu v nastavení.')
    except anthropic.RateLimitError:
        raise AIError('AI je přetížená (limit požadavků), zkus to za chvíli.')
    except anthropic.BadRequestError as e:
        raise AIError(f'AI odmítla požadavek: {e.message}')
    except anthropic.APIStatusError as e:
        raise AIError(f'Chyba AI {e.status_code}: {e.message}')
    except anthropic.APIConnectionError as e:
        raise AIError(f'Nepodařilo se spojit s api.anthropic.com '
                      f'({e.__cause__!r}).')

    if resp.stop_reason == 'refusal':
        raise AIError('AI odmítla fotku analyzovat.')
    text = next((b.text for b in resp.content if b.type == 'text'), '')
    try:
        data = json.loads(text)
    except ValueError:
        raise AIError('AI vrátila neplatnou odpověď.')
    data['jistota'] = max(0.0, min(1.0, float(data.get('jistota') or 0)))
    data['hodnota'] = (data.get('hodnota') or '').replace(',', '.').strip()
    return data
