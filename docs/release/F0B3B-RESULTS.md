# F0B-3B — Resultados de validación (RESULTS)

**Fecha:** 2026-10-13 · **Rama:** `build/f0b3b-linux-appimage`
**Base:** `build/f0b3a-linux-portable @ ef3f173`
**PR:** https://github.com/Eirom16/Doremi-Rust/pull/8 contra
`build/f0b3a-linux-portable` (el PR #7 sigue abierto).
**CI:** workflow `linux-appimage.yml` en `ubuntu-22.04` — VERDE en
`38338041664` (push) y `38338045717` (PR), commit `2dde34f`
(`BUILD_ID=f0b3b.linux.2dde34f12c29`), con X11/Xvfb ya en PASS.
Verdes previos `38337053313`/`38337057033` (`0ebe132`, sin el fix X11).
La §1 documenta además la PoC local.

## 1. Validación local (worktree, venv Python 3.12.14, CachyOS glibc 2.44)

Prueba de concepto del AppDir/AppImage — NO es el artifact de
distribución (el baseline oficial es Ubuntu 22.04 / glibc 2.35 vía CI,
§2). `TMPDIR` bajo el worktree (`/home`, 138G) tras el incidente `/tmp`
lleno documentado en REPORT §3.

```bash
# Toolchain local verificada
python --version  # 3.12.14 · rustc 1.99.0 · maturin 1.15.0 · PyInstaller 6.22.3
rm -rf vlc_libs && mkdir -p vlc_libs/plugins
cp -P /usr/lib/libvlc.so.5* vlc_libs/ && cp -P /usr/lib/libvlccore.so* vlc_libs/
cp -r /usr/lib/vlc/plugins/* vlc_libs/plugins/   # 15M, ldd sin pendientes
(cd src/doremi/native_rs && maturin build --release --locked --out dist)
# wheel: doremi_native_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl
pip install src/doremi/native_rs/dist/*.whl
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/ -q
# 392 passed (385 preexistentes + 7 tests/test_linux_appimage.py)
printf 'BUILD_VERSION = "2.1.4"\nBUILD_ID = "f0b3b.linux.local"\n' > src/doremi/_build_version.py
pyinstaller doremi-linux.spec   # exit 0 (warnings ldd menores por permisos, como F0B-3A)
cp packaging/linux/doremi.sh dist/Doremi/doremi.sh
bash packaging/appimage/build-appdir.sh dist/Doremi Doremi.AppDir
desktop-file-validate packaging/appimage/doremi.desktop && desktop-file-validate Doremi.AppDir/doremi.desktop
ARCH=x86_64 /tmp/opencode/f0b3b/squashfs-root/AppRun Doremi.AppDir Doremi-2.1.4-x86_64.AppImage
```

Estructura verificada: `Doremi.AppDir/AppRun` (+x), `doremi.desktop`,
`doremi.png` (1080x1080), `.DirIcon -> doremi.png`, `usr/bin/Doremi`
(ELF 19 497 424 B), `usr/bin/doremi` (byte-idéntico a `dist` 2024 B),
`usr/bin/_internal/` intacto (32 QML + qmldir + fuentes + locales +
migraciones + PNG + `native_rs.abi3.so` 1 057 384 B +
`vlc_libs/libvlc.so.5` + `plugins/` + Qt plataformas/QML),
`usr/share/doc/doremi/{LICENSE,THIRD-PARTY-NOTICES,APPIMAGE-NOTICES}.txt`.
AppDir: 927 MB (959761552 B), 4083 ficheros. `git diff --check` limpio,
`doremi.spec` intacto.

Portable previo revalidado (mismo commit): directo `DOREMI_SMOKE_OK` 9/9
exit 0 + launcher desde `/` 9/9 exit 0, DB real intacta
(1791770245 163840 antes = después).

Smoke del AppImage REAL (todos `DOREMI_SMOKE_OK` 9/9, `ok == true`, exit 0):

| Prueba | Comando | Resultado local |
|---|---|---|
| AppDir/AppRun (referencia, NO suficiente) | `Doremi.AppDir/AppRun --smoke-test` | 9/9, `meipass=.../Doremi.AppDir/usr/bin/_internal`, `build_id=f0b3b.linux.local` |
| A. extract-and-run | `AppImage --appimage-extract-and-run --smoke-test` | 9/9, `meipass=/tmp/.../appimage_extracted_*/usr/bin/_internal` |
| B. extract + squashfs-root | `AppImage --appimage-extract` + `./squashfs-root/AppRun --smoke-test` | 9/9, `meipass=.../squashfs-root/usr/bin/_internal` (tras fix TMPDIR; primer intento falló por `/tmp` lleno, ver REPORT §3) |
| C. otro CWD | desde `/`: `AppImage --appimage-extract-and-run --smoke-test` | 9/9, `cwd=/` |
| D. FUSE directo | `AppImage --smoke-test` (sin flags extract, `/dev/fuse` presente) | 9/9, `meipass=.../.mount_Doremi*/usr/bin/_internal` → **FUSE=PASS** (montaje real, no extracción) |

Qt/X11/Wayland (plugins presentes: `libqxcb/libqwayland/libqoffscreen`,
`Qt/qml/QtQuick`, `QtQuickWidgets`, `imageformats`, `xcbglintegrations`,
`wayland-*`, fuentes Inter/JetBrainsMono):

| Backend | Resultado local |
|---|---|
| offscreen (`QT_QPA_PLATFORM=offscreen`) | 9/9 exit 0 (todos los smokes base) |
| xcb bajo XWayland real (`DISPLAY=:0`, Plasma) | 9/9 exit 0 |
| wayland nativo (`WAYLAND_DISPLAY=wayland-0`, Plasma) | 9/9 exit 0 |
| Xvfb virtual | PENDIENTE (sin Xvfb en la máquina; el workflow CI lo intenta) |
| Ventana principal / interacción desktop | PENDIENTE (el smoke solo carga MainShell con controladores a null; NO se declara experiencia verificada) |

VLC/audio (sin red, fixture sintético autorizado `tone.wav` 440Hz 1s):

```text
vlc lib: .../squashfs-root/usr/bin/_internal/vlc_libs/libvlc.so.5  → BUNDLED_VLC_PIN_OK
VLC_INSTANCE_OK · play() -> 0 · state: State.Ended · time_ms: 941 → OPEN+ADVANCE OK
ldd vlc_libs/libvlc.so.5: 0 pendientes; NEEDED: libvlccore.so.9, libgcc_s, libc
```

PulseAudio sobre PipeWire 1.6.9 + HDA Intel presentes. La apertura y el
avance hasta `Ended` (941 ms) prueban demux/decode con la lib incluida;
la salida audible por altavoces NO se afirma (sin assert de escucha).
`vlc.Instance()` solo, sin este probe, no se considera prueba de audio.

Persistencia XDG (centinela, sin tocar DB real): `AppDirs.database`
resuelve a `$XDG_DATA_HOME/doremi/doremi.db` (nunca a `squashfs-root` ni
`.mount`), `.f0b3b-probe` sobrevive a `setup()` + segunda ejecución;
DB real `~/.local/share/doremi/doremi.db` intacta. `PERSISTENCE=PASS`.

Compatibilidad:

| Entorno | Resultado |
|---|---|
| CachyOS local (glibc 2.44, misma máquina del build) | AppImage A/B/C/D + xcb + wayland PASS (forward-compat informal, NO es prueba independiente) |
| Ubuntu 22.04 limpio sin VLC | PENDIENTE CI (sin docker local) |
| Ubuntu 24.04 | PENDIENTE CI (informativo) |
| CachyOS independiente | PENDIENTE (sin contenedor local) |

Auditoría ELF: exe `GLIBC_2.14` máx, libvlc `2.14`, rust ext `2.34`
(host 2.44); `ldd` del stub solo pide `libdl/libz/libpthread/libc`;
host debe aportar `libgl1 libegl1 libxkbcommon0 libdbus-1-3
libfontconfig1 libsm6 libxext6 libxrender1 libpulse0` + glibc (≥2.34
local; ≥2.35 baseline CI). Intencionadamente NO se empaquetan glibc ni
drivers.

## 2. CI — `linux-appimage.yml` en `ubuntu-22.04` (run 38338041664, `success`)

https://github.com/Eirom16/Doremi-Rust/actions/runs/38338041664
(commit `2dde34f`, todos los pasos en verde, incluido X11/Xvfb; el run
PR espejo `38338045717` también `success`. El HEAD `b1a1cf2` (solo
cambia docs respecto a `2dde34f`; los docs no entran al bundle) quedó
revalidado en verde por el run PR `38338686233` (artifact
`d1634c00edb607315b70db2efc2061727ea59fa2adb801b5eb1a9dbc8d36d556`,
`BUILD_ID=f0b3b.linux.5d418256554e`). Runs previos documentan los
fallos intermedios con causa raíz y fix: `38335631037` (`open(sentin)`
→ NameError en persistencia, renombrado a `probe_file`) y `38337053313`
(`X11_XVFB=FAILED` por `libxcb-cursor0` ausente en el runner, ver
REPORT §3). El código validado es idéntico salvo esos fixes.

Baseline registrado (`BUILD-MANIFEST-AppImage.txt` del artifact):
`ldd (Ubuntu GLIBC 2.35-0ubuntu3.15) 2.35`, Python 3.12.15, rustc 1.99.0,
maturin 1.15.0 `--locked`, PyInstaller 6.22.3, PySide6 6.12.0, VLC Ubuntu
3.0.16-1build7 (`libvlc5` + `libvlccore9` + `vlc-plugin-base`),
python-vlc 3.0.21203. appimagetool 1.9.1, SHA-256
`ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0`,
versión `continuous build (git 8c8c91f), build 296 built on 2025-12-04
17:55:56 UTC`; runtime `type2-runtime/continuous` (944632 B, BuildID
`6068f2cec943069c072c32fe680557d1e5f7ec6f`, idéntico al local).

| Paso | Resultado |
|---|---|
| Wheel release Linux (`maturin build --release --locked`) | OK |
| Tests nativos en runner | **17 passed** |
| Tests regresión packaging (portable + appimage) | **16 passed** |
| Suite completa (sin skips) | **392 passed** en 11.71 s |
| Stamp `BUILD_VERSION=2.1.4` + `BUILD_ID=f0b3b.linux.<sha12>` | OK (`f0b3b.linux.2dde34f12c29` en el run canónico) |
| PyInstaller `doremi-linux.spec` (onedir) + launcher | OK (bundle 917 MB, 4052 ficheros, rust ext 1 057 432 B) |
| Smoke directo (offscreen, XDG aislados, DB real intacta) | `DOREMI_SMOKE_OK` 9/9, exit 0 |
| Smoke vía launcher desde `/` (otro CWD) | `DOREMI_SMOKE_OK` 9/9, exit 0 |
| AppDir (`build-appdir.sh`, launcher byte-idéntico) | OK (918 MB, 4058 ficheros) |
| `desktop-file-validate` (fuente + AppDir) + `.DirIcon` | `DESKTOP_VALIDATE=PASS` |
| AppImage tipo 2 x86_64 sin FUSE (`squashfs-root/AppRun`) | OK (`Doremi-2.1.4-x86_64.AppImage`, 331 MB, `file` = ELF static-pie) |
| A. `--appimage-extract-and-run --smoke-test` | `SMOKE_A=PASS` 9/9 |
| B. `--appimage-extract` + `squashfs-root/AppRun --smoke-test` | `SMOKE_B=PASS` 9/9 |
| C. otro CWD (`/`) | `SMOKE_C=PASS`, `cwd=/` |
| D. FUSE directo (`/dev/fuse` presente) | `FUSE=PASS` (montaje `.mount_*`, no extracción) |
| Clean-env `ubuntu:22.04` sin VLC del sistema | `CLEAN_ENV_2204=PASS` 9/9 |
| Probe `ubuntu:24.04` (informativo) | `DISTRO_24_04_EXIT=0` 9/9 |
| X11 xcb bajo Xvfb | `X11_XVFB=PASS` en el run 38338041664 (tras instalar `libxcb-cursor0` del host; ver REPORT §3) |
| VLC probe (wav sintético 440Hz, sin red) | `VLC_INSTANCE=OK` desde `.../squashfs-root/usr/bin/_internal/vlc_libs/libvlc.so.5`, `play() -> 0`, `State.Ended` (time 0 ms headless); salida audible NO afirmada |
| Persistencia XDG (probe, sin DB real) | `PERSISTENCE_PROBE=OK` + `SECOND_RUN=OK` → `PERSISTENCE=PASS` |
| Auditoría ELF/glibc | exe máx `GLIBC_2.14`, libvlc `2.14`, rust ext `2.34`; host: `libgl1 libegl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libsm6 libxext6 libxrender1 libpulse0 libxcb-cursor0 (xcb)` + glibc ≥ 2.35 |
| SHA-256 + manifiesto + artifact 7 días | OK (ver §3–§4) |

Salida literal del smoke congelado vía AppImage (A, CI):

```text
DOREMI_SMOKE_OK {"ok": true, "checks": {"qt_app": true, "vlc": true, "app_dirs": true,
"db_migrations": true, "fonts": true, "rust": true, "theme_bridge": true,
"qml_files": true, "qml_shell": true}, "version": "2.1.4", "frozen": true,
"meipass": ".../appimage_extracted_*/usr/bin/_internal",
"build_id": "f0b3b.linux.0ebe1327cdf8", "cwd": "/home/runner/work/_temp/appimage-smoke-a"}
```

Regresión Windows: sin cambios compartidos en esta fase (solo
`packaging/appimage/`, workflow Linux, tests Linux y docs;
`doremi.spec` byte-idéntico, `git diff HEAD -- doremi.spec` vacío), el
pipeline Windows verificado de F0B-3A no se altera.

## 3. Tamaños (oficial CI + PoC local, registrados, sin límite)

| Artefacto | Oficial CI (run 38337053313) | PoC local (glibc 2.44) |
|---|---|---|
| `Doremi` (ELF) | onedir 917 MB, 4052 ficheros (rust ext 1 057 432 B) | 19 497 424 B, 4077 ficheros, 926 MB |
| `Doremi.AppDir` | **918 MB (951192035 B), 4058 ficheros** | 927 MB (959761552 B), 4083 ficheros |
| `Doremi-2.1.4-x86_64.AppImage` | **331 MB (346855928 B)** | 334 MB (350038520 B) |
| Referencia F0B-3A tar.gz oficial (CI) | 361 MB (378458556 B) | — |

El AppImage (squashfs zstd) es menor que el tarball portable pese a
añadir runtime (944632 B) + wrapper; la funcionalidad es prioritaria y
no se recortó ningún plugin. Oportunidades de dieta (plugins VLC/Qt
redundantes) quedan documentadas para fase posterior, no aplicadas.

SHA-256 oficial (CI, `BUILD_ID=f0b3b.linux.2dde34f12c29`, run 38338041664):

```text
6a6538c33f30a243a2a64943a08c6184288b42135a6c022a1a42fc585c3156b8  Doremi-2.1.4-x86_64.AppImage
```

SHA-256 del run verde previo (`0ebe132`, referencia):

```text
a627c74d181bd6c24435d0eab4391b1fda7d54fc2ac625499345a5d86aa6f109  Doremi-2.1.4-x86_64.AppImage
```

SHA-256 PoC local (`f0b3b.linux.local`, NO distribuir):

```text
43005f7d4e0d8a54d1ecc82f4c32dae37b2fdfa644235cd2d53753acbec385c4  Doremi-2.1.4-x86_64.AppImage
```

appimagetool: `ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0`.

## 4. Artifact

Oficial (run 38338041664 → Artifacts `Doremi-Linux-x86_64-AppImage`,
expira en 7 días): `Doremi-2.1.4-x86_64.AppImage` (331 MB, SHA-256
`6a6538c3…c3156b8`) + `.sha256` + `BUILD-MANIFEST-AppImage.txt` +
`pip-freeze-appimage.txt` + `appimagetool.log` + `appimagetool.sha256`.
Uso: `chmod +x Doremi-2.1.4-x86_64.AppImage;
./Doremi-2.1.4-x86_64.AppImage --appimage-extract-and-run --smoke-test`
(esperar `DOREMI_SMOKE_OK` 9/9, exit 0). Requiere en el host solo las
bibliotecas base listadas en §2 (incluido `libxcb-cursor0` para xcb).

PoC local (NO distribuir; build glibc 2.44,
`BUILD_ID=f0b3b.linux.local`, SHA `43005f7d…385c4`).

## 5. Git

Rama `build/f0b3b-linux-appimage` desde `ef3f173` en worktree
`/home/eirom/Doremi-F0B3B` (fuera de `/tmp`). Árbol original del usuario
intacto; sin reset/clean/stash/force-push. Commits lógicos (packaging +
tests · workflow · informes). `git diff --check` limpio. `doremi.spec`
byte-idéntico. PR contra `build/f0b3a-linux-portable` (no auto-merge,
no tocar `main`).

## 6. Verificado / fuera de alcance (honesto)

- AppImage real ejecutado (A + B + C + FUSE directo) → VERIFICADO local
  y en CI oficial (run 38337053313).
- `AppDir/AppRun` solo → NO se considera validación del AppImage.
- FUSE → VERIFICADO local y en CI (`FUSE=PASS` con montaje `.mount_*`
  en ambos); NO se declara PASS solo con extract-and-run.
- X11 xcb + Wayland nativo (smoke) → VERIFICADO local; Xvfb en CI →
  VERIFICADO (`X11_XVFB=PASS` en el run 38338041664 tras instalar
  `libxcb-cursor0` del host); ventana real con interacción →
  PENDIENTE (el smoke solo carga MainShell con controladores a null).
- VLC incluido + apertura/avance con fixture → VERIFICADO local y en CI
  (`play() -> 0`, `State.Ended`); escucha audible → PENDIENTE.
- XDG persistencia con probe + DB real intacta → VERIFICADO local y en
  CI (`PERSISTENCE=PASS`).
- Ubuntu 22.04 limpio sin VLC → VERIFICADO en CI (`CLEAN_ENV_2204=PASS`);
  Ubuntu 24.04 → VERIFICADO informativo (`DISTRO_24_04_EXIT=0`);
  CachyOS independiente → PENDIENTE (solo PoC en la máquina del build).
