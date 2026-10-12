# F0B-2A — Windows portable build (REPORT)

**Fecha:** 2026-10-12 · **Rama:** `build/f0b2a-windows-portable`
**Base:** `build/f0b1-native-foundation @ 29cf4ea` (PR #4 abierto sin fusionar)
**Objetivo:** Doremi completo para Windows x64 como ZIP portable (PyInstaller
onedir). Sin Inno Setup, sin Releases.

## 1. Arquitectura del bundle

```text
Doremi-Windows-x64-Portable.zip
└── portable/
    ├── Doremi/                      onedir PyInstaller 6 (exe + _internal)
    │   ├── Doremi.exe               19,1 MB, windowed, icono assets/icon.ico
    │   └── _internal/               == sys._MEIPASS en este layout
    │       ├── doremi/ui/qml/**     32 QML + Doremi/qmldir (qmldir preservado)
    │       ├── doremi/assets/fonts/ Inter/JetBrainsMono/MaterialSymbols
    │       ├── doremi/locales/      es.json, en.json
    │       ├── doremi/db/migrations/ env.py + versions/*.py (fuentes: alembic
    │       │                        las carga por ruta en runtime)
    │       ├── doremi/native_rs/    puente + native_rs.pyd (548 KB) al lado
    │       ├── native_rs/           paquete del wheel (colección automática)
    │       ├── assets/              Doremi.png + fondo + icon.ico (AppDirs.root)
    │       ├── vlc_libs/            libvlc.dll + libvlccore.dll + plugins/**
    │       └── resto               Qt6, Python 3.12 embebido, site-packages
    ├── MANIFEST.txt                 3730 ficheros con tamaños
    └── SHA256SUMS.txt               checksums SHA-256
```

`doremi.spec` (raíz del repo): Analysis sobre `src/doremi/main.py`, datas según el
mapa anterior, `collect_data_files(qt_material|ytmusicapi)`,
`collect_submodules(yt_dlp.extractor|postprocessor)`, hiddenimports
(`vlc`, `aiosqlite`+dialecto, `alembic`, `mako`, `h2`/`httpcore`, `keyring`
Windows, `logging.config/handlers`, …), `excludes=[tkinter]`.

Cambios de código frozen (todos condicionados a `sys.frozen`, sin efecto en dev):
- `ui/qml_paths.py` + 15 presenters: QML en `_MEIPASS/doremi/ui/qml`.
- `config/paths.py::bundle_package_dir()`: icons, locales i18n y migraciones
  alembic resuelven bajo `_MEIPASS/doremi/…`.
- `__init__.py`: prefiere `doremi._build_version` (estampado por CI en
  `src/doremi/_build_version.py`, gitignored) antes que `git describe`/metadatos.
  El portable informa `2.1.4` + `BUILD_ID=f0b2a.windows.<sha>` (sin hash git
  como versión pública).
- `updater.py`: API de releases → `Eirom16/Doremi-Rust` (repo correcto para
  futuras actualizaciones; antes apuntaba a `Eirom16/doremi` → 404 silencioso).
- `main.py --smoke-test`: init no interactivo (Qt offscreen, XDG a tempdirs
  aislados, Rust, `vlc.Instance` real, `AppDirs.setup`, alembic a head, fuentes,
  theme bridge, carga de `MainShell.qml` en `QQuickWidget`) con marcador
  `DOREMI_SMOKE_OK`, `smoke-result.json` (ruta vía `DOREMI_SMOKE_OUT`) y exit
  code real. Un proceso que solo sigue vivo hasta un timeout no valida nada;
  este smoke debe imprimir el marcador Y salir 0 por sí solo.

## 2. Problemas encontrados y causa raíz

1. **Layout `_internal` de PyInstaller 6 (checks del workflow).** Las datas van a
   `dist/Doremi/_internal` (== `sys._MEIPASS`), no junto al exe. Causa: asumir el
   layout pre-v6. El código ya era correcto; solo fallaban las rutas de
   verificación. Evidencia empírica: `meipass: …/dist/Doremi/_internal` en el smoke.
2. **`logging.config` ausente en el bundle.** La cadena alembic/SQLAlchemy lo
   necesita vía acceso por atributo (invisible a modulegraph). Añadido a
   hiddenimports (+`logging.handlers` defensivo). El smoke ahora incluye traceback.
3. **El operador `&` de PowerShell no espera a exes GUI.** Los checks del smoke
   competían con la app (fichero "ausente" con la app imprimiendo OK 2 s después).
   Causa raíz real del "file not written". Fix: `Start-Process -Wait -PassThru`
   + exit code del handle. Además el reporte usa ruta absoluta (`DOREMI_SMOKE_OUT`).
4. **`DATABASE_URL` ligado a import time.** El smoke reata la URL tras aislar XDG
   para no tocar jamás la DB real del usuario (detectado en validación local:
   el smoke tocó `~/.local/share/doremi/doremi.db` antes del fix; tras él, intacta).
5. **`python -m venv` roto con el python3.13 local (uv sin ensurepip)** y **`/tmp`
   lleno**: venv vía `uv`, worktree en `/home/eirom/Doremi-F0B2A`. Solo entorno.

## 3. VLC en Windows (revisión)

- Origen: `choco install vlc` en CI; se empaquetan `libvlc.dll`,
  `libvlccore.dll` y el árbol `plugins/` completo en `vlc_libs/`.
- Validación real (no solo existencia del DLL): `setup_vlc_env()` + `vlc.Instance()`
  dentro del exe congelado → `VLC detected successfully` (log del run).
- Sin dependencia de VLC externo: el orden de `vlc_check.py` prioriza el bundle.
- Licencias: los binarios VLC son copyleft (VideoLAN). El ZIP distribuye binarios
  sin fichero de avisos dedicado — **pendiente**: añadir `THIRD-PARTY-NOTICES`
  (VLC + resto) antes de cualquier release pública. No bloquea el portable de
  pruebas; queda registrado como riesgo.

## 4. Archivos modificados

23 ficheros de código frozen + `qml_paths.py` (nuevo) · `doremi.spec` (nuevo, con
`!doremi.spec` en `.gitignore` + ignore de `_build_version.py`) ·
`.github/workflows/windows-portable.yml` (nuevo) · estos dos informes.
`build.yml` e `installer.iss` intactos (el futuro instalador reutiliza
`dist\Doremi\*` tal cual).

## 5. Versiones y herramientas

CI: Python 3.12.10, Rust estable 1.99.0, maturin 1.15.0, PyInstaller (pip, serie 6),
VLC de Chocolatey (estable), pytest + PySide6 (pip). Local: Python 3.13.9 (uv),
maturin 1.15.0, rustc 1.99.0, PySide6 6.12.0, pytest 9.1.1.

## 6. Riesgos y límites conocidos

- El smoke valida arranque hasta shell QML con controladores a null (las props de
  `MainShell.qml` lo toleran por diseño `&&`), no una sesión completa con red,
  login ni reproducción audible: VLC instancia OK, pero no se reproduce audio en
  CI. Suficientemente representativo para portable; la E2E con audio queda fuera.
- Bundle 786 MB / ZIP 328 MB (Qt + VLC plugins completos + ML-web deps). Sin
  límite impuesto; dieta (excludes, plugins VLC) pendiente de fase de release.
- `pystray` sigue en dependencias sin import en `src` (no entra al bundle;
  limpieza pendiente, no afecta).
- `DOREMI_ASSETS` continúa sin leerse en `src` (resto muerto de empaquetado
  Linux; no afecta a Windows).
