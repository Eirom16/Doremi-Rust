#!/usr/bin/env python3
"""Genera src/doremi/ui/qml/Theme.qml desde ui/design/tokens.py.

Uso:
    python tools/generate_theme_qml.py            # regenera el archivo
    python tools/generate_theme_qml.py --check    # exit 1 si está desincronizado (CI)

Solo contiene tokens ESTÁTICOS (spacing, radius, typeScale, elevation).
Los colores son dinámicos en runtime (acento del usuario) y llegan a QML
vía ThemeBridge (ui/theme_bridge.py), no por este archivo.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

OUT_PATH = ROOT / "src" / "doremi" / "ui" / "qml" / "Doremi" / "Theme.qml"

HEADER = """// GENERATED — DO NOT EDIT.
// Fuente: src/doremi/ui/design/tokens.py
// Regenerar:  python tools/generate_theme_qml.py
// Verificar:  python tools/generate_theme_qml.py --check  (CI)
"""

TEMPLATE = """{header}pragma Singleton
import QtQuick

QtObject {{
    // ── Spacing (px) — tokens.Spacing ──────────────────────────
    readonly property int spacingXxs: {spacing_xxs}
    readonly property int spacingXs:  {spacing_xs}
    readonly property int spacingSm:  {spacing_sm}
    readonly property int spacingMd:  {spacing_md}
    readonly property int spacingLg:  {spacing_lg}
    readonly property int spacingXl:  {spacing_xl}
    readonly property int spacingXxl: {spacing_xxl}
    readonly property int spacingSection: {spacing_section}

    // ── Radius (px) — tokens.Radius ────────────────────────────
    readonly property int radiusNone: {radius_none}
    readonly property int radiusSm:   {radius_sm}
    readonly property int radiusMd:   {radius_md}
    readonly property int radiusLg:   {radius_lg}
    readonly property int radiusXl:   {radius_xl}
    readonly property int radiusPill: {radius_pill}

    // ── Type scale (px) — tokens.TypeScale ─────────────────────
    readonly property int typeDisplay: {type_display}
    readonly property int typeHeading: {type_heading}
    readonly property int typeTitle:   {type_title}
    readonly property int typeBody:    {type_body}
    readonly property int typeLabel:   {type_label}
    readonly property int typeCaption: {type_caption}
    readonly property int typeMono:    {type_mono}

    // ── Elevation — tokens.Elevation (la única sombra: artwork) ─
    readonly property int elevationArtworkBlur: {elev_blur}
    readonly property int elevationArtworkOffsetX: {elev_ox}
    readonly property int elevationArtworkOffsetY: {elev_oy}
    readonly property real elevationArtworkAlpha: {elev_alpha}

    readonly property string fontFamily: "Inter"
    readonly property string fontMono: "JetBrains Mono"
}}
"""


def render(tokens_module) -> str:
    s, r, ts, e = (
        tokens_module.Spacing,
        tokens_module.Radius,
        tokens_module.TypeScale,
        tokens_module.Elevation,
    )
    return TEMPLATE.format(
        header=HEADER,
        spacing_xxs=s.XXS, spacing_xs=s.XS, spacing_sm=s.SM, spacing_md=s.MD,
        spacing_lg=s.LG, spacing_xl=s.XL, spacing_xxl=s.XXL, spacing_section=s.SECTION,
        radius_none=r.NONE, radius_sm=r.SM, radius_md=r.MD,
        radius_lg=r.LG, radius_xl=r.XL, radius_pill=r.PILL,
        type_display=ts.DISPLAY, type_heading=ts.HEADING, type_title=ts.TITLE,
        type_body=ts.BODY, type_label=ts.LABEL, type_caption=ts.CAPTION, type_mono=ts.MONO,
        elev_blur=e.ARTWORK_BLUR, elev_ox=e.ARTWORK_OFFSET_X,
        elev_oy=e.ARTWORK_OFFSET_Y, elev_alpha=round(e.ARTWORK_ALPHA / 255, 4),
    )


def main() -> int:
    from doremi.ui.design import tokens

    content = render(tokens)
    if "--check" in sys.argv:
        if not OUT_PATH.exists() or OUT_PATH.read_text() != content:
            print(f"DESINCRONIZADO: {OUT_PATH} — corre tools/generate_theme_qml.py")
            return 1
        print("Theme.qml en sync con tokens.py")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(content)
    print(f"Generado {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
