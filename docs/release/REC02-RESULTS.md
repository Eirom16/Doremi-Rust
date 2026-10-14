# REC-02 — Data Foundation: resultados

Rama: `recovery/rec02-data-foundation` → destino `build/f0b3b-linux-appimage`.
Base: `80aaf1e`. Rescate (lectura): `c00d772` (+ working-tree).
Fecha: 2026-10-13 (UTC-4). Bases de prueba: solo `tmp_path` / `:memory:`.

## 1. Migraciones

- Cadena verificada: `20260708_0001 → 20260926_0002 → 20260929_0003 → 20260929_0004`
  (`ScriptDirectory.get_heads() == ['20260929_0004']`).
- `test_rec02_fresh_migration_reaches_head`: `init_db()` en archivo temporal
  deja `alembic_version = 20260929_0004` y las 7 tablas
  (`songs`, `play_history`, `downloads`, `cached_artwork`, `notifications`,
  `collections`, `local_playlist_tracks`).
- `test_rec02_upgrade_from_0002_preserves_data`: upgrade
  `0002 → head` con 1 canción + 1 historial + 1 descarga conserva las 3 filas;
  `songs.local_path IS NULL`, `play_history.position_ms == 0` en filas viejas.
- `test_rec02_reupgrade_is_idempotent`: `upgrade head` dos veces sin error.
- `test_rec02_downgrade_preserves_0002_data`: `head → 0003 → 0002 → head`
  conserva la fila semilla `keep`; artefactos REC-02 aparecen/desaparecen según
  revisión sin tocar datos pre-0003.

## 2. Integridad de datos

- `test_rec02_indexes_and_constraints`: existen
  `ix_history_context_time`, `ix_play_history_was_played`,
  `ix_local_playlist_tracks_video_id`; PKs compuestas en `collections`
  (`context_type`, `context_id`) y `local_playlist_tracks`
  (`playlist_id`, `position`); `NOT NULL` en `collections.title/thumbnail_url`
  y `local_playlist_tracks.video_id`; `songs.local_path` nullable;
  `PRAGMA foreign_key_list` vacío en las 5 tablas (desnormalizado intencional).
- `test_rec02_new_models_read_write`: RW de `Song.local_path` (valor + `NULL`),
  `PlayHistory.position_ms=42000`, `Collection`, y duplicados deliberados de
  `video_id` en posiciones distintas de la misma playlist.
- `test_rec02_unique_constraints_reject_duplicates`: `IntegrityError` en
  `songs.video_id`, `collections` PK y `local_playlist_tracks` PK duplicados.
- `test_rec02_history_repository_position_and_collection`: `add_entry` guarda
  `position_ms`, crea `Collection` desde `context_title`, no recrea
  `local-list:` eliminadas, y `position_ms` por defecto `0`.
- `test_rec02_notification_add_if_new_idempotent`: segundo `add_if_new` → `False`.
- Contratos: `test_rec02_playback_context_origins` (6 rutas + `local`),
  `test_rec02_queue_item_context_survives_serialization` (shuffle/move/restore
  + compat con payloads legacy sin claves de contexto),
  `test_rec02_listening_session_reports_position` (`15000` tras observes, `0`
  sin posición).

## 3. Tests ejecutados (local)

Comando (venv aislado del worktree, Python 3.12):

```
uv run --project . --python 3.12 --with pytest --with pytest-asyncio \
  python -m pytest tests/test_rec02_data_foundation.py tests/test_database.py tests/test_repository.py -q
```

Resultado: **25 passed** (14 REC-02 + 3 database + 8 repository).

Suite completa (sin `test_native_rs.py`, que requiere el wheel Rust sin
construir en este entorno):

```
python -m pytest tests/ -q --ignore=tests/test_native_rs.py
```

Resultado: **373 passed, 15 failed**. Los 15 fallos son `ImportError:
native_rs extension module not found` en `test_audit_regressions.py` (13) y
`test_settings_qml.py` (2). Verificación de baseline: con los cambios
aparcados (`git stash --keep-index`), la misma selección falla igual
(**15 failed, 78 passed** en esos dos ficheros), por lo que son
preexistentes/ambientales (falta de build Rust), no regresiones de REC-02.
Ningún test DB/audio/contrato falla.

Regresiones relevantes verdes: `test_database.py`, `test_repository.py`,
`test_queue.py`, `test_player.py`, `test_playback_request_races.py`,
`test_linux_packaging.py`, `test_linux_appimage.py` (estos dos últimos pasan
sin construir el bundle; validan rutas empaquetadas, no el binario).

## 4. Empaquetado / nativo

- Sin cambios en `*.spec`, QML, launchers, instaladores, `native_rs/`,
  `config/paths.py`, `db/database.py`. Impacto de empaquetado: nulo por diseño.
- `doremi/db/migrations` sigue resolviéndose vía `bundle_package_dir`
  (ruta frozen verificada por los tests de packaging existentes).
- Tests nativos (`test_native_rs.py`) no ejecutados localmente (sin wheel);
  quedan para CI, que construye el wheel con maturin antes de la suite.

## 5. CI

- Se amplió el trigger `paths:` de `linux-appimage.yml` (único cambio de
  workflow) para que un PR de solo-datos dispare el workflow, que a su vez
  ejecuta `pytest tests/ -q` completo. Sin este cambio el workflow se omitiría
  (`skipped`) y no habría evidencia.
- Estado al cierre de este documento: **PENDING** (PR por abrir; ver informe
  final para URL y runs). Hasta disponer de run verde con las pruebas REC-02
  listadas en el log, la fase es `IMPLEMENTED / PENDING_CI`, no `VERIFIED`.

## 6. Repositorios originales

- Principal `Doremi-Rust @ 80aaf1e`: limpio antes y después (solo el worktree
  contiene cambios; verificado con `git status`).
- Rescate `Doremi-Rust-Rescate @ c00d772`: sin commits ni añadidos al índice
  desde esta fase (solo lectura). Un `uv run --project <rescate>` intermedio
  recreó su `.venv` ignorado (`git check-ignore .venv` OK); ningún fichero
  rastreado cambió por esa acción (`status` sigue con los mismos 84 ficheros).
