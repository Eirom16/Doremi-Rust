# REC-02 — Data Foundation: informe de recuperación

Fase: REC-02 (recuperación controlada del modelo de datos).
Rama: `recovery/rec02-data-foundation` sobre `build/f0b3b-linux-appimage @ 80aaf1e`.
Worktree: `/home/eirom/Proyectos/Doremi/worktrees/rec02-data-foundation`.
Rescate (solo lectura): `/home/eirom/Proyectos/Doremi/Doremi-Rust-Rescate @ c00d772`
(`fix/f0a-ci-baseline`, con 9 commits exclusivos sobre el merge-base `1e44a21`
más modificaciones sin commit). Principal intacto:
`/home/eirom/Proyectos/Doremi/Doremi-Rust @ 80aaf1e` (limpio).
PR: `https://github.com/Eirom16/Doremi-Rust/pull/9` (abierto, sin fusionar).
CI: `https://github.com/Eirom16/Doremi-Rust/actions/runs/38499973485` (success).
HEAD evaluado: `f6fdd90934702c40921866eb9d362842a41440ac`.
Estado: VERIFIED (cierre documental post-CI, 2026-10-14).

Nota de ruta: el enunciado cita `src/doremi/audio/playback_context.py`,
pero el archivo real del rescate es `src/doremi/services/playback_context.py`
(introducido en `11f15a8`). Se recupera esa ruta real; la discrepancia queda
registrada como adaptación documental.

## 1. Preflight (2026-10-13)

| # | Comprobación | Resultado |
|---|--------------|-----------|
| 1 | Existen ambas rutas | OK (`Doremi-Rust`, `Doremi-Rust-Rescate`) |
| 2 | HEAD esperados | OK (principal `80aaf1e`, rescate `c00d772`) |
| 3 | Principal limpio | OK (`status --porcelain` vacío) |
| 4 | Rescate con modificaciones | OK (`M` + `??` extensos, 84 ficheros con diff) |
| 5 | Carpeta de respaldos | OK (`/home/eirom/Respaldos/Doremi/`: `Doremi-Git-History.bundle` + `Doremi-Rust-20261012-234058.tar.gz`) |

Todas las precondiciones pasaron; se creó el worktree con
`git worktree add -b recovery/rec02-data-foundation <path> 80aaf1e`.

## 2. Alcance aplicado

Recuperar **solo esquema + modelos + contratos mínimos** de las
funcionalidades de producto del rescate; separar explícitamente la
implementación completa de repositorios/controladores para fases posteriores.

Dentro:
- Migraciones `20260929_0003` (orígenes, `position_ms`, tabla `collections`)
  y `20260929_0004` (`songs.local_path`, tabla `local_playlist_tracks`).
- Modelos `Collection`, `LocalPlaylistTrack`, `Song.local_path`,
  `PlayHistory.position_ms` + índice `ix_history_context_time`.
- Extensión mínima de `HistoryRepository.add_entry`
  (`position_ms`, `context_title`, cache de `Collection` sin recrear
  `local-list:` eliminadas).
- Contrato mínimo de origen: `QueueItem.context_*` (3 campos),
  `ListenResult.position_ms` + propagación en `ListeningSession`,
  `src/doremi/services/playback_context.py` (`CONTEXT_TYPES` + `playback_context()`).
- Pruebas de integridad/migración + actualización de `test_database.py` al head `0004`.
- Ampliación mínima del trigger de CI `linux-appimage.yml` (ver §5).

Fuera (deferido con motivo):
- `ExperienceRepository` completo (277 líneas, agregaciones, `artwork`,
  `cover_map`, stats/pins/smart-tracks/continue-listening).
- `LocalLibraryRepository` completo (importación con `local_metadata`,
  `cover_map`, `_refresh_cover`, playlists locales).
- `SongRepository.ensure_songs`, `DownloadRepository.get_available_video_ids`
  (helpers de rendimiento/offline, sin cambio de esquema).
- `QueueItem.artists` (solo working-tree del rescate, para créditos de artista;
  ajeno a 0003/0004).
- `services/listening_periods.py`, `services/experience_events.py`,
  `services/artwork.py`, `services/local_metadata.py`, controladores, QML,
  Rust, pantallas, instaladores.

## 3. Matriz de recuperación

