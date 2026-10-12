# F0B-1 — Resultados de validación (RESULTS)

**Fecha:** 2026-10-12 · **Rama:** `build/f0b1-native-foundation`
**Base:** `fix/f0a-ci-isolated @ bdb830d` · **Worktree:** `/home/eirom/Doremi-F0B1`
**Repo:** https://github.com/Eirom16/Doremi-Rust · **PR:** https://github.com/Eirom16/Doremi-Rust/pull/4 (base `fix/f0a-ci-isolated`, sin fusionar)

## 1. Higiene del repositorio

```bash
git ls-files "src/doremi/native_rs/target" | wc -l   # 405 ficheros versionados
git rm -r --cached src/doremi/native_rs/target       # solo del índice, en disco quedan
# .gitignore: +src/doremi/native_rs/target/, +native_rs*.so/.pyd in-tree, +*.whl
git check-ignore -q src/doremi/native_rs/target/release/foo.so && echo OK  # OK
cargo build --locked --offline --manifest-path src/doremi/native_rs/Cargo.toml
# Compiling doremi-native-rs v0.1.0 ... Finished dev profile in 24.49s  → compila tras la limpieza
```

Commit `2363120` — solo higiene (405 deletions + `.gitignore`).

## 2. Build local (venv fresco, Python 3.13.9 via uv)

```bash
uv venv --python 3.13 venv && uv pip install --python venv/bin/python maturin pytest PySide6
cd src/doremi/native_rs && /home/eirom/Doremi-F0B1/venv/bin/maturin build --release --locked --out dist
# Finished release profile [optimized] in 23.48s
# Built wheel for abi3 Python ≥ 3.12 to dist/doremi_native_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl
uv pip install --python venv/bin/python src/doremi/native_rs/dist/doremi_native_rs-*.whl
```

Contenido del wheel (inspección real): `native_rs/__init__.py` (shim),
`native_rs/native_rs.abi3.so`, `doremi_native_rs-0.1.0.dist-info/*`.

```bash
cd /tmp && env -u PYTHONPATH venv/bin/python -c "import native_rs; ..."
# .../venv/lib/python3.13/site-packages/native_rs/__init__.py  → location OK (site-packages)
# binary OK: hermano native_rs.abi3.so dentro del paquete instalado
# API OK: ['ColorVariants', 'adjust_hsv', 'average_center_zone', 'compute_color_variants',
#          'extract_n_colors', 'native_rs', 'process_qss_template', 'update_blobs']
```

Sin `BUILD_PROFILE` en esta base (verificado con grep en `src/`, puente y tests).

## 3. Tests locales (este árbol, wheel release instalado)

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src venv/bin/python -c \
  "import native_rs; assert 'site-packages' in native_rs.__file__; print('under test:', ...)"
# under test: .../site-packages/native_rs/__init__.py
QT_QPA_PLATFORM=offscreen PYTHONPATH=src venv/bin/python -m pytest tests/test_native_rs.py -q
# 17 passed in 0.36s
uv pip install --python venv/bin/python -e ".[dev]"
QT_QPA_PLATFORM=offscreen PYTHONPATH=src venv/bin/python -m pytest tests/ -q
# 376 passed in 17.23s  (cifra real de este árbol; 0 skipped; no se reutiliza la cifra histórica)
```

| Suite | Correctas | Fallidas |
|---|---|---:|
| `tests/test_native_rs.py` (local, release) | 17 | 0 |
| Suite completa `tests/` (local) | 376 | 0 |

## 4. CI — GitHub Actions (run de PR 38196258579, `success`)

Workflow `Native wheels (Rust)`, matriz 2×2, `maturin build --release --locked`:

| Job | Smoke | Parity tests | Wheel |
|---|---|---|---|
| ubuntu-latest · py3.12 | location + `native_rs.abi3.so` + API OK | **17 passed** (0.29 s) | `doremi-native-rs-ubuntu-latest-py3.12` |
| ubuntu-latest · py3.13 | location + `native_rs.abi3.so` + API OK | **17 passed** (0.12 s) | `doremi-native-rs-ubuntu-latest-py3.13` |
| windows-latest · py3.12 | location + `native_rs.pyd` + API OK | **17 passed** (0.27 s) | `doremi-native-rs-windows-latest-py3.12` |
| windows-latest · py3.13 | location + `native_rs.pyd` + API OK | **17 passed** (0.32 s) | `doremi-native-rs-windows-latest-py3.13` |

Sin diferencias funcionales entre Python 3.12 y 3.13 (mismos 17 tests en verde).

- Run: https://github.com/Eirom16/Doremi-Rust/actions/runs/38196258579
- Artifacts (retención 7 días, pestaña del run): `doremi-native-rs-{ubuntu,windows}-latest-py{3.12,3.13}`
- Colateral: `native.yml` (F0A) también corrió sobre el PR (run 38196258643, `success`).

## 5. Estado de Git y comprobaciones

- `git diff --check`: limpio. `git status`: solo los 5 archivos de la fase.
- `git log origin/fix/f0a-ci-isolated..HEAD` (tras docs): higiene + workflow + docs.
- Árbol original (`/home/eirom/Doremi-Rust`, rama `fix/f0a-ci-baseline`, cambios sin
  commitear del usuario) intacto: no se compiló ni modificó nada en él.

## 6. No verificado / fuera de alcance

- Instaladores finales, AppImage, Releases/tags: no construidos a propósito.
- Suite completa en CI Windows/Linux dentro del workflow: solo paridad nativa en CI;
  la completa se ejecutó en local (376 passed).
- Empaquetado con el wheel incluido: pendiente (ver REPORT §6).
