# F0B-3A — Resultados de validación (RESULTS)

**Fecha:** 2026-10-12 · **Rama:** `build/f0b3a-linux-portable`
**Base:** `build/f0b2b-windows-installer @ b2162d0`
**PR:** (pendiente de crear contra `build/f0b2b-windows-installer`; PR #6 sigue abierto)

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

## 2. CI — `linux-portable.yml` en `ubuntu-22.04`

(TBD: run pendiente — se actualiza esta sección con el enlace y la tabla.)

| Paso | Resultado |
|---|---|
| Wheel release Linux (`maturin build --release --locked`) | TBD |
| Tests nativos + packaging + suite completa | TBD |
| Stamp `BUILD_VERSION=2.1.4` + `BUILD_ID=f0b3a.linux.<sha>` | TBD |
| PyInstaller `doremi-linux.spec` (onedir) + launcher | TBD |
| Estructura + `native_rs.abi3.so` + `libvlc.so.5`/`plugins` + glibc 2.35 | TBD |
| Smoke directo (offscreen, XDG aislados, DB real intacta) | TBD |
| Smoke vía launcher desde otro CWD | TBD |
| Clean-env `ubuntu:22.04` sin VLC del sistema | TBD |
| Probe `ubuntu:24.04` (informativo) | TBD |
| tar.gz + MANIFEST + SHA256 + upload (7 días) | TBD |

## 3. Tamaños (local, registrados, sin límite)

| Artefacto | Tamaño |
|---|---|
| `Doremi` (ELF) | 19 497 424 B (~18,6 MiB) |
| Bundle `dist/Doremi` (4077 ficheros) | 926 MB en disco |
| `Doremi-Linux-x86_64-Portable.tar.gz` oficial | TBD (CI) |

## 4. Artifact

`Doremi-Linux-x86_64-Portable` (run CI → Artifacts, expira en 7 días):
`Doremi-Linux-x86_64-Portable.tar.gz` + `.sha256` + `linux-manifest.txt`.
Uso: extraer, `./Doremi --smoke-test` (esperar `DOREMI_SMOKE_OK`, exit 0),
luego `./doremi.sh` o `./Doremi`. TBD: nombre exacto, tamaño y SHA-256.

## 5. Git

Commits previstos en la rama (pushed): spec+launcher+packaging ·
fix compartido `vlc_check` · tests Linux · workflow CI · informes.
`git diff --check` limpio. Árbol original del usuario intacto.

## 6. No verificado (local)

- Entorno limpio sin VLC global (sin docker/userns en la máquina de
  desarrollo) → cubierto por el paso clean-env de CI; hasta su verde,
  PARTIAL.
- Distro adicional más reciente → probe `ubuntu:24.04` de CI (informativo).
- Arranque bajo X11/XWayland/Wayland y reproducción audible real → fuera de
  alcance headless (solo offscreen en CI); categorías declaradas no
  verificadas.
