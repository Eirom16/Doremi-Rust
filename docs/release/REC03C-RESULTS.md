# REC-03C — Composición de producto: resultados

Rama: `recovery/rec03c-product-composition` → destino
`recovery/rec03b-data-repositories` (apilado, no `main`).
Base: `03324773740b58c0d1bfe1b4b8d64fe25f429e04`. Rescate (lectura): `c00d772`.
Fecha: 2026-10-14 (UTC). Solo `tmp_path`/XDG temporales + mocks.
Estado: NO VERIFIED (pendiente CI verde del PR).

## 1. Pruebas nuevas (40 passed → 45 tras correcciones P1/P2)

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

Resultado original: **514 passed**. Tras correcciones P1/P2 (REC-03C.4):
**519 passed** (474 baseline REC-03B + 40 REC-03C + 5 nuevas). Sin fallos.

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
- REC-03C.4: los filtros `paths` de `linux-appimage.yml` (push y
  `pull_request`) no incluían los archivos de esta fase; se añaden de forma
  aditiva `tests/test_rec03b*.py`, `tests/test_rec03c*.py`,
  `src/doremi/db/experience_repository.py`,
  `src/doremi/services/listening_periods.py` y
  `src/doremi/ui/screens/playlist_data.py`, de modo que el PR #12 dispara la
  suite completa + nativas + packaging + `git diff --check` al publicar los
  commits de corrección. El job `appimage` ejecuta `pytest tests/ -q`
  completo: los 5 tests nuevos quedan incluidos.
- Smoke no reclama funcionalidad interactiva.
- Commits: `d8ab1ca` (03C.1 feat) + `859a6ef` (03C.2 feat) + `59c8659`
  (03C.2 test) + `e3eb4bd` (03C.3 feat) + `18efbf1` (03C.3 test) + docs + REC-03C.4
  `283343e` (fix smart SQL pagination) + `32dd5ba` (test paginación offline
  visible) + `d30c3d9` (perf tracks SQL pushdown) + docs correcciones. PR apilado
  sobre `recovery/rec03b-data-repositories` (crear tras docs; no fusionar, no
  tags/releases). No VERIFIED hasta CI verde.
- Riesgos documentados en REPORT §5 (heredados + `create+append` 2 Tx).

## 5. Correcciones P1/P2 (REC-03C.4, corrección técnica de revisión)

Reproducción de cada defecto con prueba que falla sobre el árbol de
recuperación original (`70d224e`), verificado mediante run aislado de las
fuentes previas (`git archive 70d224e` en scratch `/tmp`, sin tocar árboles reales).

- **P1-A (commit `283343e`)**: `smart:` recortaba después de un sobre-fetch
  de 1.000 → páginas `offset>0` no alcanzaban a cruzar el tope y `has_more`
  usaba la heurística `len==cap`. Corrección: paginación real en SQL —
  `ExperienceRepository.smart_tracks` gana `offset` validado (SQL `OFFSET`
  tras `ORDER BY <regla>, Song.video_id`, desempate determinista para
  empates) y `include_unavailable` (marca `is_downloaded=False/local_path=None`
  en vez de descartar; default `False` preserva el comportamiento heredado y
  a `home_composer`). `playlist_data` pagina `smart:` sobre el conjunto
  VISIBLE con ventana acotada.
  Test reproducción (falla en código previo, pasa tras el fix):
  `test_rec03c3_smart_pagination_beyond_1000` — 1.200 favoritas sin
  historial (todas empatadas), páginas `limit=600` en `offset=0/600/1200`
  recomponen la secuencia exacta sin omisiones/repetidos y con `has_more`
  exacto (`True/False/cola vacía+False`).
- **P1-B (commits `283343e`+`32dd5ba`)**: `session:`/`local-list:` filtraban
  offline DESPUÉS de paginar (páginas encogidas + `has_more` heurística
  engañosa). Corrección común: helper `_paginate_visible` en
  `playlist_data.py` — recorre candidatos por ventanas (`limit+1`
  inicial, ×4 hasta tope 1.000 = tope de los tres repositorios, nunca
  clampeado), salta tras desaparecidos sin consumir espacio de página,
  corta solo visibles, avanza cursor sin revisitar posiciones (sin N+1,
  sin bucle infinito) y calcula `has_more` por evidencia `limit+1`
  (exacta). Contratos de repos sin firma alterada (misma
  `limit/offset` publicados); `is_file` queda en los repositorios
  (evaluación de bloqueo: ~32 µs/stat y ≤ `limit+1` stats por llamada
  pequeña — mide `40ms/1000`; no se introduce `to_thread` nuevo).
  Tests reproducción: `test_rec03c3_local_list_offline_pagination_excludes_missing`
  (7 rutas inexistentes primeras + 9 disponibles → páginas 4/4/1 exactas,
  `has_more` `True/True/False`, concatenación igual al orden de disponibles,
  ninguna marca de disponibilidad sobre archivo ausente) y
  `test_rec03c3_session_offline_pagination_excludes_missing` (equivalente
  sobre historial/sesión).
- **P2 (commit `d30c3d9`)**: `ListeningPeriods.tracks` materializaba TODO
  el período (CTE completa id por id + JOINHistory/Song/Download de todos +
  recorte Python). Corrección: el corte `LIMIT :limit OFFSET :offset` viaja
  en SQLite tras `ORDER BY played_at, id` sobre los miembros (misma
  semántica de ventana: IDs marcadores de ruta, intercalados soportados);
  solo la página (≤ limit filas, IN bacheado ≤500) se materializa.
  `limit=None` conserva el camino completo idéntico (save_as_playlist sin
  cambios: ensure/create/append, no idempotente). Test reproducción
  `test_rec03c2_tracks_large_session_sql_pagination` — sesión de 620
  entradas: corte exacto `limit=100/offset=200`, recomposición de 6
  páginas consecutivas sin huecos, igualdad con el camino completo, y
  evidencia SQL (existe statement con `LIMIT`/`OFFSET`; máx. parámetros
  enlazados ≤10 donde el camino previo enlazaba ~620 IDs). Test adicional
  `test_rec03c2_tracks_interleaved_ids_sql_paging` (IDs no contiguos).

Resultados tras correcciones: **45 focalizadas passed** (5 nuevas), suite
completa **519 passed**, nativas **17**, packaging **16**, `git diff --check`
limpio. Rendimiento P2 medido: página `limit=5` en sesión de 2.000 miembros,
offset 1.000 — 121.68 ms antes → 18.77 ms después (−85%); memoria acotada al
tamaño de página (5 filas + CTE en SQLite).
