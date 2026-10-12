# F0B-2B — Resultados de validación (RESULTS)

**Fecha:** 2026-10-13 · **Rama:** `build/f0b2b-windows-installer`
**Base:** `build/f0b2a-windows-portable @ 1b61f4d`
**PR:** https://github.com/Eirom16/Doremi-Rust/pull/6 (base `build/f0b2a-windows-portable`, sin fusionar)
**HEAD:** `52ddc36` (`52ddc36df979a015ecdf0a71f8f4b7cbdc0dc2e4`)

## 1. Validación local (worktree `/home/eirom/Doremi-F0B2B`, sin tocar el árbol del usuario)

```bash
python3 packaging/windows/stamp_installer_version.py --check
# OK: installer.iss stamped for 2.1.4 (Doremi-v2.1.4-Setup.exe)
grep -n "^\[" packaging/windows/installer.iss
# [Setup] [Languages] [Tasks] [Files] [Icons] [Run]  (sin [UninstallDelete])
sha256sum Doremi-v2.1.4-Setup.exe   # descargado del artifact
# 431ef5932c3ae26f4386f44c405a2f79246b3cf18b99a907b8935a4e2d1be756  == CI
```

(Sin Inno Setup ni runner Windows en local; compilación e instalación reales
solo en CI Windows.)

## 2. CI — run 38321966425 (`success`) + duplicado PR 38321970781 (`success`)

https://github.com/Eirom16/Doremi-Rust/actions/runs/38321966425
(Runs previos con fallos intermedios documentados en REPORT §4.)

| Paso | Resultado |
|---|---|
| VLC 3.0.24 (choco) + libvlc `3,0,24,0` + Python 3.12.10 + rustc 1.99.0 + maturin 1.15.0 | OK |
| Wheel release (`maturin build --release --locked`) + tests nativos | **17 passed** (0.23 s) |
| Stamp `BUILD_VERSION=2.1.4` + `BUILD_ID=f0b2b.windows.52ddc36df979` | OK |
| PyInstaller 6.22.3 `doremi.spec` + checks `_internal` (QML, fuentes, migraciones, VLC, `.pyd`) | OK |
| Smoke `dist\Doremi.exe` (`Start-Process -Wait`, XDG aislados, offscreen) | `DOREMI_SMOKE_OK` 9/9, exit 0, `ok==true` |
| Inno Setup 6.7.1 (`x64compatible` aceptado, sin warnings) | OK |
| Stamp+lint `installer.iss` (versión, repo, sin `UninstallDelete`, ISPP `RepoRoot`) | OK |
| `ISCC packaging\windows\installer.iss` → `Doremi-v2.1.4-Setup.exe` (214,4 MB) | OK |
| A. Instalación silenciosa (exit 0, `Doremi.exe` 19,1 MB, shortcut, AppId HKCU nativo `...{b2285fdf-…}_is1`, `DisplayVersion='2.1.4'`) | pass |
| Smoke desde INSTALACIÓN A (`meipass=…\Doremi-Test\Doremi\_internal`, VLC+Rust del bundle) | `ok==true`, exit 0 |
| B. Reinstalación (exit 0, AppId idéntico, 6/6 centinelas) + smoke instalado | pass |
| C. Upgrade simulado mismo AppId (exit 0, AppId idéntico, 6/6 centinelas) | pass (cross-version NO verificado) |
| D. Desinstalación (exit 0, `InstallDir` eliminado, `.lnk` retirado, 6/6 centinelas incl. legacy `%LOCALAPPDATA%\Doremi`) | pass |
| SHA-256 + artifact temporal (14 días) | OK, sin tags ni Releases |

Smoke literal (instalado, escenario A):

```text
DOREMI_SMOKE_OK {"ok": true, "checks": {"qt_app": true, "vlc": true, "app_dirs": true,
"db_migrations": true, "fonts": true, "rust": true, "theme_bridge": true,
"qml_files": true, "qml_shell": true}, "version": "2.1.4", "frozen": true,
"meipass": "D:\\a\\_temp\\Doremi-Test\\Doremi\\_internal",
"build_id": "f0b2b.windows.52ddc36df979", "cwd": "D:\\a\\Doremi-Rust\\Doremi-Rust"}
```

## 3. Tamaños y hash

| Artefacto | Tamaño | SHA-256 |
|---|---|---|
| `Doremi-v2.1.4-Setup.exe` | 214,4 MB | `431EF5932C3AE26F4386F44C405A2F79246B3CF18B99A907B8935A4E2D1BE756` |
| `Doremi.exe` (instalado) | 19,1 MB | (dentro del bundle instalado) |

## 4. Artifact

`Doremi-Windows-x64-Setup` (run → Artifacts, expira en 14 días):
`Doremi-v2.1.4-Setup.exe` + `.sha256` + `doremi-installer-results.json` +
`installer-manifest.txt` + `installer-pip-freeze.txt`. Sin firma: Windows
SmartScreen mostrará advertencia; esperado hasta la firma pre-release.
Uso per-user sin admin:
`Doremi-v2.1.4-Setup.exe /SP- /SILENT` → `%LOCALAPPDATA%\Programs\Doremi`.

## 5. Git

Rama `build/f0b2b-windows-installer` desde `1b61f4d`; commits lógicos pushed
(installer+tests+CI · fix vlc-version · fix stamper · fix CWD · fix ISPP ·
fix registry-views · informes); PR #6 contra `build/f0b2a-windows-portable`
sin fusionar; `git diff --check` limpio; árbol del usuario
(`fix/f0a-ci-baseline`) intacto; sin cambios en paquetes Linux; sin tags
ni Releases.

## 6. No verificado / fuera de alcance

- Upgrade entre versiones DISTINTAS (declarado simulado en C).
- Reproducción audible E2E (VLC instancia OK; sin assert de audio).
- Cierre legal completo (source offers + textos LGPL/GPL + NOTICE Rust +
  texto Apache Material Symbols) → release público BLOQUEADO.
- Firma de código (SmartScreen esperado).
