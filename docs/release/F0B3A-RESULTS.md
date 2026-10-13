# F0B-3A — Resultados de validación (RESULTS)

**Fecha:** 2026-10-12 · **Rama:** `build/f0b3a-linux-portable`
**Base:** `build/f0b2b-windows-installer @ b2162d0`
**PR:** https://github.com/Eirom16/Doremi-Rust/pull/7 (base
`build/f0b2b-windows-installer`; PR #6 sigue abierto)

## 1. Validación local (worktree, venv fresco Python 3.12.14, glibc 2.44)

Prueba de concepto del spec/launcher/smoke — NO es el artifact portable
(el baseline oficial es Ubuntu 22.04 / glibc 2.35 vía CI, §2).

```bash
(cd src/doremi/native_rs && maturin build --release --locked --out dist)
# wheel: doremi_native_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl
pip install src/doremi/native_rs/dist/*.whl
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -c "import native_rs; assert 'site-packages' in native_rs.__file__"  # OK
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/ -q
# 385 passed (376 preexistentes + 9 tests/test_linux_packaging.py), 0 skips forzados
pyinstaller doremi-linux.spec   # PyInstaller 6.22.3, OK (warnings ldd menores por permisos, ver log)
```

Estructura verificada: `dist/Doremi/Doremi` (ELF x86-64, 19 497 424 B),
`doremi.sh`, `_internal/doremi/ui/qml/MainShell.qml` + `Doremi/qmldir`
(32 QML), `fonts/Inter-Regular.ttf`, `locales/es.json`,
`db/migrations/env.py`, `assets/Doremi.png`,
`vlc_libs/libvlc.so.5` + `plugins/`, `doremi/native_rs/native_rs.abi3.so`.
Bundle: 926 MB, 4077 ficheros. `git diff --check` limpio,
`doremi.spec` byte-idéntico.

Smoke congelado directo (XDG aislados, offscreen, CWD propio):

```text
DOREMI_SMOKE_OK {"ok": true, "checks": {"qt_app": true, "vlc": true, "app_dirs": true,
"db_migrations": true, "fonts": true, "rust": true, "theme_bridge": true,
"qml_files": true, "qml_shell": true}, "version": "2.1.4", "frozen": true,
"meipass": ".../dist/Doremi/_internal",
"build_id": "f0b3a.linux.local", "cwd": "/tmp/opencode/f0b3a-smoke"}
exit 0
```

Smoke vía launcher desde `/` (otro CWD, env limpio sin `*_VLC_*` ni
`LD_LIBRARY_PATH`): `DOREMI_SMOKE_OK` 9/9, exit 0.

Aislamiento DB real: `~/.local/share/doremi/doremi.db` con idéntico
mtime+tamaño (1791770245 163840) antes y después de ambos smokes.

Pin VLC incluido (proceso fresco con `sys.frozen` + `_MEIPASS` al bundle,
VLC del sistema presente):

```text
PYTHON_VLC_LIB_PATH=.../_internal/vlc_libs/libvlc.so.5
vlc.dll._name      =.../_internal/vlc_libs/libvlc.so.5
VLC detected successfully → BUNDLED VLC PIN OK
```

`ldd` sobre el libvlc incluido: 0 dependencias sin resolver. Referencias
glibc máximas: exe 2.14, libvlc 2.14, `native_rs.abi3.so` 2.34 (host 2.44).

## 2. CI — `linux-portable.yml` en `ubuntu-22.04` (run 38329666926, `success`)

https://github.com/Eirom16/Doremi-Rust/actions/runs/38329666926
(commit `e61ae57`, 24/24 pasos en verde; runs previos 38325270528 /
38325398101 / 38325568632 / 38326023910 documentan los fallos intermedios:
cabeceras dbus, `pytest-asyncio`, README excluido por gitignore,
word-splitting en SHA256 — todos con causa raíz y fix registrados.)

Baseline registrado (`linux-manifest.txt` del artifact):
`ldd (Ubuntu GLIBC 2.35-0ubuntu3.15) 2.35`, Python 3.12.15, rustc 1.99.0,
VLC Ubuntu 3.0.16-1build7 (`libvlc5` + `libvlccore9` + `vlc-plugin-base`).

