# F0B-1 — Build foundation del módulo nativo (REPORT)

**Fecha:** 2026-10-12 · **Rama:** `build/f0b1-native-foundation`
**Base:** `fix/f0a-ci-isolated @ bdb830d` (F0A-C verificado, PR #3 abierto sin fusionar)
**Alcance:** base reproducible de compilación del módulo Rust para Linux x86_64 y
Windows x64 en GitHub Actions. Sin instaladores, AppImages ni Releases.

## 1. Arquitectura del sistema de build

```text
src/doremi/native_rs/          crate PyO3 (cdylib) + pyproject maturin
  Cargo.toml                   pyo3 0.23, extension-module + abi3-py312
  pyproject.toml               module-name = "native_rs", requires-python >=3.12
  Cargo.lock                   respetado con --locked (se conserva versionado)
        │  maturin build --release --locked --out dist
        ▼
  dist/doremi_native_rs-0.1.0-cp312-abi3-<plat>.whl   (abi3: un wheel vale para 3.12+)
        │  pip install <wheel> en entorno limpio
        ▼
  site-packages/native_rs/
    __init__.py                shim maturin: from .native_rs import *
    native_rs.abi3.so  (.pyd en Windows)
        ▲
        │  doremi.native_rs (puente) lo importa top-level o junto al __init__.py
```

`.github/workflows/native-build.yml` — matriz 2×2 (ubuntu/windows × Python 3.12/3.13):

1. `setup-python` + toolchain Rust estable + `rust-cache`.
2. En Linux: las mismas system libs de F0A (QtGui las necesita al importar).
3. `maturin build --release --locked --out dist` (bash en Linux, `pwsh` con
   `Set-Location` en Windows; en Windows el wheel se resuelve con
   `Get-ChildItem ... | Select-Object -First 1`, sin asumir globs de bash).
4. Instalación del wheel + `pytest` + `PySide6` y smoke test **fuera del árbol de
   fuentes y sin `PYTHONPATH`**: el import debe resolver a `site-packages`, el
   binario debe ser un `native_rs*.so` / `native_rs*.pyd` hermano dentro del
   paquete instalado, y la API (6 funciones + `ColorVariants`) debe estar completa.
5. Suite de paridad `tests/test_native_rs.py` con `PYTHONPATH=src` (solo expone el
   puente `doremi`; se reafirma que `native_rs` sigue resolviendo a site-packages).
6. `upload-artifact` por plataforma/Python, retención 7 días (intermedios, no finales).

## 2. Problemas encontrados y causa raíz

- **P1 — El wheel es un paquete, no un módulo suelto (corregido antes del push).**
  La primera versión del smoke exigía `native_rs.__file__.endswith('.so')`, pero
  maturin genera `native_rs/__init__.py` + `native_rs.abi3.so` interno, luego
  `__file__` termina en `__init__.py`. Causa: suposición sobre el layout sin
  inspeccionar el wheel. Corrección: localizar el binario por glob
  (`native_rs*.so` / `native_rs*.pyd`) junto al paquete instalado. Detectado en
  validación local, no llegó a CI.
- **P2 — `python -m venv` roto con el Python 3.13 del equipo (entorno, no repo).**
  El `python3.13` local es un runtime gestionado por `uv` sin `ensurepip`; el venv
  se creó con `uv venv --python 3.13` y los paquetes con `uv pip --python`
  (los venvs de `uv` no traen binario `pip`). Sin impacto en CI.
- **P3 — `/tmp` lleno al 99 % (72 MB libres, repo 2,3 GB).** El worktree se creó en
  `/home/eirom/Doremi-F0B1` en lugar de `/tmp/opencode`. Sin impacto en el resultado.
- **Interfaz real de esta base:** no existe `BUILD_PROFILE` (propiedad de commits
  locales ajenos a la base remota). El smoke y los tests solo usan las 6 funciones
  + `ColorVariants`, verificados contra `lib.rs` y el test file de este árbol.

## 3. Archivos modificados (frente a la base)

| Commit | Archivo | Cambio |
|---|---|---|
| `2363120` | `src/doremi/native_rs/target/**` (405) | `git rm --cached`; siguen en disco local, fuera del índice |
| `2363120` | `.gitignore` | Excluye `src/doremi/native_rs/target/`, binarios in-tree y `*.whl` |
| (workflow) | `.github/workflows/native-build.yml` | Nuevo workflow matriz 2×2 (123 líneas) |
| (docs) | `docs/release/F0B1-REPORT.md` | Este informe |
| (docs) | `docs/release/F0B1-RESULTS.md` | Comandos y resultados |

No se tocó `build.yml`, `packaging/`, `main`, ni código fuente Rust/Python.
`git diff --check` limpio. Sin tests deshabilitados (la suite local cierra 376 passed,
0 skipped).

## 4. Versiones

| Herramienta | CI (ubuntu job) | Local (venv fresco) |
|---|---|---|
| Python | 3.12.15 / 3.13.16 (hostedtoolcache) | 3.13.9 (uv) |
| rustc | 1.99.0 | 1.99.0 |
| maturin | 1.15.0 | 1.15.0 |
| pytest | (pip, serie 9) | 9.1.1 |
| PySide6 | (pip) | 6.12.0 |

## 5. Riesgos

- El runner `ubuntu-latest` migrará a 26.04 (aviso presente en logs); los paquetes
  apt elegidos existen en ambas versiones.
- Los artifacts intermedios caducan en 7 días: son reproducibles reejecutando el
  workflow (`workflow_dispatch` disponible).
- `native.yml` (F0A) también se dispara con este PR porque el diff toca rutas
  `src/doremi/native_rs/**` (borrado de `target/`): pasó en verde, sin conflicto.
- Empaquetar (PyInstaller/.deb/RPM/Flatpak) sigue pendiente: ningún artefacto de
  esta fase es instalable por sí solo (el wheel es solo el módulo nativo).

## 6. Limitaciones pendientes (siguientes fases, no implementadas)

1. Incluir el wheel de la plataforma correcta en instaladores Linux/Windows.
2. Diagnóstico F0A de releases intacto: `doremi.spec`, `packaging/rpm/*.spec`,
   `RELEASE_NOTES.md`, `doremi-launcher.sh` siguen ausentes; `sed` de versión sobre
   `__version__` dinámico sigue siendo no-op; `postrm` con `pip uninstall` sistémico.
3. Decidir versiones Python soportadas por instalador (3.12 vs 3.13; 3.13 validado
   aquí como build+tests, sin diferencias observadas).
