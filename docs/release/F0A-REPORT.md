# F0A — Informe de estabilización inicial (REPORT)

**Fecha:** 2026-10-11 · **Rama:** `fix/f0a-ci-baseline` · **Base:** `main @ ea75ca5`
**Alcance:** línea base confiable + corrección del workflow nativo Rust.
No incluye empaquetado completo ni nuevas características (corresponden a F0B).

## 1. Inspección del repositorio

- Rama de trabajo: `main`, con HEAD en `ea75ca5` y **7 commits locales por delante de
  `origin/main`** más modificaciones sin commitear en el árbol. Todo se conservó:
  no se usó `git reset --hard`, `git clean` ni `stash`. Para no tocar `main` se creó
  la rama `fix/f0a-ci-baseline` sobre el estado existente.
- Cómo se compila el módulo Rust: `cd src/doremi/native_rs && maturin develop --locked`
  (perfil `debug` en desarrollo; `./script-release.sh --build-only` para `release`).
  El crate usa PyO3 con `abi3-py312`, luego el wheel sirve para Python 3.12+.
- Cómo se ejecuta la suite: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/ -q`.
- Arranque: `src/doremi/native_rs/__init__.py` exige el módulo compilado **antes** de
  importar Qt; si falta o está desactualizado, la app aborta con `ImportError`.

## 2. Hallazgos históricos ya corregidos vs defectos reproducibles

**Histórico (ya corregido, no reabrir):** `AUDIT_POLISH.md` documenta BUG-001…BUG-050
resueltos con regresiones asociadas; la última pasada integrada citada es
**385 passed**. La suite actual en este árbol da **523 passed** (ver F0A-RESULTS.md),
coherente con trabajo posterior del usuario (7 commits + tests nuevos). Nada de esto
requiere acción en F0A.

**Defectos reproducibles ( Alcance F0A / diagnóstico F0B):**

1. **CI nativo en rojo (F0A, corregido aquí):** el job `Build native_rs + parity tests`
   de `.github/workflows/native.yml` fallaba con 16 passed + 1 failed porque
   `PySide6.QtGui` no podía cargar `libEGL.so.1` en el runner `ubuntu-latest`.
   Es un error de entorno, no del módulo nativo. Ver §3.
2. **Sistema de releases no viable (F0B, solo diagnosticado):** ver §4. No se tocó
   `build.yml` ni `packaging/` en esta fase.

## 3. Causa raíz del fallo de CI y corrección aplicada

- **Cadena del fallo:** `tests/test_native_rs.py::TestComputeColorVariants::test_matches_qcolor`
  hace `import PySide6.QtGui` para contrastar contra `QColor`. QtGui enlaza dinámicamente
  contra `libEGL.so.1`/`libGL`. La imagen `ubuntu-latest` no trae esas bibliotecas de
  usuario, así que la importación aborta y el test falla aunque el código Rust sea correcto.
- **Evidencia local de que es entorno:** en este equipo (CachyOS/Arch, mesa instalado,
  `/usr/lib/libEGL.so.1` presente) el mismo test pasa; `QT_QPA_PLATFORM=offscreen` solo
  evita necesitar servidor gráfico, no sustituye a las librerías GL.
- **Corrección (único cambio de CI en F0A):** nuevo paso `Install Qt system libraries`
  en `.github/workflows/native.yml` antes de `Run parity tests`:
  `libegl1 libgl1 libopengl0 libxkbcommon0 libdbus-1-3` vía apt. Cubre `libEGL.so.1`
  y las dependencias habituales de QtGui/QtDbus en runners Ubuntu 24.04/26.04.
- **Lo que NO se hizo:** no se deshabilitó ni marcó `xfail` ninguna prueba; el test
  QColor sigue siendo obligatorio.

## 4. Diagnóstico del sistema de releases (para F0B, priorizado, sin implementar)

**P0 — rompen el pipeline hoy:**

- **P0.1** `packaging/rpm/doremi.spec` no existe, pero `build-rpm` y `build-opensuse`
  hacen `sed` y `rpmbuild` sobre él → ambos jobs fallan siempre.
- **P0.2** `doremi.spec` (PyInstaller) no existe, pero `build-windows` ejecuta
  `pyinstaller doremi.spec` → el job falla siempre. Agravante: `.gitignore` tiene la
  regla `*.spec`, así que cuando se cree habrá que añadir excepción o `git add -f`.
- **P0.3** `RELEASE_NOTES.md` no existe, pero el job `release` lo usa como
  `body_path` en `softprops/action-gh-release` → la publicación falla o sale vacía.
- **P0.4** `doremi-launcher.sh` no existe, pero el manifiesto Flatpak lo instala en
  `/app/bin/doremi` → el módulo `doremi` de Flatpak falla.
- **P0.5** El `sed` de estampado de versión sobre `src/doremi/__init__.py`
  (`s/__version__ = ".*"/…/`) **nunca coincide**: el archivo define
  `__version__ = _resolve_version()` (dinámico vía `git describe` o metadatos del dist).
  Es un no-op silencioso en los 5 jobs de build (el de `pyproject.toml` sí aplica).

**P1 — generan paquetes rotos aunque el job termine en verde:**

- **P1.1** Ningún job Linux/Windows compila el módulo Rust (sin toolchain Rust ni
  maturin en `build-arch/deb/rpm/opensuse/windows`, ni en el yml de Flatpak).
  La app **exige** `native_rs` al arrancar, luego todos esos artefactos fallarían en
  ejecución con `ImportError`.
- **P1.2** `PKGBUILD`: el tarball de GitHub descomprime como `Doremi-Rust-$pkgver`,
  pero `build()` hace `cd "Doremi-$pkgver"` → `makepkg` falla. Además la `url` apunta
  a `github.com/Eirom16/doremi` (nombre de repo incorrecto; es `Doremi-Rust`).
- **P1.3** Dependencias obsoletas tras la auditoría: `PKGBUILD` (`optdepends`
  `python-pypresence`, `python-pylast`), `postinst`/`postrm` de deb y el manifiesto
  Flatpak siguen instalando `pylast`/`pypresence`, retirados del producto cuando se
  eliminaron Last.fm/Discord (AUDIT_POLISH.md). El `pkgdesc` también anuncia
  "Discord RPC".
- **P1.4** `PKGBUILD` declara `depends=('python>=3.12')` sin cota superior, pero
  `pyproject.toml` exige `<3.14` → en Arch rolling, Python 3.14 rompería la instalación.
- **P1.5** `control` de deb: `Depends` usa `libvlc5` (en Ubuntu 24.04+ es `libvlc5t64`)
  y relega `python3-pyside6` a `Recommends` aunque es dependencia dura; el resto de
  dependencias Python se instalan vía `pip` en `postinst` (frágil sin red, bypass PEP 668).
- **P1.6** Recursos Windows: sin `.spec` no hay constancia de qué `datas` (42 QML,
  `assets/`, fuentes, `qmldir`) entrarían en el bundle; `installer.iss` asume
  `SourceDir=..\..` y `assets\icon.ico` (existe `assets/icon.ico`, verificado).

**P2 — higiene y seguridad:**

- **P2.1** `postrm` del deb, en `purge`, ejecuta `pip3 uninstall -y …` sobre paquetes
  del sistema que pueden pertenecer a otras aplicaciones o al usuario, con una lista
  parcial (no desinstala todo lo que `postinst` instaló). Riesgo de dañar el sistema.
- **P2.2** **405 ficheros de `src/doremi/native_rs/target/` están versionados en Git**
  aunque `.gitignore` los excluye (se commitearon antes de la regla). Inflan el repo y
  los diffs; conviene `git rm --cached` en F0B.
- **P2.3** `release` usa `retention-days: 1` y `fail_on_unmatched_files: false`: si un
  job de build falla, la release se publica igualmente con artefactos parciales sin error.
- **P2.4** Flatpak `pip3 install … pylast pypresence` + sin Rust: doble causa de
  artefacto no funcional (P1.1 + P1.3). Revisar también `runtime-version: '6.7'`
  frente a los runtimes KDE disponibles en build.

## 5. Alcance y modificaciones de F0A (esta rama)

| Archivo | Cambio |
|---|---|
| `.github/workflows/native.yml` | Nuevo paso `Install Qt system libraries` (apt: `libegl1 libgl1 libopengl0 libxkbcommon0 libdbus-1-3`) antes de los parity tests |
| `.gitignore` | Excepción `!docs/release/*.md` para que los informes F0A sean versionables pese a la regla `*.md` |
| `docs/release/F0A-REPORT.md` | Este informe |
| `docs/release/F0A-RESULTS.md` | Comandos, resultados y versiones |

No se modificó `main` directamente, no se crearon tags ni releases, no se tocó
`build.yml`/`packaging/`, y no se añadieron dependencias. Solo se commitean los 4
archivos anteriores; el resto de modificaciones del árbol pertenecen al usuario y se
dejan intactas en el working tree. Nota: el commit de `.gitignore` arrastra dos
hunks previos del usuario ya presentes en el árbol (`!docs/PLAN_REFERENCIAS_VISUALES.md`
y las exclusiones de `src/doremi/native_rs/target/` + `*.pyd`), necesarios para
coherencia; no se alteró ni descartó ningún cambio suyo.

## 6. Riesgos

- El número exacto de paquetes apt puede variar si `ubuntu-latest` migra de 24.04 a
  26.04 (aviso ya presente en el runner); los 5 elegidos existen en ambas.
- El intérprete local es Python 3.13.9 y el sistema trae 3.14 (fuera del rango
  soportado `>=3.12,<3.14`); la conformidad con **3.12 queda pendiente de la propia
  ejecución del CI** (no hay intérprete 3.12 en este equipo).
- El venv local carece del módulo `pip` (`.venv/bin/python -m pip` falla), aunque
  `maturin`/`pytest` funcionan como binarios; reinstalar pip queda fuera de F0A pero
  conviene revisarlo en F0B porque `script.sh` documenta instalar con pip.
- Los 7 commits locales sobre `origin/main` + cambios sin commitear no forman parte
  de este PR; si el PR se abre contra `origin/main`, el diff incluirá solo F0A al
  estar la rama basada en el `main` local (revisar en el push).

## 7. Próximos pasos (F0B, no iniciados)

1. Recrear `packaging/rpm/doremi.spec`, `doremi.spec` (PyInstaller, con QML/assets y
   `native_rs`), `RELEASE_NOTES.md` y `doremi-launcher.sh` (+ excepción de `*.spec`).
2. Compilar e incluir el módulo Rust en los 5 jobs de build + Flatpak.
3. Corregir `PKGBUILD` (directorio del tarball, url, cota Python, deps post-auditoría).
4. Endurecer deb (`libvlc5t64`, PySide6 como dependencia dura, revisar pip en
   postinst/postrm) y eliminar `pip uninstall` sistémico del `postrm`.
5. Arreglar el estampado de versión (`_resolve_version()` dinámico) o eliminarlo.
6. `git rm --cached` de `native_rs/target/` y revisar `retention-days` /
   `fail_on_unmatched_files` del job `release`.
