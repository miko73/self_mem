# -*- coding: utf-8 -*-
"""Jednorázové vygenerování PWA ikon (modrý blok s řádky poznámky)."""
from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parent / 'static'


def make_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 512  # měřítko vůči základnímu návrhu 512 px

    # pozadí – zaoblený modrý čtverec přes celou plochu (maskable-safe)
    d.rounded_rectangle([0, 0, size - 1, size - 1],
                        radius=int(96 * s), fill=(37, 99, 235, 255))
    # bílý "list papíru"
    d.rounded_rectangle([int(128 * s), int(96 * s), int(384 * s), int(416 * s)],
                        radius=int(24 * s), fill=(255, 255, 255, 255))
    # řádky textu
    for y in (168, 232, 296):
        d.rounded_rectangle(
            [int(164 * s), int(y * s), int(348 * s), int((y + 20) * s)],
            radius=int(10 * s), fill=(147, 176, 240, 255))
    # poslední kratší řádek
    d.rounded_rectangle(
        [int(164 * s), int(360 * s), int(280 * s), int(380 * s)],
        radius=int(10 * s), fill=(147, 176, 240, 255))
    return img


for size in (192, 512):
    make_icon(size).save(STATIC / f'icon-{size}.png')
    print(f'icon-{size}.png OK')
