# REC-04.1.2 — Resultados

Fecha: 2026-10-23. Rama `recovery/rec042-navigation-resume`.
Base publicada verificada: `a4cb9f23e8f55149f084e12ce0b2bfc996e92434`
(PR #13, rama `recovery/rec041-playback-context`).

## Preparación

Última ejecución del HEAD documental de REC-04.1.1 consultada antes de avanzar:
[39085705408](https://github.com/Eirom16/Doremi-Rust/actions/runs/39085705408),
`completed / success`. Job `117551692920`, AppImage, también success.
El worktree nuevo se creó desde ese SHA, sin mover las ramas anteriores.

## Commits de esta unidad

| Commit | Unidad / cambio |
|---|---|
| `9569444` | A: pruebas rojas de navegación local y reconexión |
| `989c4c3` | A: política central con parámetros e identidades válidas |
| `16e253f` | B: pruebas rojas de reanudación y carreras de seek |
| `50a9289` | A: refrescar disponibilidad al perder red, con regresión roja previa |
| `2343134` | B: miembros, contexto, tokens y seek protegido; pruebas adicionales |
| `2a6559c` | CI: filtros aditivos para todos los archivos de REC042 y sus documentos |

El commit documental sigue a los anteriores. Consultar `git log` o el HEAD
del PR para su SHA; ninguna fase anterior se reescribe.

## Pruebas locales

Intérprete existente utilizado solo como dependencia:
`/home/eirom/Proyectos/Doremi/worktrees/rec03c-product-composition/.venv/bin/python`.
Código importado desde `src` del worktree nuevo. Todas las ejecuciones con
`QT_QPA_PLATFORM=offscreen`, `PYTHONDONTWRITEBYTECODE=1` y
`-p no:cacheprovider`; no se instala ni escribe en el entorno anterior.
SQLite y filesystem temporales, YouTube/extractor/VLC simulados en la batería
nueva; sin base de datos, música o configuración reales.

| Bloque | Comando (`python -m pytest`) | Resultado |
|---|---|---|
| A roja inicial sobre la base | `tests/test_rec042_offline_navigation.py -q` | 10 failed / 14 passed |
| A pérdida de conexión en smart, antes del refresco | `tests/test_rec042_offline_navigation.py::test_connection_loss_refreshes_smart_offline_filter -q` | 1 failed |
| A final | `tests/test_rec042_offline_navigation.py -q` | **25 passed** |
| B roja inicial | `tests/test_rec042_collection_resume.py -q` | 22 failed / 8 passed |
| B roja, batería final contra código A | mismo archivo, sin implementación B | 23 failed / 10 passed |
| B selección durante animación, antes de snapshot inicial | `tests/test_rec042_collection_resume.py::test_playback_selection_during_navigation_animation_cancels_resume -q` | 1 failed |
| Focalizadas A+B y contratos previos | `tests/test_rec042_collection_resume.py tests/test_rec042_offline_navigation.py tests/test_rec041_playback_context.py tests/test_playback_request_races.py tests/test_player.py tests/test_controllers.py -q` | **128 passed**, 24.73 s |
| Suite completa | `tests/ -q` | **599 passed**, 42.62 s (541 + 58) |
| Nativas + packaging | `tests/test_native_rs.py tests/test_linux_packaging.py tests/test_linux_appimage.py -q` | **33 passed**, 0.62 s (17 nativas + 16 packaging) |
| Diff | `git diff --check` | limpio |
| Workflow | `yaml.safe_load` + comparación de paths con archivos modificados | válido, cobertura completa |

La repetición roja de B se hizo temporalmente en el worktree nuevo usando
los archivos de A (`50a9289`) y restaurándolos en `finally`; no se tocó ningún
worktree anterior. Los logs locales de trabajo están en `/tmp/rec042-*.log`.
Las carreras se coordinan con `asyncio.Event` y el lock del reproductor,
sin tiempos de red ni audio reales.

## CI y estado

**VALIDADO LOCALMENTE; CI de REC042 pendiente al redactar este commit.**
No se declara VERIFIED con el CI de REC-04.1.1 ni con resultados locales.
El PR se apila sobre `recovery/rec041-playback-context`, nunca sobre main.

El workflow `Linux AppImage (F0B-3B)` ejecuta nativas, packaging, suite completa,
PyInstaller, AppImage y sus smoke tests. Los filtros de `pull_request` incluyen
`navigation_controller.py`, `integrations_controller.py`, `audio/player.py`,
`tests/test_rec042*.py` y `docs/release/REC042*.md`. Se añadieron también a los
paths de push conservando su restricción de rama existente. Por tanto, tanto
código como sellado documental del PR disparan la validación representativa.

## Integridad

Comparación posterior con snapshot previo de HEAD y estado porcelain completo:

| Árbol anterior | Resultado |
|---|---|
| `Doremi-Rust` / build | idéntico, limpio |
| `rec02-data-foundation` | idéntico, limpio |
| `rec03a-metadata-services` | idéntico; conserva los no seguidos previos de `.venv` |
| `rec03b-data-repositories` | idéntico, limpio |
| `rec03c-product-composition` | idéntico, limpio |
| `rec041-playback-context` | idéntico, limpio, HEAD `a4cb9f23` |
| `Doremi-Rust-Rescate` | solo lectura; HEAD/porcelain idénticos con sus cambios previos |

Los límites funcionales y contratos modificados están en
[REC042-REPORT.md](REC042-REPORT.md). D2 sigue pendiente. Sin cambios en QML,
ViewModels, modelos, migraciones ni Rust. Sin `experience_events`, Home nuevo
o estadísticas. Sin merge, tags, releases o publicación pública; licencias
siguen bloqueando la distribución pública. No se inicia la siguiente fase.
