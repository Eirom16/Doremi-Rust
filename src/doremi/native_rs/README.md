# native\_rs — Doremi Rust acceleration

## Overview

Rust/PyO3 native module replacing Doremi's C module (`fast_image.c`) and
optimising three Python bottlenecks. **The module is required** — there are no
pure-Python fallbacks anymore; if it is not built, importing `doremi.native_rs`
fails at startup and `tests/test_native_rs.py` fails.

## Build

```bash
cd src/doremi/native_rs
maturin develop --release
```

Requires:
- Rust toolchain (edition 2021)
- Python 3.12+ (ABI‑3‑forward‑compatible, tested on 3.14)
- `maturin` (`pip install maturin`)

Builds to: `native_rs.abi3.so` in site‑packages.
The bridge `__init__.py` re‑exports from the installed top‑level `native_rs`
package.

## API

### `process_qss_template(template, vars_map) → str`

Single‑pass QSS variable substitution via Aho‑Corasick (fastest for 40+
simultaneous replacements).

- **template** — raw QSS string with placeholder tokens (`#A78BFA`, `167,139,250`, …)
- **vars_map** — dict of every placeholder → replacement value
- **Returns** — fully substituted QSS string

### `compute_color_variants(accent_hex, active_mode) → ColorVariants`

Pre‑computes lighter/darker colour variants for a given accent.

- **accent_hex** — e.g. `"#A78BFA"`
- **active_mode** — `"dark"` or `"light"` (reserved for future text‑on‑accent logic)
- **Returns** — `ColorVariants` with `.bright_hex`, `.dark_hex`, `.r`, `.g`, `.b`,
  `.dark_r`, `.dark_g`, `.dark_b`

### `adjust_hsv(r, g, b, min_saturation, min_value) → (int, int, int)`

Clamps HSV saturation/value to minimum thresholds.

### `extract_n_colors(pixels, width, height, n_colors) → list[list[int,int,int]]`

Divides the image into `n_colors` vertical zones and averages each zone.

- **pixels** — flat `list[int]` of RGB bytes (3 per pixel, row‑major)

### `average_center_zone(pixels, width, height) → [int, int, int]`

Average colour of the centre 25%–75% zone.

### `update_blobs(xs, ys, target_xs, target_ys, dt, threshold_sq) → (list[float], list[float], int)`

Single‑step blob animation for the ambient background.

- **dt** — delta‑time step (default 0.005)
- **threshold_sq** — squared‑distance threshold for "reached" detection
- **Returns** — `(new_xs, new_ys, reached_count)`

## Architecture

```
src/
├── lib.rs          — PyO3 module registration
├── qss.rs          — Aho‑Corasick QSS template engine
├── color.rs        — Colour math (lighter, darker, HSV, hex)
└── image.rs        — Image processing + blob animation
```

## Fidelity note — `compute_color_variants`

`lighter()`/`darker()` replicate Qt's `QColor::lighter/darker` **in HSV space**
(qcolor.cpp): `v *= factor/100`, and on overflow the excess is subtracted from
saturation (the "towards white" pastel shift). Parity vs `QColor` is enforced
by `tests/test_native_rs.py` (±2 quantization slack allowed — Qt works in
16-bit ints).

## Tests & CI

- `tests/test_native_rs.py` — verifies the native functions against inline
  reference implementations and `QColor` (fails if the module is not built).
- `.github/workflows/native.yml` — builds the wheel with maturin and runs the
  tests on every push/PR touching `native_rs`.
