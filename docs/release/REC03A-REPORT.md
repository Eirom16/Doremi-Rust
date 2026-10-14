# REC-03A — Servicios de metadatos y artwork: informe de recuperación

Fase: REC-03A (recuperación controlada de servicios de producto).
Rama: `recovery/rec03a-metadata-services` sobre `recovery/rec02-data-foundation @ 38c1a1d`.
Worktree: `/home/eirom/Proyectos/Doremi/worktrees/rec03a-metadata-services`.
Rescate (solo lectura): `/home/eirom/Proyectos/Doremi/Doremi-Rust-Rescate @ c00d772`
(`fix/f0a-ci-baseline`, working-tree con 3 ficheros `??` no versionados).
Principal intacto: `/home/eirom/Proyectos/Doremi/Doremi-Rust @ 80aaf1e` (limpio).
PR: `https://github.com/Eirom16/Doremi-Rust/pull/10` apilado sobre
`recovery/rec02-data-foundation` (no sobre `main`), sin fusionar.
Estado: VERIFIED (cierre documental post-CI; código evaluado `48ec621`; ver §5).

## 1. Auditoría y matriz de recuperación

Procedencia aclarada: `artist_credits.py`, `artwork.py`, `local_metadata.py` son
`??` untracked en el rescate (no están en `HEAD c00d772`, `git log --follow`
vacío). No son recuperables por `cherry-pick`; se adaptan al árbol de
distribución. En REC-02 quedaron explícitamente diferidos
(`services/artwork.py`, `services/local_metadata.py`).

| Archivo origen (rescate, untracked) | Funcionalidad | Destino | Adaptación | Tests | Pendiente (motivo) |
|---|---|---|---|---|---|
| `services/artist_credits.py` (35L) | `artist_credits(artists, fallback) -> [{name,id}]`. Prefiere créditos estructurados; solo parte legacy `,;feat/ft`; nunca parte `&`; filtra `unknown/*`; dedup por `(name.casefold(), id)` | `src/doremi/services/artist_credits.py` | Copia exacta (`diff` idéntico). Solo stdlib `re`; sin I/O/red/env | `test_rec03a_*credits*` (10 tests) incl. control 1 | Cableado en viewmodels/controladores/QML `ArtistLinks` → fase posterior (fuera de alcance) |
| `services/artwork.py` (40L) | `resolve_artwork(url, video_id)` + `cover_fields(tracks, explicit)`. Selección sin red usando cachés en disco; `explicit` domina; hasta 4 fuentes distintas en orden | `src/doremi/services/artwork.py` | Copia exacta (`diff` idéntico). Solo `AppDirs.artwork_cache` + `cache/offline/artwork`; `video_id` validado `alnum+_-` | `test_rec03a_*cover*/*resolve*/*offline*` (10 tests) incl. control 2 | Consumidores (`listening_periods`, `home_composer`, `experience/local_library`, 12 viewmodels, `playlist_data`) → fase posterior |
| `services/local_metadata.py` (82L) | `read_metadata(path) -> {title,artist,album,duration_ms,thumbnail_url}` + `_first/_picture`. Lee tags/covers sin modificar el audio; carátula a `artwork_cache/embedded-<sha256>.jpg` atómico; límite 16 MiB antes de decodificar | `src/doremi/services/local_metadata.py` | Comportamiento idéntico; solo docstrings ampliados (contrato síncrono + atomicidad + límite). Sin `asyncio`, sin Qt, sin DB. Imports: `PIL` (ya), `loguru` (ya), `mutagen` (nuevo), `AppDirs` | `test_rec03a_*metadata*/*huge*/*concurrent*/*sync*` (15 tests) incl. control 3 | `LocalLibraryRepository.import_files` (`to_thread(inspect)`), playlists `local-list:`, `_refresh_cover` → fase posterior |
| `db/local_library_repository.py`, `db/experience_repository.py`, `services/listening_periods.py`, `services/home_composer.py`, `services/experience_events.py`, viewmodels/controladores/QML | Repositorios agregados, composición home, eventos, pantallas | — (no recuperado) | — | — (ningún test REC-03A los importa) | Fase posterior completa; exigirían DB/QML/reproducción (prohibido en REC-03A) |

Controles reforzados exigidos en la aprobación (todos cubiertos):

1. **Dedup con distinto id**: clave `(name.casefold(), identity)` preserva
   `[{"A","UC_A"},{"A","UC_B"}]` (ambos) y colapsa mismo id. Test
   `test_credits_same_name_different_ids_preserved`.
2. **Rutas resueltas contenidas**: además de validar `video_id`, se verifica que
   todo hit de caché vive bajo `XDG_CACHE_HOME` (`is_relative_to`), que
   `file://` inexistente → `""`, y que `video_id` con `/.: `, espacios o
   `..` se rechaza (`""`/passthrough sin tocar offline).
