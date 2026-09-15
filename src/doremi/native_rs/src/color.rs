/// Color math operations — lighter, darker, HSV adjustment, hex conversion.
///
/// Replaces the Python code in theme_manager.py that used QColor.lighter()
/// and QColor.darker(), as well as the HSV adjustment in config/themes.py.

use pyo3::prelude::*;

/// Holds the pre-computed color variants for a given accent + theme combo.
///
/// Returned by [`compute_color_variants`] and consumed by the QSS template
/// engine to avoid re-computing the same values in Python.
#[pyclass(get_all)]
#[derive(Clone)]
pub struct ColorVariants {
    pub bright_hex: String,
    pub dark_hex: String,
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub dark_r: u8,
    pub dark_g: u8,
    pub dark_b: u8,
}

#[pymethods]
impl ColorVariants {
    fn __repr__(&self) -> String {
        format!(
            "ColorVariants(bright={}, dark={}, rgb=({},{},{}), dark_rgb=({},{},{}))",
            self.bright_hex, self.dark_hex, self.r, self.g, self.b, self.dark_r, self.dark_g, self.dark_b,
        )
    }
}

/// Parse a hex color string (e.g. `#A78BFA`) to its RGB components.
fn hex_to_rgb(hex: &str) -> Option<(u8, u8, u8)> {
    let hex = hex.trim_start_matches('#');
    if hex.len() != 6 {
        return None;
    }
    let r = u8::from_str_radix(&hex[0..2], 16).ok()?;
    let g = u8::from_str_radix(&hex[2..4], 16).ok()?;
    let b = u8::from_str_radix(&hex[4..6], 16).ok()?;
    Some((r, g, b))
}

/// Lighten a colour by a percentage factor (100 = unchanged).
///
/// Faithful mirror of Qt's `QColor::lighter(factor)` (qcolor.cpp): the colour
/// is converted to HSV, `v` is scaled by `factor/100`, and if the scaled value
/// overflows 1.0 the excess is subtracted from the saturation — producing the
/// characteristic "towards white" pastel shift rather than an RGB multiply.
#[inline]
fn lighter(r: u8, g: u8, b: u8, factor: u8) -> (u8, u8, u8) {
    let (h, s, v) = rgb_to_hsv(
        f64::from(r) / 255.0,
        f64::from(g) / 255.0,
        f64::from(b) / 255.0,
    );
    let mut v_new = v * (f64::from(factor) / 100.0);
    let mut s_new = s;
    if v_new > 1.0 {
        s_new = (s_new - (v_new - 1.0)).max(0.0);
        v_new = 1.0;
    }
    let (ro, go, bo) = hsv_to_rgb(h, s_new, v_new);
    (
        (ro * 255.0 + 0.5) as u8,
        (go * 255.0 + 0.5) as u8,
        (bo * 255.0 + 0.5) as u8,
    )
}

/// Darken a colour by a percentage factor (100 = unchanged).
///
/// Mirror of `QColor.darker(factor)`: HSV conversion, `v * 100 / factor`,
/// saturation untouched.
#[inline]
fn darker(r: u8, g: u8, b: u8, factor: u8) -> (u8, u8, u8) {
    let (h, s, v) = rgb_to_hsv(
        f64::from(r) / 255.0,
        f64::from(g) / 255.0,
        f64::from(b) / 255.0,
    );
    let v_new = (v * 100.0 / f64::from(factor)).min(1.0);
    let (ro, go, bo) = hsv_to_rgb(h, s, v_new);
    (
        (ro * 255.0 + 0.5) as u8,
        (go * 255.0 + 0.5) as u8,
        (bo * 255.0 + 0.5) as u8,
    )
}

/// Convert RGB → HSV (all components in 0..1 range).
fn rgb_to_hsv(r: f64, g: f64, b: f64) -> (f64, f64, f64) {
    let max = r.max(g).max(b);
    let min = r.min(g).min(b);
    let delta = max - min;

    let v = max;
    let s = if max > 0.0 { delta / max } else { 0.0 };

    if delta < 1e-9 {
        return (0.0, s, v);
    }

    let h = if max == r {
        60.0 * (((g - b) / delta) % 6.0)
    } else if max == g {
        60.0 * (((b - r) / delta) + 2.0)
    } else {
        60.0 * (((r - g) / delta) + 4.0)
    };
    let h = if h < 0.0 { h + 360.0 } else { h };

    (h / 360.0, s, v)
}

/// Convert HSV → RGB (all components in 0..1 range).
fn hsv_to_rgb(h: f64, s: f64, v: f64) -> (f64, f64, f64) {
    if s < 1e-9 {
        return (v, v, v);
    }
    let hi = (h * 6.0).floor() as i32 % 6;
    let f = h * 6.0 - (h * 6.0).floor();
    let p = v * (1.0 - s);
    let q = v * (1.0 - f * s);
    let t = v * (1.0 - (1.0 - f) * s);

    match hi {
        0 => (v, t, p),
        1 => (q, v, p),
        2 => (p, v, t),
        3 => (p, q, v),
        4 => (t, p, v),
        _ => (v, p, q),
    }
}

/// Pre-compute all colour variants needed for QSS template substitution.
///
/// This replaces the Python code that called `QColor.lighter(125)` and
/// `QColor.darker(120)` individually.
///
/// Args:
///     accent_hex: Hex colour string like `"#A78BFA"`.
///     active_mode: Either `"dark"` or `"light"` (used for `text_on_accent`).
///
/// Returns:
///     A [`ColorVariants`] struct with all pre-computed values.
#[pyfunction]
pub fn compute_color_variants(accent_hex: &str, _active_mode: &str) -> ColorVariants {
    let (r, g, b) = hex_to_rgb(accent_hex).unwrap_or((167, 139, 250));

    let (br, bg, bb) = lighter(r, g, b, 125);
    let (dr, dg, db) = darker(r, g, b, 120);

    ColorVariants {
        bright_hex: format!("#{:02X}{:02X}{:02X}", br, bg, bb),
        dark_hex: format!("#{:02X}{:02X}{:02X}", dr, dg, db),
        r,
        g,
        b,
        dark_r: dr,
        dark_g: dg,
        dark_b: db,
    }
}

/// Adjust the saturation and value (brightness) of an RGB colour.
///
/// Replaces the Python + C `adjust_hsv` logic in `config/themes.py` and
/// `native/fast_image.c`.
///
/// Args:
///     r, g, b: Input RGB components (0–255).
///     min_saturation: Minimum saturation clamp (0–1).
///     min_value: Minimum value/brightness clamp (0–1).
///
/// Returns:
///     Adjusted (r, g, b) components as a tuple.
#[pyfunction]
pub fn adjust_hsv(r: u8, g: u8, b: u8, min_saturation: f64, min_value: f64) -> (u8, u8, u8) {
    let (h, mut s, mut v) = rgb_to_hsv(
        f64::from(r) / 255.0,
        f64::from(g) / 255.0,
        f64::from(b) / 255.0,
    );

    if s < min_saturation {
        s = min_saturation;
    }
    if v < min_value {
        v = min_value;
    }

    let (ro, go, bo) = hsv_to_rgb(h, s, v);
    (
        (ro * 255.0 + 0.5) as u8,
        (go * 255.0 + 0.5) as u8,
        (bo * 255.0 + 0.5) as u8,
    )
}
