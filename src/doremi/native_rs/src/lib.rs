/// Doremi native Rust acceleration module.
///
/// This crate provides high-performance replacements for three
/// bottlenecks identified in Doremi's Python codebase:
///
/// * **QSS template processing** — single-pass placeholder substitution
///   (replaces 40× `str.replace()` chain).
/// * **Colour math** — lighter, darker, HSV adjustment, hex conversion.
/// * **Image colour extraction & blob animation** — replaces
///   `native/fast_image.c`.
///
/// # Requirement
///
/// This module is a mandatory binary dependency of Doremi.
/// Python code imports `doremi_native_rs` directly for performance.

pub mod color;
pub mod image;
pub mod qss;

use pyo3::prelude::*;

/// Doremi native Rust acceleration — QSS, colour, image helpers.
#[pymodule]
fn native_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // ── Colour variants class ────────────────────────────────────────
    m.add_class::<color::ColorVariants>()?;

    // ── QSS template engine ──────────────────────────────────────────
    m.add_function(wrap_pyfunction!(qss::process_qss_template, m)?)?;

    // ── Colour math ──────────────────────────────────────────────────
    m.add_function(wrap_pyfunction!(color::compute_color_variants, m)?)?;
    m.add_function(wrap_pyfunction!(color::adjust_hsv, m)?)?;

    // ── Image processing & blob animation ────────────────────────────
    m.add_function(wrap_pyfunction!(image::extract_n_colors, m)?)?;
    m.add_function(wrap_pyfunction!(image::average_center_zone, m)?)?;
    m.add_function(wrap_pyfunction!(image::update_blobs, m)?)?;

    Ok(())
}
