# F0A — Resultados de validación (RESULTS)

**Fecha:** 2026-10-11 · **Rama:** `fix/f0a-ci-baseline` · **HEAD base:** `ea75ca5`
**SO local:** CachyOS (Arch) rolling · **Repo:** https://github.com/Eirom16/Doremi-Rust

> **Procedencia de la evidencia:** las validaciones locales (§1.2–§1.5) se ejecutaron
> sobre el `main` local en `ea75ca5`, que incluía 7 commits por delante de
> `origin/main` más cambios sin commitear del usuario. El contenido funcional de los
> 4 archivos de este PR es idéntico al validado entonces; la conformidad sobre la
> base remota actual la aporta el CI del propio PR (§3).

## 1. Comandos ejecutados y resultados reales

### 1.1 Inspección (solo lectura, sin modificar archivos)

```bash
git branch --show-current          # main (luego fix/f0a-ci-baseline)
git rev-parse HEAD                 # ea75ca5f9fe257f0cabd186e77db7c2542aab304
git status --porcelain=v1 -b       # ## main...origin/main [ahead 7] + ~85 ficheros M y ~14 untracked (usuario, preservados)
git log origin/main..HEAD --oneline  # 7 commits locales (ea75ca5 … 11f15a8)
git ls-files | grep -c "native_rs/target"  # 405 ficheros de build versionados
git check-ignore -v docs/release/F0A-REPORT.md  # .gitignore:66:*.md (confirmado: había que exceptuar)
```

### 1.2 Construcción del módulo Rust (maturin)

```bash
cd src/doremi/native_rs && /home/eirom/Doremi-Rust/.venv/bin/maturin develop --locked
```

Resultado: **OK**.

```text
🐍 Found CPython 3.13 at /home/eirom/Doremi-Rust/.venv/bin/python
🔗 Found pyo3 bindings with abi3-py3.12 support
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.19s
📦 Built wheel for abi3 Python ≥ 3.12 to /tmp/.tmp5CxYPp/doremi_native_rs-0.1.0-cp312-abi3-linux_x86_64.whl
🛠 Installed doremi-native-rs-0.1.0
```

### 1.3 Verificación de importación del módulo nativo

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -c \
  "from doremi.native_rs import BUILD_PROFILE; print('BUILD_PROFILE =', BUILD_PROFILE)"
# BUILD_PROFILE = debug

QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -c \
  "from PySide6.QtGui import QColor; print('QtGui OK, QColor:', QColor('#A78BFA').name())"
# QtGui OK, QColor: #a78bfa
```

Resultado: **OK**. El puente `doremi.native_rs` carga la extensión y `PySide6.QtGui`
importa correctamente en este equipo (mesa provee `/usr/lib/libEGL.so.1`).

### 1.4 Pruebas `tests/test_native_rs.py`

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/test_native_rs.py -v
```

Resultado: **22 passed in 0.52s** (incluye `TestComputeColorVariants::test_matches_qcolor`,
el test que falla en CI por `libEGL.so.1`). Cero fallos, cero skips, cero xfails.
En el momento del fallo de CI el fichero tenía 17 tests (16 passed + 1 failed);
los 5 adicionales provienen del trabajo posterior del usuario.

### 1.5 Suite completa con Qt en modo offscreen

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/ -q
```

Resultado: **523 passed in 19.29s**. Cero fallos.

### 1.6 Compatibilidad Python 3.12

- `pyproject.toml` exige `>=3.12,<3.14`; el venv local es **3.13.9** (dentro de rango).
- El wheel construido es `cp312-abi3` (`abi3-py3.12` según PyO3), compatible con 3.12+.
- El CI (`native.yml`) fija `PYTHON_VERSION: "3.12"`.
- **Verificado vía CI tras el fix** (run 38194743416): 17/17 passed en Python 3.12.
  No se verificó con intérprete 3.12 local (no instalado en este equipo).

### 1.7 Pruebas correctas / fallidas

| Suite | Correctas | Fallidas | Notas |
|---|---|---:|---|
| `tests/test_native_rs.py` | 22 | 0 | Incluye paridad QColor vs QtGui |
| Suite completa `tests/` | 523 | 0 | `QT_QPA_PLATFORM=offscreen` |

No se deshabilitó ni ignoró ninguna prueba.

## 2. Versiones de herramientas

| Herramienta | Versión | Notas |
|---|---|---|
| Python (venv `.venv`) | 3.13.9 | intérprete de validación |
| Python (sistema) | 3.14.8 | **fuera del rango soportado** (`<3.14`) |
| Python 3.12 | no instalado | pendiente vía CI |
| rustc / cargo | 1.99.0 | edición 2021 |
| maturin | 1.15.0 | binario en `.venv/bin` |
| pytest | 9.1.1 | + pytest-asyncio 1.4.0 |
| PySide6 | 6.11.2 | QtGui importa OK en local |
| pip en venv | **ausente** (`No module named pip`) | ver riesgos en REPORT |

## 3. Commit y CI

- **Commit F0A:** (ver `git log fix/f0a-ci-baseline`) — incluye únicamente
  `.github/workflows/native.yml`, `.gitignore`, `docs/release/F0A-REPORT.md`,
  `docs/release/F0A-RESULTS.md`.
- **Run fallido analizado:** https://github.com/Eirom16/Doremi-Rust/actions/runs/36257325737
  (16 passed + 1 failed por `libEGL.so.1`, según log referido en la tarea).
- **Run verificado vía web:** job `Build native_rs + parity tests`, commit `e8c217a`,
  estado `Failure`, `exit code 1`, 44 s (sin acceso al log detallado sin sesión).
- **Run del fix (PR #2):** https://github.com/Eirom16/Doremi-Rust/actions/runs/38194743416 —
  `conclusion: success`. `Run parity tests`: **17 passed in 0.18s en Python 3.12**,
  incluido `TestComputeColorVariants::test_matches_qcolor` (el que fallaba por
  `libEGL.so.1`). Esto además confirma la compatibilidad con Python 3.12, que no
  pudo verificarse con intérprete local. PR: https://github.com/Eirom16/Doremi-Rust/pull/2
  (abierto, sin fusionar).

## 4. Bloqueos / no verificado

1. ~~Ejecución del workflow corregido en GitHub Actions (requiere push/PR).~~
   Verificado: run 38194743416 en verde (17 passed, Python 3.12).
2. ~~Conformidad en intérprete Python 3.12 local (sin intérprete disponible).~~
   Cubierto por el run de CI en 3.12.
3. Sistema de releases: solo diagnosticado (F0B), sin cambios aplicados a propósito.