| Archivo origen (rescate) | Funcionalidad recuperada | Archivo destino | Adaptaciones | Tests que la protegen | Pendiente |
|---|---|---|---|---|---|
| `src/doremi/db/migrations/versions/20260929_0003_product_context.py` (nuevo en `11f15a8`) | Orígenes de reproducción: `play_history.position_ms`, índice `(context_type, context_id, played_at)`, tabla `collections` | `src/doremi/db/migrations/versions/20260929_0003_product_context.py` (nuevo) | Mismo `revision`/`down_revision`; añadidos helpers `_tables/_columns/_indexes` y guardas idempotentes estilo 0001/0002; `downgrade` con guardas (solo destruye artefactos REC-02) | `test_rec02_fresh_migration_reaches_head`, `test_rec02_upgrade_from_0002_preserves_data`, `test_rec02_reupgrade_is_idempotent`, `test_rec02_indexes_and_constraints`, `test_rec02_downgrade_preserves_0002_data`, `test_database_initialization_uses_alembic_for_file_db` | Nada de esquema; el uso pleno (pins/continue/stats) requiere `ExperienceRepository` (fase posterior) |
| `src/doremi/db/migrations/versions/20260929_0004_local_library.py` (nuevo en `11f15a8`) | Biblioteca local: `songs.local_path`, tabla `local_playlist_tracks` + índice `video_id` | `src/doremi/db/migrations/versions/20260929_0004_local_library.py` (nuevo) | Igual que 0003: mismos IDs, guardas idempotentes, `downgrade` con guardas | Mismos tests de migración + `test_rec02_new_models_read_write`, `test_rec02_unique_constraints_reject_duplicates` | Escritura/lectura plena de playlists locales requiere `LocalLibraryRepository` (fase posterior) |
| `src/doremi/db/models.py` (`M` en `11f15a8`) | `Song.local_path`, `PlayHistory.position_ms` + `Index(ix_history_context_time)`, `Collection`, `LocalPlaylistTrack` | `src/doremi/db/models.py` | Copia exacta del delta de esquema (verificado con `diff`: idéntico al rescate); sin cambios de packaging | `test_rec02_in_memory_create_all_includes_new_tables`, `test_rec02_new_models_read_write`, suite `test_database/test_repository` | Nada |
| `src/doremi/db/repository.py` (`M` en `11f15a8` + `ensure_songs` en `b98c47e` + `get_available` en `110c316/69aa42e`) | Solo la extensión de `HistoryRepository.add_entry` (`position_ms`, `context_title`, cache `Collection`) | `src/doremi/db/repository.py` | Se importa solo ese hunk; se excluyen deliberadamente `ensure_songs` y `get_available_video_ids` (deferidos, ver §2) | `test_rec02_history_repository_position_and_collection`, `test_history_repository_add_entry` (existente, sigue verde) | `ensure_songs`, `get_available_video_ids` → fase posterior con sus consumidores |
| `src/doremi/audio/queue.py` (`M` en `11f15a8` + `artists` solo en working-tree) | `QueueItem.context_type/context_id/context_title` con defaults (`unknown`/`""`) | `src/doremi/audio/queue.py` | Solo los 3 campos de contexto; se excluye `artists: list[dict]` (working-tree ajeno a REC-02) | `test_rec02_queue_item_context_survives_serialization`, suite `test_queue.py` | `artists` + controladores de cola → fase posterior |
| `src/doremi/audio/listening.py` (`M` en `11f15a8`) | `ListenResult.position_ms` + `position_ms=self._last_position_ms or 0` en `finish()` | `src/doremi/audio/listening.py` | Copia exacta (verificado con `diff`: idéntico al rescate) | `test_rec02_listening_session_reports_position`, suite `test_player.py` | El volcado a `HistoryRepository` por el controlador → fase posterior |
| `src/doremi/services/playback_context.py` (nuevo en `11f15a8`; el enunciado lo cita como `audio/`) | `CONTEXT_TYPES` + `playback_context(window)` (origen en el borde de acción de usuario) | `src/doremi/services/playback_context.py` (nuevo) | Copia exacta (sin acoplamiento nuevo; la función ya es pura y sin dependencias Qt/DB) | `test_rec02_playback_context_origins` | Su cableado en `navigation/playback/queue_controller` + `main_window` → fase posterior |
| `src/doremi/db/experience_repository.py` (nuevo en `11f15a8`, `M` en `b98c47e/69aa42e`, `M` en working-tree) | Consultas agregadas de producto | — (no recuperado) | — | — (ningún test REC-02 lo importa) | Fase posterior completa |
| `src/doremi/db/local_library_repository.py` (nuevo en `11f15a8`, `M` en working-tree) | Importación/playlists locales | — (no recuperado) | — | — | Fase posterior completa |
| `src/doremi/db/database.py` (`M` rescate: `bundle_package_dir` → `Path(__file__)`) | Cambio de resolución de migraciones | — (no recuperado, invariante) | Se conserva `bundle_package_dir` (frozen/PyInstaller); el rescate lo simplificaba solo para tests | `test_database_initialization_uses_alembic_for_file_db` verifica que la ruta empaquetada sigue funcionando | Nada |

## 4. Invariantes