3. **Malformados / enormes / concurrentes**: dañado → defaults sin excepción;
   `>16 MiB` no llega a `Image.open` (mock verifica `called == []`); 8 hilos
   sobre la misma carátula → 1 URL, JPEG válido (`verify()`), sin `*.tmp`.
4. **mutagen frozen**: `pyproject` declara `mutagen>=1.47,<2`; ambos `.spec`
   añaden `"mutagen"` + `collect_submodules("mutagen")` (36 submódulos:
   `mp3/flac/mp4/ogg/wave/...` que `File()` carga dinámicamente y modulegraph
   no ve). Tests estáticos lo verifican + `py_compile` de specs.

Arquitectura: no se introduce `asyncio` ni se tocan controladores Qt.
`read_metadata()` es síncrona por diseño (decodifica en el hilo llamante);
el docstring exige `asyncio.to_thread` en futuros consumidores.

## 2. Archivos modificados y motivo

- `src/doremi/services/artist_credits.py` (nuevo): servicio puro recuperado.
- `src/doremi/services/artwork.py` (nuevo): selector sin red recuperado.
- `src/doremi/services/local_metadata.py` (nuevo): lector local recuperado +
  docstrings de contrato síncrono/atomicidad/límite (única adaptación).
- `pyproject.toml`: +`mutagen>=1.47,<2` (igual que rescate; `pillow`/`loguru`
  ya existían). Sin dependencias pesadas nuevas.
- `doremi.spec`, `doremi-linux.spec`: +`"mutagen"` en `hiddenimports` +
  `collect_submodules("mutagen")` con comentario de justificación. `PIL` ya
  estaba. Sin cambios de `datas/binaries/excludes`/launchers.
- `.github/workflows/linux-appimage.yml` (`paths:` push + pull_request):
  +`services/artist_credits.py`, `services/artwork.py`,
  `services/local_metadata.py`, `tests/test_rec03a*.py`. Justificación estilo
  REC-02: el workflow ejecuta `pytest tests/ -q` completo pero se omitiría
  (`skipped`) en un PR de solo-servicios sin estas rutas. Ningún job/paso
  cambia. Resto de workflows sin cambios (`doremi.spec` ya dispara los de
  Windows; `doremi-linux.spec` ya dispara los de Linux).
- `tests/test_rec03a_metadata_services.py` (nuevo, 43 tests): ver §4 y RESULTS.
- `docs/release/REC03A-REPORT.md`, `docs/release/REC03A-RESULTS.md` (este pack).

No se crean migraciones, ni se tocan QML, controladores, repositorios de
experiencia, navegación, reproducción ni Rust.

## 3. Dependencias introducidas o evitadas

- Introducida: `mutagen>=1.47,<2` (1.48.1 instalada en venv; misma cota que
  rescate). Necesaria para `File/ID3/Picture` (mp3/flac/ogg/opus/m4a/wav).
  Congelada vía `hiddenimports` + `collect_submodules` (control 4).
- Reutilizadas (evitan peso nuevo): `pillow>=10.0`, `loguru>=0.7` (ya en
  baseline y en ambos `.spec`).
- Evitadas: `ytmusicapi/yt-dlp` (sin red en estos servicios), `sqlalchemy`,
  `PySide6/QML` (sin hilo Qt), `asyncio` en producción (solo `to_thread`
  documentado para consumidores futuros), cualquier dependencia pesada nueva.
- Sin variables de entorno nuevas (solo `XDG_CACHE_HOME/DATA/CONFIG` vía
  `AppDirs`, ya frozen-aware).

## 4. Pruebas (resumen; detalle en REC03A-RESULTS)

- Nuevas: `tests/test_rec03a_metadata_services.py` — **43 passed** (local).
- Completa local: **448 passed** (405 baseline REC-02 + 43 nuevas).
- Nativas local: **17 passed** (`test_native_rs.py`, wheel `maturin --release`).
- Packaging Python local: **16 passed** (`test_linux_packaging` + `test_linux_appimage`).
- CI verifica lo mismo sobre el código evaluado `48ec621`: AppImage
  **448 passed** + 17 nativas + 16 packaging; Linux portable
  **447 passed, 1 skipped** + 17 nativas (omisión documentada en RESULTS §5,
  no es fallo); Windows portable 17 nativas + build + smoke. Ver §5.
- `git diff --check`: OK. Specs `py_compile`: OK.

## 5. CI