| Paso | Resultado |
|---|---|
| Wheel release Linux (`maturin build --release --locked`) | OK (`doremi_native_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl`, extensión verificada en site-packages) |
| Tests nativos en runner | **17 passed** |
| Tests regresión packaging Linux | **9 passed** |
| Suite completa (sin skips) | **385 passed**, 1 warning en 10.74 s |
| Stamp `BUILD_VERSION=2.1.4` + `BUILD_ID=f0b3a.linux.e61ae5741f60` | OK |
| PyInstaller `doremi-linux.spec` (onedir) + launcher | OK |
| Estructura: exe 18.6 MB + 32 QML + qmldir + fuentes + locales + migraciones + PNG + `native_rs.abi3.so` (1 057 432 B) + `libvlc.so.5`/`plugins` (ldd sin pendientes) | OK (bundle 917 MB, 4052 ficheros) |
| Smoke directo (offscreen, XDG aislados, DB real intacta) | `DOREMI_SMOKE_OK` 9/9, exit 0 |
| Smoke vía launcher desde `/` (otro CWD) | `DOREMI_SMOKE_OK` 9/9, exit 0 |
| Clean-env `ubuntu:22.04` sin VLC del sistema (`no system libvlc, good`) | `DOREMI_SMOKE_OK` 9/9 → `CLEAN_ENV=PASS` |
| Probe `ubuntu:24.04` (informativo) | `DOREMI_SMOKE_OK` 9/9, `DISTRO_24_04_EXIT=0` |
| tar.gz + MANIFEST + SHA256 + upload (7 días) | OK |

Salida literal del smoke congelado (directo, CI):

```text
DOREMI_SMOKE_OK {"ok": true, "checks": {"qt_app": true, "vlc": true, "app_dirs": true,
"db_migrations": true, "fonts": true, "rust": true, "theme_bridge": true,
"qml_files": true, "qml_shell": true}, "version": "2.1.4", "frozen": true,
"meipass": "/home/runner/work/Doremi-Rust/Doremi-Rust/dist/Doremi/_internal",
"build_id": "f0b3a.linux.e61ae5741f60", "cwd": "/home/runner/work/_temp/doremi-smoke"}
```

Regresión Windows: el workflow `Windows portable (PyInstaller)` disparado por
el PR #7 sobre `abc17e1` (incluye el fix compartido de `vlc_check.py`) terminó
`success` — el pipeline Windows verificado no se altera.

## 3. Tamaños (CI oficial, registrados, sin límite)

| Artefacto | Tamaño |
|---|---|
| `Doremi` (ELF) | ~18,6 MB |
| Bundle `dist/Doremi` (4052 ficheros) | 917 MB en disco |
| `Doremi-Linux-x86_64-Portable.tar.gz` (4059 ficheros) | **361 MB** (378 458 556 B) |

SHA-256: `faf1f29f39ffa0254c3d61bbaac83f0f9108423b2921907dd51d4d72e0ece124`

## 4. Artifact

`Doremi-Linux-x86_64-Portable` (run 38329666926 → Artifacts, expira en 7 días):
`Doremi-Linux-x86_64-Portable.tar.gz` + `.tar.gz.sha256` + `linux-manifest.txt`
(manifest validado: glibc 2.35, VLC 3.0.16, `CLEAN_ENV=PASS`,
`DISTRO_24_04_EXIT=0`).
Uso: extraer, `./Doremi --smoke-test` (esperar `DOREMI_SMOKE_OK`, exit 0),
luego `./doremi.sh` o `./Doremi`.

Verificación adicional del artifact oficial (descargado por SHA, suma OK):
extraído en máquina distinta (CachyOS, glibc 2.44) y ejecutado vía
`doremi.sh` desde `/tmp` con env limpio → `DOREMI_SMOKE_OK` 9/9, exit 0,
`build_id=f0b3a.linux.e61ae5741f60`. Compatibilidad hacia adelante
glibc 2.35 → 2.44 demostrada en la práctica.

## 5. Git

Commits en la rama (pushed): spec+launcher+packaging · fix compartido
`vlc_check` · tests Linux · workflow CI · informes · 4 fixes CI con evidencia
(dbus-dev, dev extra, README en gitignore, xargs -0) · informes finales.
`git diff --check` limpio. Árbol original del usuario intacto.

## 6. Verificado / fuera de alcance

- Entorno limpio sin VLC global → VERIFICADO (`CLEAN_ENV=PASS`,
  contenedor `ubuntu:22.04` sin libvlc del sistema, smoke 9/9).
- Distro adicional más reciente → VERIFICADO (`ubuntu:24.04`, smoke 9/9,
  exit 0) + artifact oficial re-ejecutado en CachyOS/glibc 2.44 (9/9).
- Arranque bajo X11/XWayland/Wayland y reproducción audible real → fuera de
  alcance headless (solo offscreen en CI); categorías declaradas NO
  verificadas (sin servidor gráfico ni assert de audio en CI).
