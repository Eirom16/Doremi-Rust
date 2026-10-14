# REC-03C — Composición de producto: resultados

Rama: `recovery/rec03c-product-composition` → destino
`recovery/rec03b-data-repositories` (apilado, no `main`).
Base: `03324773740b58c0d1bfe1b4b8d64fe25f429e04`. Rescate (lectura): `c00d772`.
Fecha: 2026-10-14 (UTC). Solo `tmp_path`/XDG temporales + mocks.
Estado: NO VERIFIED (pendiente CI verde del PR).

## 1. Pruebas nuevas (40 passed)

Comando (venv REC-03A reutilizado, mismas deps, Python 3.12):

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ~/Proyectos/Doremi/worktrees/rec03a-metadata-services/.venv/bin/python -m pytest tests/test_rec03c_home_composition.py tests/test_rec03c_listening_stats.py tests/test_rec03c_playlist_data.py -q
```

Resultado: **40 passed** (10 home + 16 escucha/stats + 14 playlists).

- 03C.1 (10): imports sin red/Qt; `identity` (videoId/`play:`/params ordenados,
  resume/position/next/autoplay ignorados); `diverse_tracks` (cap ≤2/artista,
  dedup, sin-artista); `compose_home` vacío/dedup-prioridad/límites
  6/16/45/1/personal-6/offline-songs-sobre-spotlight/no-mutación/
  determinismo; `personalized_home` perezoso (`ListeningPeriods`/
  `DownloadRepository` lazy, `smart×100` + `recent(3)`).
- 03C.2 (16): imports sin red/Qt y sin `enrich`; sin `is_file` directo;
  vacío/parcial (skips ignorados)/abundante (510→`stats(all)` 510, legacy 500
  documentado); gap 30min + IDs como marcadores; cutoff 90d + periodo que
  crece; paginación `tracks(limit/offset)` + validación; duración desconocida
  + covers faltantes; fronteras calendario half-open; `gather_stats(period)`
  delega + `today` inyectable determinista; lecturas no escriben
  (`Collection/Song` counts iguales); `save` duplicados `["dup","dup"]` +
  reintento crea NUEVA id (no idempotente); `save` vacío raise antes de
  escribir; `save` con `append` roto→sin parcial; `save` con `ensure` roto→
  sin playlist.
- 03C.3 (14): imports sin red/Qt; vacío/inválidos (`session:bogus`,
  `local-list:missing`, `smart:bogus→ValueError`, límites); `smart:liked`
  contrato; `session:` igual a `tracks`; `local-list` orden/duplicados/huecos
  `[0,2]`; `local:` nunca YouTube; desaparecido→`local_path None/False`;
  offline filtra a disponible (local + smart); paginación grande
  10→4+4+2 con `has_more` y recomposición exacta; covers faltantes `""`;
  remota preserva `artists` + liked/downloaded + counts; remota con fallo→
  vacío sin red; borrada se oculta en vista pero historial intacto; 1 sola
  llamada repo por rama (no N+1).

## 2. Suite completa + nativas + packaging

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/ -q
```

Resultado: **514 passed** (474 baseline REC-03B + 40 nuevas). Sin fallos.

Nativas (`tests/test_native_rs.py`): **17 passed**.
Packaging (`test_linux_packaging.py` + `test_linux_appimage.py`):
**16 passed**. Sin nuevas dependencias; `AppDirs` frozen-safe; nuevos `.py`
bajo `src/doremi/{services,ui/screens}` incluidos automáticamente.

## 3. Recuperadas / adaptadas / aplazadas

- Recuperadas: `home_composer.{identity,diverse_tracks,compose_home,
  personalized_home}`, `ListeningPeriods.{parse_identity,recent,tracks,
  save_as_playlist}`, `Wrapped.summary`, `gather_stats(period/legacy)`,
  `gather_playlist{session,local-list,smart,local_,remote}` + `cover_fields`
  + `artists`.
- Adaptadas: límites validados, `tracks(limit/offset)` + bacheo 500,
  `save_as_playlist` con limpieza best-effort + doc no-idempotente,
  `gather_stats(today=)`, `gather_playlist(limit/offset/has_more)`,
  `smart` over-fetch+slice, docstrings de procedencia/contratos.
- Aplazadas: `enrich_artist_portraits` (red + writes), `gather_home` con
  `explore.py` (sin stub), QML/controladores/viewmodels/Rust/migraciones/
  modelos. Sin stubs.

## 4. CI y entrega

- Workflows `linux-appimage.yml/linux-portable.yml` ejecutan `pytest tests/ -q`
  (+ `test_native_rs` y packaging); nuevos `test_rec03c_*` se activan por
  `testpaths=["tests"]`/`python_files=["test_*.py"]` sin cambiar workflows.
- Smoke no reclama funcionalidad interactiva.
- Commits: `d8ab1ca` (03C.1 feat) + `859a6ef` (03C.2 feat) + `59c8659`
  (03C.2 test) + `e3eb4bd` (03C.3 feat) + `18efbf1` (03C.3 test) + docs. PR apilado sobre
  `recovery/rec03b-data-repositories` (crear tras docs; no fusionar, no
  tags/releases). No VERIFIED hasta CI verde.
- Riesgos documentados en REPORT §5 (heredados + `create+append` 2 Tx).
