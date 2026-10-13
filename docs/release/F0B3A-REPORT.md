# F0B-3A — Linux portable build (REPORT)

**Fecha:** 2026-10-12 · **Rama:** `build/f0b3a-linux-portable`
**Base:** `build/f0b2b-windows-installer @ b2162d0` (PR #6 abierto sin fusionar)
**Objetivo:** Doremi completo para Linux x86_64 como tarball portable
(PyInstaller onedir). Sin AppImage, sin .deb/.rpm, sin Releases.

## 1. Arquitectura del bundle

```text
Doremi-Linux-x86_64-Portable.tar.gz
└── Doremi-Linux-x86_64-Portable/
    ├── Doremi                     ELF x86_64 onedir (console=True, ~18,6 MiB)
    ├── doremi.sh                  launcher (env del bundle, desde cualquier CWD)
    ├── _internal/                 == sys._MEIPASS en este layout
    │   ├── doremi/ui/qml/**       32 QML + Doremi/qmldir (qmldir preservado)
    │   ├── doremi/assets/fonts/   Inter/JetBrainsMono/MaterialSymbols (+OFL texts)
    │   ├── doremi/locales/        es.json, en.json
    │   ├── doremi/db/migrations/  env.py + versions/*.py (fuentes: alembic
    │   │                          las carga por ruta en runtime)
    │   ├── doremi/native_rs/      puente + native_rs.abi3.so al lado
    │   ├── native_rs/             paquete del wheel (colección automática)
    │   ├── assets/                Doremi.png + fondo (AppDirs.root)
    │   ├── vlc_libs/              libvlc.so.5 + libvlccore.so.* + plugins/**
    │   └── resto                  Qt6, Python 3.12 embebido, site-packages
    ├── README.md                  instrucciones (./Doremi, ./doremi.sh, XDG)
    ├── LICENSE.txt                Doremi GPL-3.0
    ├── THIRD-PARTY-NOTICES.txt    avisos Linux (VLC/Qt/Python/Rust/fuentes)
    ├── BUILD-MANIFEST.txt         baseline glibc + versiones VLC/toolchain
    ├── pip-freeze.txt             pin exacto de paquetes Python
    ├── MANIFEST.txt               ficheros con tamaños
    └── SHA256SUMS.txt             checksums SHA-256
```

Uso: extraer y ejecutar `./Doremi` (directo) o `./doremi.sh` (launcher
recomendado). Ambos funcionan desde cualquier directorio, sin root, sin
Python/Rust/VLC globales. `./Doremi --smoke-test` debe imprimir
`DOREMI_SMOKE_OK` y salir 0.

## 2. Decisiones de diseño

**`doremi-linux.spec` (nuevo) en vez de tocar `doremi.spec`.** El spec Windows
de F0B-2B queda byte-idéntico (verificado por test). Diferencias Linux,
todas justificadas:
- Sin recurso `icon=*.ico` en el EXE (PyInstaller solo admite iconos de
  ejecutable en Windows/macOS); los PNG de runtime sí se distribuyen.
- `console=True` para que `--smoke-test` y los logs lleguen a stdout.
- keyring `SecretService` + `secretstorage` + `dbus` en hiddenimports en vez
  de `Windows`/`win32ctypes`.
- Mismo mapa de datas (QML, fuentes, locales, migraciones, PNGs, vlc_libs)
  y mismo glob de la extensión Rust (`.pyd` + `.so`).

**VLC: doble capa (launcher + in-process).** Investigación con python-vlc
3.0.21203: `find_lib()` se ejecuta a nivel de `import vlc` y en Linux usa
`find_library("vlc")` (caché ldconfig, ignora el bundle) con fallback a
`ctypes.CDLL("libvlc.so.5")`. Solo `PYTHON_VLC_LIB_PATH` fija el fichero de
forma determinista, y debe estar definido ANTES del primer `import vlc`
(el import en `audio/player.py` ya es lazy, y `main.py`/smoke llaman a
`setup_vlc_env()` primero — orden seguro verificado por grep).
- `doremi.sh` pre-exporta `LD_LIBRARY_PATH` (prepend, sin sobrescribir),
  `PYTHON_VLC_LIB_PATH` (solo si ausente) y `VLC_PLUGIN_PATH` (solo si
  ausente) antes del exec. Garantiza la carga incluso si el proceso Python
  no llegara a configurar el entorno.
- `utils/vlc_check.py::setup_vlc_env()` ahora también fija
  `PYTHON_VLC_LIB_PATH` al `libvlc.so.5`/`.so` del bundle en Linux (antes
  solo `LD_LIBRARY_PATH`; en Windows el comportamiento es idéntico al
  verificado). Respeta valores preexistentes (los del launcher).
- Deliberadamente NO se empaquetan glibc, drivers GPU ni librerías del host:
  esas siempre las pone el sistema.

**Baseline de compatibilidad: Ubuntu 22.04 (glibc 2.35).** El build local de
prueba se hizo en CachyOS (glibc 2.44) por falta de runtime de contenedores
en la máquina de desarrollo; ese binario NO es el artifact de distribución.
El artifact oficial lo construye CI sobre `ubuntu-22.04` (ver §5 y workflow).

## 3. Problemas encontrados y causa raíz

1. **`find_library()` ignora el bundle (VLC).** Sin `PYTHON_VLC_LIB_PATH`,
   un host con VLC podría sombrear la lib incluida. Causa: semántica de
   `ctypes.util.find_library` (ldconfig), no un bug nuestro. Fix: pin
   determinista en launcher + `setup_vlc_env` (probado: `vlc.dll._name`
   apunta al bundle aun con VLC del sistema presente).
2. **`.gitignore` vetaba el nuevo spec.** `*.spec` con excepción solo para
   `doremi.spec` dejaba `doremi-linux.spec` sin versionar. Fix: añadir
   `!doremi-linux.spec` (test de regresión incluido).
3. **Tests que parcheaban una property sin setter.** `AppDirs.vlc_dir` es
   property de solo lectura sobre un singleton; `monkeypatch.setattr` sobre
   la instancia falla. Fix: parcheo a nivel de clase con `property(...)`.
4. **Aserción demasiado estricta sobre `.ico`.** El docstring del spec nombra
   `icon.ico` por contraste; el test y el check de CI ahora solo rechazan
   las formas de código entrecomilladas (`"assets/icon.ico"`).
5. **`LD_LIBRARY_PATH` fijado desde Python puede no bastar.** `dlopen()` sí
   lo consulta, pero la selección de `python-vlc` ocurre vía `find_library`
   (que no). Por eso el launcher previo al exec es la capa robusta y el
   binario directo la conveniente; CI prueba ambas.

## 4. Archivos modificados/creados

- `doremi-linux.spec` (nuevo) · `.gitignore` (+1 línea) ·
  `src/doremi/utils/vlc_check.py` (+11 líneas, rama Linux de `setup_vlc_env`) ·
  `packaging/linux/doremi.sh` + `README-Portable.md` + `THIRD-PARTY-NOTICES.txt`
  (nuevos) · `tests/test_linux_packaging.py` (nuevo, 9 tests) ·
  `.github/workflows/linux-portable.yml` (nuevo). `doremi.spec`,
  `build.yml` y el packaging Windows quedan intactos.

## 5. Versiones y herramientas

- Oficial (CI run 38329666926, verificado): Ubuntu 22.04 x86_64, glibc 2.35
  (`ldd (Ubuntu GLIBC 2.35-0ubuntu3.15)`), Python 3.12.15, Rust estable
  1.99.0, maturin 1.15.0 `--locked`, PyInstaller 6.22.3, VLC Ubuntu
  3.0.16-1build7 (`libvlc5` + `libvlccore9` + `vlc-plugin-base`), registradas
  por build en `BUILD-MANIFEST.txt` + `pip-freeze.txt` del artifact.
- Local (prueba de concepto): CachyOS rolling, glibc 2.44, Python 3.12.14
  (uv), rustc 1.99.0, maturin 1.15.0, PyInstaller 6.22.3, PySide6 6.12.0,
  VLC sistema 3.0.24 (libvlc 3.0.24-1). Wheel resultante
  `manylinux_2_34_x86_64`.

## 6. Riesgos y límites conocidos

- El smoke valida arranque hasta shell QML con controladores a null, no
  sesión completa con red/login ni reproducción audible (igual que F0B-2A).
- Tamaño local 926 MB / 4077 ficheros (Qt + plugins VLC completos + deps
  web/ML). Sin dieta antes de demostrar funcionamiento.
- Licencias: se distribuye `THIRD-PARTY-NOTICES.txt`, pero la release
  pública sigue BLOCKED hasta cerrar source-offers y textos completos
  (VLC §1, Qt §2 — auditoría Linux independiente de la Windows —, paquetes
  §3, Rust §4, Material Symbols §5).
- Sin firma ni sandbox; uso interno de pruebas.
