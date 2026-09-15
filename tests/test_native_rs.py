"""Tests del módulo nativo Rust (`doremi.native_rs`), dependencia OBLIGATORIA.

Las funciones nativas se verifican contra implementaciones de referencia
independientes (inline en este archivo) y contra QColor. Si el módulo no está
compilado (`maturin develop --release`), estos tests FALLAN — no hay skip.
"""
from __future__ import annotations

import pytest

from doremi.native_rs import (
    adjust_hsv,
    average_center_zone,
    compute_color_variants,
    extract_n_colors,
    process_qss_template,
    update_blobs,
)

# The real placeholder set used by theme_manager._apply_actual()
QSS_VARS = {
    "#A78BFA": "#FF5733",
    "#a78bfa": "#ff5733",
    "#BBA4FC": "#FF8866",
    "#bba4fc": "#ff8866",
    "#8B5CF6": "#CC4526",
    "#8b5cf6": "#cc4526",
    "167,139,250": "255,87,51",
    "167, 139, 250": "255, 87, 51",
    "139,92,246": "204,69,38",
    "139, 92, 246": "204, 69, 38",
}


def _python_qss_chain(template: str, vars_map: dict[str, str]) -> str:
    """Reference: the Python fallback chain of str.replace()."""
    out = template
    for key, value in vars_map.items():
        out = out.replace(key, value)
    return out


