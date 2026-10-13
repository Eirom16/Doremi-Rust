# F0B-3B — Resultados de validación (RESULTS)

**Fecha:** 2026-10-13 · **Rama:** `build/f0b3b-linux-appimage`
**Base:** `build/f0b3a-linux-portable @ ef3f173`
**PR:** contra `build/f0b3a-linux-portable` mientras el PR #7 siga abierto
(ver §6). **CI:** workflow `linux-appimage.yml` en `ubuntu-22.04` —
PENDIENTE de run tras el push (este documento registra la PoC local;
se actualizará con el run verde).

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
`.mount`), `.f0b3b-sentinel` sobrevive a `setup()` + segunda ejecución;
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

## 2. CI — `linux-appimage.yml` en `ubuntu-22.04`

PENDIENTE de run tras el push de esta rama. El workflow (11 pasos §11
del enunciado) reconstruye desde ESTE commit: toolchain + `vlc_libs`
Ubuntu 22.04, wheel `--locked`, `test_linux_packaging` +
`test_linux_appimage` + suite completa, `git diff --check`, stamp
`BUILD_ID=f0b3b.linux.<sha>`, PyInstaller, validación del portable
previo (directo + launcher), `build-appdir.sh`, `desktop-file-validate`,
appimagetool 1.9.1 sin FUSE, generación tipo 2 x86_64, pruebas A/B/C/D
del AppImage real, clean-env `ubuntu:22.04` sin VLC, probe `ubuntu:24.04`,
Xvfb xcb, probe VLC/audio con wav sintético, persistencia con centinela,
auditoría ELF/glibc, SHA-256 + manifiesto + comparativa de tamaños y
artifact de 7 días. Sin tags ni Releases. Se actualizará esta sección
con el run verde (o PARTIAL/BLOCKED honesto si algo queda pendiente).

## 3. Tamaños (PoC local, registrados, sin límite)

| Artefacto | Tamaño |
|---|---|
| `Doremi` (ELF) | 19 497 424 B (~18,6 MB) |
| Bundle `dist/Doremi` (4077 ficheros) | 926 MB (958894102 B) |
| `Doremi.AppDir` (4083 ficheros) | 927 MB (959761552 B) |
| `Doremi-2.1.4-x86_64.AppImage` | **334 MB (350038520 B)** |
| Referencia F0B-3A tar.gz oficial (CI) | 361 MB (378458556 B) |

El AppImage (squashfs zstd) es menor que el tarball portable pese a
añadir runtime (944632 B) + wrapper; la funcionalidad es prioritaria y
no se recortó ningún plugin. Oportunidades de dieta (plugins VLC/Qt
redundantes) quedan documentadas para fase posterior, no aplicadas.

SHA-256 (PoC local, `f0b3b.linux.local` — el oficial será el del run CI):

```text
43005f7d4e0d8a54d1ecc82f4c32dae37b2fdfa644235cd2d53753acbec385c4  Doremi-2.1.4-x86_64.AppImage
```

appimagetool: `ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0`.

## 4. Artifact

PoC local (NO distribuir; build glibc 2.44, `BUILD_ID=f0b3b.linux.local`).
El artifact oficial será `Doremi-2.1.4-x86_64.AppImage` + `.sha256` +
`BUILD-MANIFEST-AppImage.txt` + `pip-freeze-appimage.txt` +
`appimagetool.log` + `appimagetool.sha256` publicados por el run CI con
retención de 7 días. Uso: `chmod +x ...AppImage; ./...AppImage
--appimage-extract-and-run --smoke-test` (esperar `DOREMI_SMOKE_OK`,
exit 0). Requiere en el host solo las bibliotecas base listadas en §1.

## 5. Git

Rama `build/f0b3b-linux-appimage` desde `ef3f173` en worktree
`/home/eirom/Doremi-F0B3B` (fuera de `/tmp`). Árbol original del usuario
intacto; sin reset/clean/stash/force-push. Commits lógicos (packaging +
tests · workflow · informes). `git diff --check` limpio. `doremi.spec`
byte-idéntico. PR contra `build/f0b3a-linux-portable` (no auto-merge,
no tocar `main`).

## 6. Verificado / fuera de alcance (honesto)

- AppImage real ejecutado (A + B + C + FUSE directo) → VERIFICADO local.
- `AppDir/AppRun` solo → NO se considera validación del AppImage.
- FUSE → VERIFICADO local (montaje `.mount_*`); en CI se revalida y NO
  se declarará PASS solo con extract-and-run.
- X11 xcb + Wayland nativo (smoke) → VERIFICADO local; Xvfb + ventana
  real → PENDIENTE.
- VLC incluido + apertura/avance con fixture → VERIFICADO local;
  escucha audible → PENDIENTE.
- XDG persistencia con centinela + DB real intacta → VERIFICADO local.
- Ubuntu 22.04/24.04 limpios, suite CI verde, artifact oficial →
  PENDIENTE de run (sección §2 se actualizará).