Verificado SUCCESS sobre el código evaluado `48ec621` (evento `pull_request`
del PR #10; filtros `paths:` dispararon los workflows, no `skipped`):

- AppImage SUCCESS —
  `https://github.com/Eirom16/Doremi-Rust/actions/runs/38572766738`:
  **448 passed in 14.92s**, nativas **17 passed in 0.16s**, packaging
  **16 passed in 0.18s**, `mutagen-1.48.1` instalado desde `pyproject`,
  PyInstaller con `Analyzing hidden import 'mutagen...'` y
  `Adding imports: [..., 'mutagen', ...]`, generación AppImage y smoke tests
  completados (`DOREMI_SMOKE_OK`, 9/9: directo, launcher, A/B/C).
- Linux portable SUCCESS —
  `https://github.com/Eirom16/Doremi-Rust/actions/runs/38572766826`:
  **447 passed, 1 skipped in 9.43s**, nativas **17 passed in 0.13s**,
  construcción portable y smoke tests completados (`DOREMI_SMOKE_OK`, 9/9).
  La omisión (1 skipped) se documenta sin ocultarla ni convertirla en fallo:
  es un skip condicional preexistente de packaging Linux
  (`desktop-file-validate` no instalado / `Linux-only env semantics`,
  `pytest -q` no muestra el motivo), ajeno a REC-03A; el run AppImage sobre el
  mismo HEAD muestra 448 sin omisiones.
- Windows portable SUCCESS —
  `https://github.com/Eirom16/Doremi-Rust/actions/runs/38572766754`:
  nativas **17 passed in 0.50s**, `mutagen-1.48.1` instalado, PyInstaller con
  `Analyzing hidden import 'mutagen...'` (`doremi.spec` verificado en Windows),
  construcción del portable y smoke test completados (`DOREMI_SMOKE_OK`,
  `ok: True`, 9/9 checks, `f0b2a.windows.0c80db4d31eb`). Este workflow no
  ejecuta la suite completa por diseño (solo nativas + build + smoke).
- `windows-installer.yml` no dispara por diseño
  (filtro `branches: [build/f0b2a-windows-portable]`).
- PR #10 abierto y apilado sobre `recovery/rec02-data-foundation`, sin
  fusionar, sin tags ni releases. Estado: **VERIFIED** con los límites de §6.
Enlaces adicionales en REC03A-RESULTS §5.

## 6. Riesgos pendientes y límites explícitos de VERIFIED

- **Packaging verificado**: los tres bundles construyeron con `mutagen`
  procesado por PyInstaller (ver §5). `collect_submodules("mutagen")` cubrió
  los lectores dinámicos; un formato exótico no ejercitado podría revelar un
  import adicional, pero ningún formato soportado falló en CI.
- **Smoke ≠ funcional interactiva**: `DOREMI_SMOKE_OK` 9/9 valida arranque y
  contenido del bundle (Qt/VLC/dirs/migraciones/fuentes/Rust/puente/QML),
  no interacción real de pantallas.
- **QML**: persisten advertencias preexistentes de propiedades nulas como
  limitación conocida; no se introducen nuevas superficies QML en REC-03A.
- **Rendimiento**: `read_metadata()` debe ejecutarse fuera del hilo principal
  de Qt cuando se integre (`asyncio.to_thread`/worker). Es síncrona por diseño
  (PIL decode + `thumbnail(1024)` + JPEG q90); el límite 16 MiB previo a decode
  y `thumbnail` acotan memoria/DoS. Contrato documentado + test síncrono.
- **Alcance no recuperado**: repositorios (`LocalLibraryRepository`,
  `ExperienceRepository`), controladores, navegación, reproducción y
  consumidores QML/viewmodels siguen aplazados a fases posteriores.
- **Licencias**: publicación pública permanece **BLOQUEADA** (VLC/Qt/Python/
  Rust/fonts, ver `THIRD-PARTY-NOTICES`). Sin releases/tags. `mutagen` es
  GPLv2 — incorporarla al bundle mantiene el bloqueo vigente.
- **Disco/biblioteca**: la única escritura es la carátula content-addressed
  bajo `artwork_cache` (atómica tmp+`replace`, idempotente por hash,
  concurrente verificada). La biblioteca musical no se modifica.

## 7. Integridad de árboles

- Principal `/home/eirom/Proyectos/Doremi/Doremi-Rust @ 80aaf1e`
  (`build/f0b3b-linux-appimage`): limpio (`status` vacío), sin commits nuevos.
- REC-02 worktree `/home/eirom/Proyectos/Doremi/worktrees/rec02-data-foundation
  @ 38c1a1d`: limpio, sin cambios.
- Rescate `/home/eirom/Proyectos/Doremi/Doremi-Rust-Rescate @ c00d772`
  (`fix/f0a-ci-baseline`): solo lectura. Sin installs/builds/tests en él, sin
  `checkout/reset/clean/stash/commit`. `status` conserva sus `M`/`??`
  preexistentes; ningún fichero rastreado cambió por esta fase. Venv aislado
  creado solo en el worktree REC-03A (no en rescate).
- Esta fase vive solo en `recovery/rec03a-metadata-services` desde `38c1a1d`
  exacto. Sin merges de PRs, sin tags/releases.