- Esquema hasta `0002` intacto: las migraciones nuevas solo añaden; el
  upgrade desde `0002` con datos de prueba conserva filas (`test_rec02_upgrade_from_0002_preserves_data`).
- Datos de usuario: todos los tests usan `tmp_path` / `:memory:`; ningún test
  toca `~/.local/share/doremi/doremi.db` (verificado por diseño; la CI además
  usa `XDG_*` temporales).
- Rutas de configuración/DB: `config/paths.py` y `db/database.py` sin cambios.
- Convenciones SQLAlchemy/Alembic: migraciones idempotentes estilo 0001/0002,
  `env.py` y `Base.metadata` sin cambios.
- Inicialización/empaquetado: sin cambios en `*.spec`, launchers, instaladores,
  QML, Rust. Solo el trigger de CI (justificado en §5).
- Soporte Windows/Linux: cambios solo Python puro + SQLite; sin rutas
  específicas de plataforma.

## 5. Cambio mínimo de CI (justificación)

El workflow `linux-appimage.yml` ejecuta la suite completa
(`python -m pytest tests/ -q`), pero sus filtros `paths:` no incluían
`db/models.py`, `db/migrations/**`, `db/repository.py`,
`services/playback_context.py`, `audio/queue.py`, `audio/listening.py` ni los
tests de base/datos. Un PR de solo-datos habría omitido el workflow
(`skipped`), lo que el enunciado prohíbe como evidencia. Se añadieron
únicamente esas rutas a `push` y `pull_request` del workflow
`linux-appimage.yml`; ningún job, paso ni script cambió. Sin este cambio, las
pruebas nuevas nunca se ejecutarían en CI.

Cierre post-CI (2026-10-14): el PR #9 disparó el workflow (evento
`pull_request`, no `skipped`) y el job Linux AppImage concluyó `success`
sobre el HEAD `f6fdd90`. Los 15 fallos locales documentados en
REC02-RESULTS §3 se producen solo cuando falta la extensión Rust compilada
(`ImportError: native_rs extension module not found`); con el wheel instalado
la suite completa pasó en CI (405 passed, incluyendo 17 de `test_native_rs.py`).

## 6. Riesgos

- `downgrade` 0004→0002 elimina artefactos REC-02 (`collections`,
  `local_playlist_tracks`, `position_ms`, `local_path`). Preserva datos
  pre-0003 por diseño, pero puede destruir datos creados en las nuevas tablas
  y columnas (filas de `collections` / `local_playlist_tracks`, valores de
  `position_ms` / `local_path` escritos tras el upgrade) si se degrada
  (comportamiento estándar de Alembic, documentado en el `downgrade`).
- Sin FKs por diseño (desnormalizado para supervivencia de historial). La
  integridad referencial `local_playlist_tracks.video_id → songs.video_id` la
  garantiza la capa de repositorio futura, no la DB.
- `position_ms` con `server_default="0"` (heredado del rescate) deja el tipo
  como entero SQLite; verificado en upgrade desde 0002 (filas viejas → `0`).
- El smoke frozen (`DOREMI_SMOKE_OK`, 9/9) valida arranque y contenido del
  bundle, no demuestra interacción real de las pantallas.
- Las advertencias QML de propiedades nulas permanecen como limitación
  conocida de la prueba.
- Proceso: durante la fase local se creó una `.venv` ignorada dentro del
  rescate (`uv run --project <rescate>`); no repetirlo — el rescate debe
  conservarse estrictamente en solo lectura.

## 7. Pendiente para siguientes fases

1. `ExperienceRepository` (pins, `quick_access`, `continue_listening`,
   `smart_tracks`, `stats`, `period_bounds`, `collection_route`).
2. `LocalLibraryRepository` (`import_files` + `local_metadata`, `cover_map`,
   playlists `local-list:`, `append`/`tracks`/`_refresh_cover`).
3. `SongRepository.ensure_songs`, `DownloadRepository.get_available_video_ids`.
4. Cableado de `playback_context` en controladores y `main_window`; `QueueItem.artists`.
5. `listening_periods.py`, `experience_events.py`, servicios de home/artwork,
   pantallas QML/viewmodels, Rust.

## 8. Cierre post-CI (2026-10-14)

- PR #9 abierto (sin fusionar) sobre `build/f0b3b-linux-appimage @ 80aaf1e`;
  HEAD de producción evaluado `f6fdd90`.
- CI run 38499973485 (`pull_request`): job Linux AppImage `success`.
  Evidencia completa en `REC02-RESULTS.md` §§3–5 (suite 405, nativa 17,
  packaging 16, AppImage + smoke 9/9 PASS).
- Este cierre es exclusivamente documental: ningún cambio de producción,
  tests, workflows o specs. No se inicia REC-03A.
