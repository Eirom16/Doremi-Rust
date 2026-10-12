# F0B-2A — Resultados de validación (RESULTS)

**Fecha:** 2026-10-12 · **Rama:** `build/f0b2a-windows-portable`
**Base:** `build/f0b1-native-foundation @ 29cf4ea`
**PR:** https://github.com/Eirom16/Doremi-Rust/pull/5 (base `build/f0b1-native-foundation`, sin fusionar)

## 1. Validación local (worktree, venv fresco Python 3.13.9)

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src venv/bin/python -m pytest tests/ -q
# 376 passed (tras los 22 ficheros frozen; sin skips ni deshabilitados)
python -m doremi.main --smoke-test   # XDG aislados, QT offscreen
# EXIT:0  DOREMI_SMOKE_OK 9/9 (qt, vlc real libvlc.so.5, app_dirs, db, fonts,
#         rust, theme, qml_files, qml_shell) — ~/.local/share/doremi/doremi.db intacto
```

## 2. CI — run verde 38199021193 (`success`)

https://github.com/Eirom16/Doremi-Rust/actions/runs/38199021193
(Runs previos 38197407875/38197793545/38198610363 documentan los fallos
intermedios: layout `_internal`, `logging.config`, race del exe GUI.)

| Paso | Resultado |
|---|---|
| Wheel release Windows (`maturin build --release --locked`) | OK |
| Tests nativos en runner (`PYTHONPATH=src`) | **17 passed** (0.22 s) |
| Stamp `BUILD_VERSION=2.1.4` + `BUILD_ID=f0b2a.windows.aaa0c1b967b2` | OK |
| PyInstaller `doremi.spec` (onedir) | OK |
| Estructura: exe + 32 QML + qmldir + fuentes + locales + migraciones + iconos + `native_rs.pyd` (561 152 B) + `libvlc.dll`/`libvlccore.dll`/`plugins` | OK |
| Smoke exe congelado (`Start-Process -Wait`, XDG aislados, offscreen) | `DOREMI_SMOKE_OK` 9/9, exit 0 + `ok==true` en fichero |
| ZIP + MANIFEST + SHA256 | OK |
| Upload artifact (7 días) | OK |

Salida literal del smoke congelado:

```text
DOREMI_SMOKE_OK {"ok": true, "checks": {"qt_app": true, "vlc": true, "app_dirs": true,
"db_migrations": true, "fonts": true, "rust": true, "theme_bridge": true,
"qml_files": true, "qml_shell": true}, "version": "2.1.4", "frozen": true,
"meipass": "D:\\a\\Doremi-Rust\\Doremi-Rust\\dist\\Doremi\\_internal",
"build_id": "f0b2a.windows.aaa0c1b967b2", "cwd": "D:\\a\\_temp\\doremi-smoke"}
smoke ok: True | version: 2.1.4 | build: f0b2a.windows.aaa0c1b967b2
```

## 3. Tamaños (registrados, sin límite)

| Artefacto | Tamaño |
|---|---|
| `Doremi.exe` | 19,1 MB |
| Bundle `dist/Doremi` (786 MB en disco) | — |
| `Doremi-Windows-x64-Portable.zip` (3730 ficheros) | **328,5 MB** |

## 4. Artifact

`Doremi-Windows-x64-Portable` (run → Artifacts, expira en 7 días):
`Doremi-Windows-x64-Portable.zip` + `MANIFEST.txt` + `SHA256SUMS.txt`.
Uso en Windows limpio: descargar, extraer, ejecutar `Doremi\Doremi.exe`
(sin Python/VLC previos necesarios; sin admin). Para repetir el smoke:
`$env:QT_QPA_PLATFORM="offscreen"; .\Doremi\Doremi.exe --smoke-test`
y comprobar exit 0 + `DOREMI_SMOKE_OK`.

## 5. Git

Commits (todos en la rama, pushed): frozen-compat (23 ficheros) · spec+workflow ·
`_internal` fix · `logging.config`+traceback · `DOREMI_SMOKE_OUT`+`-Wait`.
`git diff --check` limpio. Árbol original del usuario intacto
(`fix/f0a-ci-baseline @ c00d772`, 100 líneas sin commitear preservadas).

## 6. No verificado / fuera de alcance

- Instalador Inno Setup, tags, Releases: no generados a propósito.
- Reproducción audible E2E en CI (VLC instancia OK; sin assert de audio).
- Avisos de redistribución VLC en el ZIP (riesgo documentado en REPORT §3).
- Empaquetado Linux: sin cambios.
