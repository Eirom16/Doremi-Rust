/// Image processing & blob animation helpers.
///
/// Replaces `native/fast_image.c` and the Python loops in
/// `ambient_background.py` and `config/themes.py`.

use pyo3::prelude::*;

/// Extract `n_colors` dominant colours from raw RGB pixel data.
///
/// Divides the image into `n_colors` vertical zones and averages each.
/// Same algorithm as `fast_image.c`'s `extract_n_colors`.
///
/// Args:
///     pixels: Flat array of RGB bytes (no padding, 3 bytes per pixel).
///     width, height: Image dimensions in pixels.
///     n_colors: Number of colours to extract (typically 3).
///
/// Returns:
///     List of `[r, g, b]` arrays, one per zone.
#[pyfunction]
pub fn extract_n_colors(
    pixels: Vec<u8>,
    width: u32,
    height: u32,
    n_colors: u32,
) -> Vec<[u8; 3]> {
    if pixels.is_empty() || width == 0 || height == 0 || n_colors == 0 {
        return Vec::new();
    }

    let zone_w = (width / n_colors).max(1);
    let mut colors = Vec::with_capacity(n_colors as usize);

    for zone in 0..n_colors {
        let x0 = (zone * zone_w) as usize;
        let x1 = if zone == n_colors - 1 {
            width as usize
        } else {
            (x0 + zone_w as usize).min(width as usize)
        };

        let mut r_sum: u64 = 0;
        let mut g_sum: u64 = 0;
        let mut b_sum: u64 = 0;
        let mut count: u64 = 0;

        for y in 0..height as usize {
            let row_start = y * width as usize * 3;
            for x in x0..x1 {
                let idx = row_start + x * 3;
                r_sum += pixels[idx] as u64;
                g_sum += pixels[idx + 1] as u64;
                b_sum += pixels[idx + 2] as u64;
                count += 1;
            }
        }

        if count > 0 {
            colors.push([
                (r_sum / count) as u8,
                (g_sum / count) as u8,
                (b_sum / count) as u8,
            ]);
        }
    }

    colors
}

/// Compute the average colour of the centre zone (25%–75%) of the image.
///
/// Same algorithm as `fast_image.c`'s `average_center_zone`.
///
/// Args:
///     pixels: Flat array of RGB bytes.
///     width, height: Image dimensions.
///
/// Returns:
///     `[r, g, b]` of the centre average, or `[128, 128, 128]` on error.
#[pyfunction]
pub fn average_center_zone(
    pixels: Vec<u8>,
    width: u32,
    height: u32,
) -> [u8; 3] {
    if pixels.is_empty() || width == 0 || height == 0 {
        return [128, 128, 128];
    }

    let y0 = (height / 4) as usize;
    let y1 = (height * 3 / 4) as usize;
    let x0 = (width / 4) as usize;
    let x1 = (width * 3 / 4) as usize;

    let mut r_sum: u64 = 0;
    let mut g_sum: u64 = 0;
    let mut b_sum: u64 = 0;
    let mut count: u64 = 0;

    for y in y0..y1 {
        let row_start = y * width as usize * 3;
        for x in x0..x1 {
            let idx = row_start + x * 3;
            r_sum += pixels[idx] as u64;
            g_sum += pixels[idx + 1] as u64;
            b_sum += pixels[idx + 2] as u64;
            count += 1;
        }
    }

    if count > 0 {
        [
            (r_sum / count) as u8,
            (g_sum / count) as u8,
            (b_sum / count) as u8,
        ]
    } else {
        [128, 128, 128]
    }
}

/// Update blob positions for the ambient background animation.
///
/// Same algorithm as `fast_image.c`'s `update_blobs` and the Python
/// loop in `ambient_background.py`.
///
/// Args:
///     xs, ys: Current blob positions (modified in place on the Rust side,
///             but returned as new lists for Python's immutable floats).
///     target_xs, target_ys: Target positions.
///     dt: Delta-time step (default 0.005).
///     threshold_sq: Squared distance threshold for "reached" detection.
///
/// Returns:
///     Tuple of (new_xs, new_ys, reached_count).
#[pyfunction]
pub fn update_blobs(
    xs: Vec<f64>,
    ys: Vec<f64>,
    target_xs: Vec<f64>,
    target_ys: Vec<f64>,
    dt: f64,
    threshold_sq: f64,
) -> (Vec<f64>, Vec<f64>, u32) {
    let n = xs.len().min(ys.len()).min(target_xs.len()).min(target_ys.len());
    let mut new_xs = Vec::with_capacity(n);
    let mut new_ys = Vec::with_capacity(n);
    let mut reached = 0u32;

    for i in 0..n {
        let dx = target_xs[i] - xs[i];
        let dy = target_ys[i] - ys[i];
        new_xs.push(xs[i] + dx * dt);
        new_ys.push(ys[i] + dy * dt);
        if dx * dx + dy * dy < threshold_sq {
            reached += 1;
        }
    }

    (new_xs, new_ys, reached)
}