def _py_extract_n_colors(pixels: list[int], width: int, height: int, n_colors: int) -> list[list[int]]:
    """Reference: zone-average algorithm, mirror of image.rs."""
    zone_w = max(width // n_colors, 1)
    colors = []
    for zone in range(n_colors):
        x0 = zone * zone_w
        x1 = width if zone == n_colors - 1 else min(x0 + zone_w, width)
        rs = gs = bs = count = 0
        for y in range(height):
            row = y * width * 3
            for x in range(x0, x1):
                idx = row + x * 3
                rs += pixels[idx]
                gs += pixels[idx + 1]
                bs += pixels[idx + 2]
                count += 1
        if count:
            colors.append([rs // count, gs // count, bs // count])
    return colors


class TestComputeColorVariants:
    def test_matches_qcolor(self):
        pytest.importorskip("PySide6.QtGui")
        from PySide6.QtGui import QColor

        def hex_max_channel_delta(hex_a: str, rgb_qcolor) -> int:
            r = int(hex_a[1:3], 16)
            g = int(hex_a[3:5], 16)
            b = int(hex_a[5:7], 16)
            return max(
                abs(r - rgb_qcolor.red()),
                abs(g - rgb_qcolor.green()),
                abs(b - rgb_qcolor.blue()),
            )

        # Qt computes lighter/darker in 16-bit HSV space; the Rust port works
        # in f64 — allow the ±2 quantization slack, never a visible divergence.
        for accent in ("#A78BFA", "#FF5733", "#0066CC", "#000000", "#FFFFFF"):
            cv = compute_color_variants(accent, "dark")
            c = QColor(accent)
            bright = c.lighter(125)
            dark = c.darker(120)
            assert hex_max_channel_delta(cv.bright_hex, bright) <= 2, accent
            assert hex_max_channel_delta(cv.dark_hex, dark) <= 2, accent
            assert (cv.r, cv.g, cv.b) == (c.red(), c.green(), c.blue())
            assert (
                abs(cv.dark_r - dark.red()) <= 2
                and abs(cv.dark_g - dark.green()) <= 2
                and abs(cv.dark_b - dark.blue()) <= 2
            )

    def test_invalid_hex_falls_back_to_default_accent(self):
        cv = compute_color_variants("not-a-color", "dark")
        assert (cv.r, cv.g, cv.b) == (167, 139, 250)  # #A78BFA default


class TestProcessQssTemplate:
    TEMPLATE = (
        "QWidget { background: #0A0A14; color: #A78BFA; } "
        "#x { border: 1px solid rgba(167,139,250,0.12); } "
        ".y:hover { color: #bba4fc; border-color: rgba(139, 92, 246, 0.5); } "
        "QSlider::sub-page { background: #8B5CF6; } .z { color: #a78bfa; }"
    )

    def test_parity_with_replace_chain(self):
        assert process_qss_template(self.TEMPLATE, QSS_VARS) == _python_qss_chain(
            self.TEMPLATE, QSS_VARS
        )

    def test_full_qss_parity(self):
        from doremi.ui.stylesheet import DOREMI_QSS

        assert process_qss_template(DOREMI_QSS, QSS_VARS) == _python_qss_chain(
            DOREMI_QSS, QSS_VARS
        )

    def test_empty_map_is_identity(self):
        assert process_qss_template(self.TEMPLATE, {}) == self.TEMPLATE

    def test_no_placeholders(self):
        assert process_qss_template("QWidget { color: red; }", QSS_VARS) == "QWidget { color: red; }"


class TestAdjustHsv:
    def test_clamps_low_saturation_and_value(self):
        r, g, b = adjust_hsv(40, 40, 42, min_saturation=0.5, min_value=0.6)
        import colorsys

        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        assert s >= 0.45  # rounding tolerance
        assert v >= 0.59

    def test_already_vivid_color_is_stable(self):
        r, g, b = adjust_hsv(200, 50, 120, min_saturation=0.3, min_value=0.3)
        assert abs(r - 200) <= 1
        assert abs(g - 50) <= 1
        assert abs(b - 120) <= 1

    def test_grayscale_parity_with_python_reference(self):
        # A grayscale input has no hue; forcing min saturation pins it to
        # hue 0 (reddish) — the colorsys reference acts as the contract.
        import colorsys

        r, g, b = adjust_hsv(30, 30, 30, min_saturation=0.5, min_value=0.8)
        h, s, v = colorsys.rgb_to_hsv(30 / 255, 30 / 255, 30 / 255)
        s = max(s, 0.5)
        v = max(v, 0.8)
        er, eg, eb = (round(x * 255) for x in colorsys.hsv_to_rgb(h, s, v))
        assert abs(r - er) <= 1
        assert abs(g - eg) <= 1
        assert abs(b - eb) <= 1


class TestExtractNColors:
    def test_pure_color_zones(self):
        width, height = 9, 4
        zones = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        pixels = []
        for _y in range(height):
            for x in range(width):
                pixels.extend(zones[x // 3])
        result = extract_n_colors(pixels, width, height, 3)
        assert [list(c) for c in result] == [[255, 0, 0], [0, 255, 0], [0, 0, 255]]

    def test_parity_with_python_reference(self):
        width, height, n = 17, 11, 4
        pixels = [(i * 7) % 256 for i in range(width * height * 3)]
        result = extract_n_colors(pixels, width, height, n)
        assert [list(c) for c in result] == _py_extract_n_colors(pixels, width, height, n)

    def test_empty_input(self):
        assert extract_n_colors([], 0, 0, 3) == []


class TestAverageCenterZone:
    def test_white_center_in_black_frame(self):
        width = height = 4
        pixels = []
        for y in range(height):
            for x in range(width):
                inside = 1 <= x < 3 and 1 <= y < 3
                pixels.extend((255, 255, 255) if inside else (0, 0, 0))
        assert list(average_center_zone(pixels, width, height)) == [255, 255, 255]

    def test_empty_returns_neutral_gray(self):
        assert list(average_center_zone([], 0, 0)) == [128, 128, 128]


class TestUpdateBlobs:
    def test_moves_towards_target(self):
        xs, ys, reached = update_blobs([0.0], [0.0], [1.0], [1.0], 0.5, 0.01)
        assert xs == [0.5]
        assert ys == [0.5]
        assert reached == 0

    def test_reached_threshold(self):
        xs, ys, reached = update_blobs([0.99], [0.99], [1.0], [1.0], 0.005, 0.01)
        assert reached == 1

    def test_mismatched_lengths_use_shortest(self):
        xs, ys, reached = update_blobs([0.0, 0.0], [0.0], [1.0], [1.0], 0.5, 0.01)
        assert len(xs) == len(ys) == 1
