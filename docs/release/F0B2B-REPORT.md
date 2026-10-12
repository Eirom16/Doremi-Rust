# F0B-2B — Windows installer (REPORT)

**Fecha:** 2026-10-12/13 · **Rama:** `build/f0b2b-windows-installer`
**Base:** `build/f0b2a-windows-portable @ 1b61f4d` (PR #5 abierto sin fusionar)
**PR:** https://github.com/Eirom16/Doremi-Rust/pull/6 (contra `build/f0b2a-windows-portable`, sin fusionar)
**CI RUN:** https://github.com/Eirom16/Doremi-Rust/actions/runs/38321966425 (`success`;
duplicado PR https://github.com/Eirom16/Doremi-Rust/actions/runs/38321970781 también `success`)
**HEAD:** `52ddc36` (`52ddc36df979a015ecdf0a71f8f4b7cbdc0dc2e4`)
**Objetivo:** instalador Windows x64 (`Doremi-v2.1.4-Setup.exe`) con Inno Setup,
per-user sin elevación, install/reinstall/upgrade/uninstall sin pérdida de
datos personales. Sin GitHub Releases. Sin firma (SmartScreen documentado).

## 1. Auditoría de `installer.iss` (cambios)

Base: `packaging/windows/installer.iss @ 1b61f4d` (sin AppId, con placeholders,
URLs al repo inexistente `Eirom16/doremi`, `ArchitecturesInstallIn64BitMode=x64`
obsoleto, accesos duplicados, y `[UninstallDelete] {localappdata}\Doremi`).

| # | Defecto | Fix |
|---|---|---|
| 1 | Sin `AppId` (cada build = producto distinto, upgrades imposibles) | `AppId={{b2285fdf-22de-411a-93b2-4ce4d8a5fa8a}}`, estable y documentado en cabecera. Historial: `git log -- packaging/windows/installer.iss` muestra un único commit (Initial) sin AppId previo → no hay identidad legacy que preservar; esta es la primera y queda congelada. Evidencia CI: la misma clave HKCU `...\Uninstall\{b2285fdf-…}_is1` en A, B y C. |
| 2 | URLs `https://github.com/Eirom16/doremi*` (404; el repo real es `Eirom16/Doremi-Rust`, ya corregido en `utils/updater.py` en F0B-2A) | Publisher/Support/Updates → `Eirom16/Doremi-Rust`. Verificado por `stamp_installer_version.py --check` (falla si aparece `github.com/Eirom16/doremi`). |
| 3 | `AppVersion`/`OutputBaseFilename` = `VERSION_PLACEHOLDER` | Estampado `2.1.4` / `Doremi-v2.1.4-Setup` desde `pyproject.toml` vía `packaging/windows/stamp_installer_version.py` (CI lo ejecuta y verifica; idempotente, auto-repara una línea `AppVerName` mutilada y rechaza claves `[Setup]` duplicadas o sin `=`). |
| 4 | `ArchitecturesInstallIn64BitMode=x64` (obsoleto desde Inno 6.3: el compilador avisa y sustituye por `x64os`, que NO cubre ARM64 Win11) | `ArchitecturesAllowed=x64compatible` + `ArchitecturesInstallIn64BitMode=x64compatible` (docs JRSoftware: arch identifiers / 64-bit installs / 6.3 whatsnew). CI instala Inno Setup **6.7.1** (`Compiler engine version: Inno Setup 6.7.1` en el log) sin warnings de arquitectura. |
| 5 | Accesos duplicados: `{group}\Doremi` + `{userstartmenu}\Doremi` | Eliminados `{userstartmenu}` y la tarea `startmenuicon`; quedan `{group}\Doremi`, `{group}\Desinstalar Doremi` y `{autodesktop}` opcional (`desktopicon`, unchecked). El test falla si reaparece el `.lnk` duplicado — verificado ausente en CI. |
| 6 | `[UninstallDelete] {localappdata}\Doremi` → borra datos personales | SECCIÓN ELIMINADA. El desinstalador solo retira `{app}`. Además `AppDirs` ni siquiera usa `%LOCALAPPDATA%` (usa `~/.config|~/.local/share|~/.cache/doremi` con overrides XDG, ver `src/doremi/config/paths.py`), así que la regla antigua ni cubría las rutas reales y sí amenazaba una ruta legacy. Lint + 6 centinelas lo blindan (todos intactos tras D). |
| 7 | Sin metadatos de desinstalación | `UninstallDisplayIcon={app}\Doremi.exe`, `AppVerName`, `VersionInfoVersion=2.1.4.0`. CI muestra `DisplayName='Doremi' DisplayVersion='2.1.4'`. |
| 8 | Sin manejo de ficheros bloqueados en upgrade | `CloseApplications=yes` + `RestartApplications=yes`. |
| 9 | Sin garantías per-user explícitas | `PrivilegesRequired=lowest` + `DefaultDirName={autopf}\Doremi` + `PrivilegesRequiredOverridesAllowed=dialog`. Evidencia: clave de desinstalación bajo **HKCU** (nunca HKLM) y test que falla si aparece fuera de HKCU. |
| 10 | Rutas relativas frágiles (fallo real en CI: `SetupIconFile` no encontrado con `SourceDir=..\..` según el CWD) | Todas las rutas del repo absolutas vía ISPP `#define RepoRoot SourcePath + "\\..\\.."` (`LicenseFile`/`SetupIconFile`/`OutputDir`/`[Files]`). Compila desde cualquier CWD. El lint exige el `#define`. |
| 11 | Cumplimiento mínimo en el bundle instalado | `[Files]` añade `LICENSE→{app}\LICENSE.txt` y `THIRD-PARTY-NOTICES.txt→{app}` junto a `dist\Doremi\*` + `icon.ico`. Compresión `lzma2/max`. |

## 2. Protección de datos (diseño + evidencia)

- Rutas reales (`config/paths.py`): `config=XDG_CONFIG_HOME|~/.config/doremi`
  (`settings.toml`), `data=XDG_DATA_HOME|~/.local/share/doremi` (`doremi.db`,
  `downloads/`, `logs/`, `vlc/`), `cache=XDG_CACHE_HOME|~/.cache/doremi`
  (`artwork/`, `lyrics/`). En Windows `~` = `%USERPROFILE%`.
- `test_installer.ps1` planta 6 centinelas con contenido+SHA-256 conocidos y
  exige checksums idénticos tras A/B/C/D. Resultado CI: `sentinels preserved
  (6 files)` en A, B, C y D, incluyendo el legacy
  `%LOCALAPPDATA%\Doremi\sentinel-legacy.txt` (hash `04850D…` intacto).
- La limpieza del test borra solo ficheros explícitos — jamás
  `Remove-Item -Recurse` sobre rutas de usuario.
- `run_smoke_test` aísla XDG en tempdirs: ni el smoke del portable ni el de la
  app instalada tocan la DB real (los smokes instalados corren con
  `meipass=D:\a\_temp\Doremi-Test\Doremi\_internal`).

## 3. Bundle reutilizado (mismo SHA y BUILD_ID)

El workflow reconstruye el bundle en la MISMA ejecución (maturin `--locked`,
`vlc_libs` desde Chocolatey, stamp `BUILD_ID=f0b2b.windows.52ddc36df979`,
`pyinstaller doremi.spec`), le pasa el smoke de `dist\` y LUEGO compila el
instalador sobre `dist\Doremi\*`. Instalador y bundle corresponden al mismo
commit por construcción; ningún artifact antiguo. Evidencia: los tres smokes
(dist, instalado A, instalado B) informan `build: f0b2b.windows.52ddc36df979`.

## 4. Pipeline (`.github/workflows/windows-installer.yml`) — 23/23 pasos verdes

Build bundle → checks `_internal` → smoke dist (`Start-Process -Wait`, exit 0,
`ok==true` 9/9) → `choco install innosetup` (6.7.1) → stamp+lint →
`ISCC packaging\windows\installer.iss` → verificación
`Doremi-v2.1.4-Setup.exe` + `pip freeze` → `test_installer.ps1` (A/B/C/D) →
SHA-256 → artifact temporal (14 días). Sin tags ni Releases.

Fallos intermedios documentados (runs `38317337784`, `38318176747`,
`38318932819`, `38319844988`, `38320798370`): (a) `vlc.exe --version` bloquea
headless → versión leída de `libvlc.dll`; (b) el stamper mutilaba `AppVerName`
→ corregido + auto-reparación + lint de duplicados; (c) `SourceDir` relativo
depende del CWD → rutas absolutas ISPP; (d) la clave HKCU debe buscarse sin
asumir vista → búsqueda en vistas x64+WOW6432Node con assert de estabilidad
(resultó estar en la vista nativa por el modo 64-bit).

## 5. Licencias (resumen; detalle en `packaging/windows/THIRD-PARTY-NOTICES.txt`)

Versiones concretas distribuidas (CI `installer-manifest.txt` + `pip freeze`):
VLC **3.0.24** (libvlc `3,0,24,0`), PySide6 **6.12.0** (Qt 6), Python **3.12.10**,
rustc **1.99.0**, maturin **1.15.0**, PyInstaller **6.22.3**,
python-vlc **3.0.21203**, yt-dlp **2026.8.19**, ytmusicapi **1.12.3**,
SQLAlchemy **2.1.4**, keyring **25.7.0**, pyo3 **0.23.5** + resto en
`Cargo.lock`. Fuentes Inter/JetBrains Mono OFL incluidas ✓.

- libVLC/libvlccore LGPL-2.1+ (VideoLAN), plugins mixtos GPL — oferta de
  fuentes pendiente → **release público BLOQUEADO**.
- Qt6/PySide6 LGPL-3.0/GPL — textos + source offer pendientes → BLOQUEADO.
- Python deps — textos por versión pendientes → BLOQUEADO.
- Rust crates MIT/Apache-2.0 — NOTICE pendiente → BLOQUEADO.
- Material Symbols Apache-2.0 sin texto vendored → BLOQUEADO.
- Instalador incluye `{app}\LICENSE.txt` + `{app}\THIRD-PARTY-NOTICES.txt`.
- Sin firma de código: SmartScreen avisará; firma = tarea pre-release.

## 6. Evidencia CI (run 38321966425, `success`)

- INSTALL A: exit 0, `Doremi.exe` 19,1 MB, shortcut
  `...\Start Menu\Programs\Doremi\Doremi.lnk`, sin duplicado, AppId HKCU nativo.
- Smoke INSTALADO (A y B): `DOREMI_SMOKE_OK`, `ok==true`, exit 0, 9/9 checks,
  VLC+Rust desde `Doremi\_internal` (`.pyd` + `vlc_libs\libvlc.dll` presentes).
- REINSTALL B: exit 0, AppId idéntico (`..._is1` misma ruta), datos intactos.
- UPGRADE C (simulado, mismo AppId + `UsePreviousAppDir`): exit 0, AppId
  idéntico, datos intactos. Cross-version NO verificado (no existe 2ª versión).
- UNINSTALL D: exit 0, `InstallDir` eliminado, `.lnk` retirado, 6/6 centinelas.
- Artifact: `Doremi-v2.1.4-Setup.exe` **214,4 MB**,
  SHA-256 `431EF5932C3AE26F4386F44C405A2F79246B3CF18B99A907B8935A4E2D1BE756`
  (verificado por descarga y `sha256sum` local).
- Tests nativos en runner: **17 passed**. Sin elevación en ningún paso.

## 7. Limitaciones y pendientes

- Upgrade entre versiones DISTINTAS no verificado (declarado simulado).
- Audio E2E no verificado (VLC instancia OK; sin assert audible).
- Cierre legal completo pendiente → release público BLOQUEADO.
- Firma de código pendiente (SmartScreen esperado).
- Bundle pesado heredado de F0B-2A (instalador 214 MB por `lzma2/max`).
