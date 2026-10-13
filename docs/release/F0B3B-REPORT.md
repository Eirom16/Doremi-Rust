# F0B-3B — Linux AppImage type 2 (REPORT)

**Fecha:** 2026-10-13 · **Rama:** `build/f0b3b-linux-appimage`
**Base:** `build/f0b3a-linux-portable @ ef3f173` (PR #7 abierto sin fusionar)
**Objetivo:** `Doremi-2.1.4-x86_64.AppImage` (tipo 2, x86_64) a partir del
portable verificado en F0B-3A, sin depender de Python/Rust/VLC globales.
Sin Arch/DEB/RPM. Sin GitHub Releases.

## 1. Arquitectura AppDir

```text
Doremi-2.1.4-x86_64.AppImage  (ELF static-pie runtime + squashfs zstd, tipo 2)
└── Doremi.AppDir/
    ├── AppRun                   sh, ejecutable; invoca usr/bin/doremi ("$@");
    │                            NO duplica env VLC; respeta $APPDIR/$OWD;
    │                            preserva CWD del llamante; sin cd
    ├── doremi.desktop           Name=Doremi, Exec=doremi %U, Icon=doremi,
    │                            Type=Application, Categories=Audio;Music;...,
    │                            Terminal=false; SIN MimeType (protocolo no probado);
    │                            desktop-file-validate PASS
    ├── doremi.png               1080x1080 RGBA (820115 B)
    ├── .DirIcon -> doremi.png   symlink requerido por la spec
    └── usr/
        ├── bin/Doremi           copia intacta del onedir (cp -a, +x, 19.5 MB)
        ├── bin/doremi           copia byte-idéntica de dist doremi.sh (+x)
        ├── bin/_internal/       copia intacta de dist _internal (== _MEIPASS):
        │   ├── doremi/ui/qml/** 32 QML + Doremi/qmldir
        │   ├── doremi/assets/fonts/ Inter/JetBrainsMono (+OFL texts)
        │   ├── doremi/locales/  es.json, en.json
        │   ├── doremi/db/migrations/ env.py + versions/ (alembic por ruta)
        │   ├── doremi/native_rs/ puente + native_rs.abi3.so al lado
        │   ├── vlc_libs/        libvlc.so.5 + libvlccore + plugins/**
        │   └── resto            Qt6, Python 3.12 embebido, site-packages
        └── share/doc/doremi/
            ├── LICENSE.txt              Doremi GPL-3.0 (del portable)
            ├── THIRD-PARTY-NOTICES.txt  avisos F0B-3A (del portable)
            └── APPIMAGE-NOTICES.txt     addendum runtime (nuevo, ver §6)
```

Uso real (NO basta AppDir/AppRun): `./Doremi-2.1.4-x86_64.AppImage
--appimage-extract-and-run --smoke-test` debe imprimir `DOREMI_SMOKE_OK`
9/9, `ok == true`, exit 0. También soporta `--appimage-extract` +
`squashfs-root/AppRun`, otro CWD y montaje FUSE directo.

## 2. Decisiones de diseño

**Reutilizar el onedir + `_internal` sin reempaquetar.** `build-appdir.sh`
copia con `cp -a` (permisos intactos) y verifica la lista F0B-3A
relocalizada bajo `usr/bin/`. Deliberadamente NO usa linuxdeploy /
linuxdeployqt (evita una segunda copia de Qt/VLC), NO copia glibc ni
drivers GPU del host y NO hace strip para ahorrar megabytes. La
funcionalidad es prioritaria.

**AppRun delega en el launcher verificado.** `packaging/linux/doremi.sh`
sigue siendo la única fuente de verdad para `LD_LIBRARY_PATH` (prepend),
`PYTHON_VLC_LIB_PATH` (solo si ausente) y `VLC_PLUGIN_PATH` (solo si
ausente). AppRun solo resuelve `$APPDIR` (runtime o `readlink -f` para
extracción directa) y hace `exec "$APPDIR/usr/bin/doremi" "$@"`. Tests
verifican que AppRun NO exporta vars VLC y reenvía args (`--smoke-test`).

**Desktop honesto.** Se crea `packaging/appimage/doremi.desktop` sin
`MimeType`: `packaging/doremi.desktop` anuncia
`x-scheme-handler/doremi` pero ningún handler está implementado ni
probado (grep sin resultados), así que el AppImage no lo reclama.
`packaging/doremi.desktop` queda intacto. Icono `doremi` (sin extensión)
resuelve a `doremi.png` + `.DirIcon`.

**Baseline: Ubuntu 22.04 (glibc 2.35) en CI.** El build local de esta
fase se hizo en CachyOS (glibc 2.44) por falta de docker en la máquina
de desarrollo; ese binario es prueba de concepto, NO el artifact de
distribución. El artifact oficial lo construye CI sobre `ubuntu-22.04`
con el mismo commit (ver workflow y RESULTS §2).

## 3. Problemas encontrados y causa raíz

1. **`/tmp` lleno truncó la primera extracción B (0-byte `doremi`).**
   `/tmp` es tmpfs 3.8G al 100% (restos F0B-3A: 1.3G artifact + 862M
   venv + extracciones `appimage_extracted_*` sin limpiar). El runtime
   extrae por defecto bajo `$TMPDIR` (`/tmp`), y la extracción falló en
   silencio dejando `squashfs-root/usr/bin/doremi` vacío → `exec:
   Formato de ejecutable incorrecto`. Causa: presión de disco, no bug
   del AppImage (el payload era correcto: `Doremi.AppDir/usr/bin/doremi`
   2024 B). Fix: limpiar `/tmp/appimage_extracted_*` y restos propios,
   exportar `TMPDIR=<worktree>/.tmp-appimage` (en `/home`, 138G libres)
   para todas las pruebas AppImage; re-ejecutado B PASS. Lección para CI:
   el runner tiene `/tmp` amplio, pero el workflow no asume nada y usa
   `$RUNNER_TEMP`.
2. **Tests demasiado estrictos sobre comentarios.** Las aserciones
   `... not in text` fallaban por menciones en comentarios (`VLC_*` en
   AppRun, `linuxdeploy`/`strip` en build-appdir.sh). Fix: filtrar líneas
   que empiezan por `#` y asertar solo sobre código (`*_PATH=`,
   invocaciones reales).
3. **`uv.lock` huérfano y `.venv` con `.python-version` discordante.**
   `uv run` generó `uv.lock` no versionado y el worktree heredó un
   `.venv` 3.12 con `.python-version` 3.13.9. Fix: borrar `uv.lock` /
   cachés, documentar que el venv local es 3.12.14 (coherente con el
   baseline) y no commitearlo (gitignored).

## 4. Archivos modificados/creados

- `packaging/appimage/AppRun` (nuevo, +x) · `doremi.desktop` (nuevo, sin
  MimeType) · `build-appdir.sh` (nuevo, +x) · `APPIMAGE-NOTICES.txt`
  (nuevo) · `tests/test_linux_appimage.py` (nuevo, 7 tests) ·
  `.github/workflows/linux-appimage.yml` (nuevo). `doremi.spec`,
  `doremi-linux.spec`, `packaging/linux/doremi.sh`,
  `packaging/doremi.desktop` y el packaging Windows quedan intactos
  (verificado: `git diff HEAD -- doremi.spec` vacío).

## 5. Versiones y herramientas

- Oficial (CI `ubuntu-22.04`, PENDIENTE de run — ver RESULTS §2):
  Python 3.12, Rust estable + `maturin build --release --locked`,
  PyInstaller 6.x, VLC Ubuntu 22.04 (`libvlc5` + `libvlccore9` +
  `vlc-plugin-base`), `appimagetool 1.9.1` (ver abajo). Registro por
  build en `BUILD-MANIFEST-AppImage.txt` + `pip-freeze-appimage.txt`.
- Local (prueba de concepto, este informe): CachyOS rolling x86_64,
  glibc 2.44 (`ldd (GNU libc) 2.44`), Python 3.12.14 (uv), rustc 1.99.0,
  maturin 1.15.0, PyInstaller 6.22.3, PySide6 6.12.0, VLC sistema 3.0.24
  (`/usr/lib/libvlc.so.5.6.1`, libvlccore 9.0.1, plugins Arch). Wheel
  `doremi_native_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl`.
- appimagetool (pinneado, misma versión en local y CI):
  URL `https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage`,
  SHA-256 `ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0`
  (15M), versión reportada `appimagetool, continuous build (git version
  8c8c91f), build 296 built on 2025-12-04 17:55:56 UTC` (el asset 1.9.1
  resuelve a ese build; se registra literal). Uso sin FUSE vía
  `--appimage-extract-and-run` y `./squashfs-root/AppRun` extraído.
- Runtime embebido: descargado por appimagetool desde
  `https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64`
  (944632 B), tipo 2. `file` del AppImage: `ELF 64-bit LSB pie
  executable, x86-64, static-pie linked`.

## 6. Riesgos y límites conocidos

- El smoke valida arranque hasta shell QML con controladores a null, no
  sesión completa con red/login. La experiencia de escritorio real (ventana
  principal, interacción) NO se declara verificada por superar smokes
  (aunque offscreen + xcb/XWayland + wayland nativo pasen).
- Tamaño local: AppDir 927 MB / 4083 ficheros, AppImage 334 MB (squashfs
  zstd). Sin dieta antes de demostrar funcionamiento; oportunidades de
  optimización (plugins VLC/Qt redundantes) quedan para fase posterior.
- Licencias: el AppDir incluye `LICENSE.txt` + `THIRD-PARTY-NOTICES.txt`
  + `APPIMAGE-NOTICES.txt` (runtime MIT + musl/libfuse-LGPL2/squashfuse/
  libzstd/zlib). La release pública sigue BLOCKED hasta cerrar
  source-offers y textos completos (VLC §1, Qt §2 — auditoría Linux
  independiente —, paquetes §3, Rust §4, Material Symbols §5, más
  runtime §a-b del addendum). Generar el AppImage NO autoriza a
  distribuirlo públicamente.
- Sin firma GPG ni sandbox; artifact temporal con retención de 7 días;
  uso interno de pruebas. Sin tags ni Releases.
