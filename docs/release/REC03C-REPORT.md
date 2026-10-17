# REC-03C — Composición de producto (Home, escucha y playlists): informe

Fase: REC-03C (recuperación controlada de composición sobre repositorios REC-03B).
Rama: `recovery/rec03c-product-composition` desde REC-03B exacto
`03324773740b58c0d1bfe1b4b8d64fe25f429e04`.
Worktree: `/home/eirom/Proyectos/Doremi/worktrees/rec03c-product-composition`.
Rescate (solo lectura): `/home/eirom/Proyectos/Doremi/Doremi-Rust-Rescate @ c00d772`
(working-tree con modificaciones sin commit; sin `.venv`/cachés/builds creados allí,
sin instalaciones/compilaciones/pruebas/escrituras/cambios Git allí).
Principal intacto: `/home/eirom/Proyectos/Doremi/Doremi-Rust` (no alterado).
Worktrees previos intactos: rec02/rec03a/rec03b (sin cambios).
PR base: `https://github.com/Eirom16/Doremi-Rust/pull/11` (REC-03B, abierto, sin fusionar).
Estado: NO VERIFIED (pendiente CI verde del PR apilado).

## 1. Auditoría, procedencia exacta y matriz

Rutas reales localizadas (todas existen en el rescate; ninguna asumida):

- `src/doremi/services/home_composer.py` (109 líneas, sha256 `7d4646fa…`):
  commit `b98c47e feat: personalize home…`, +9 líneas no versionadas
  (`cover_fields`, `smart_tracks limit 6→100` con comentario de covers).
- `src/doremi/services/listening_periods.py` (154 líneas):
  commits `11f15a8`/`b98c47e`/`69aa42e`, +41 líneas no versionadas
  (covers SQL `json_group_array`, `cover_fields`, thumbnails de downloads,
  thumbnails en `Wrapped`).
- `src/doremi/ui/screens/playlist_data.py` (185 líneas):
  commit `69aa42e`, +8 líneas no versionadas (`cover_fields` mosaico en 3 ramas,
  campo `artists` en remota).
- `src/doremi/ui/screens/stats_data.py` (143 líneas):
  commits `97f9a59`/`1e44a21`/`b98c47e`, +53 líneas no versionadas
  (`enrich_artist_portraits` con red + `remember_collections`).
- Dependencia común: `src/doremi/services/artwork.py`
  (`resolve_artwork`, `cover_fields`) es untracked en el rescate pero YA
  recuperada en REC-03B (idéntica); no se re-recupera.
- `src/doremi/ui/screens/home_data.py` (rescate): `gather_home` depende además
  de `services/explore.py` (ausente en REC-03B). Por eso el wrapper `gather_home`
  con `explore_categories` queda APLAZADO; `personalized_home` sí se recupera.

Funciones públicas y consumidores previstos:

- `home_composer.identity/diverse_tracks/compose_home` (puras): usadas por
  `personalized_home` y testeadas por `test_product_experience.py` del rescate.
- `personalized_home(remote)`: consumida por `home_data.gather_home`
  (`home_data.py:83`) y `home_qml`; solo necesita repos + `ListeningPeriods`.
- `ListeningPeriods.recent/tracks/save_as_playlist`, `Wrapped.summary`:
  consumidas por `home_composer` (periods), `playlist_data` (`session:`),
  `playlist_qml.save` y `stats_qml` (Wrapped).
- `gather_playlist(yt_client, id)`: consumida por `playlist_qml` y viewmodels;
  ramas `session:/local-list:/smart:` usan solo repos.
- `gather_stats(period)`: consumida por `stats_qml`; `enrich_artist_portraits`
  solo la usa `stats_qml` para retratos remotos (aplazada).

Contratos usados (todos ya en REC-03B, sin cambios):

- `ExperienceRepository.quick_access/continue_listening/smart_tracks/stats/
  remember_collections`, `SMART_TITLES`, `collection_route`, `period_bounds`.
- `LocalLibraryRepository.tracks(limit/offset)/playlists/cover_map/track_data/
  create_playlist/append/delete_playlist/remove_occurrence`.
- `SongRepository.ensure_songs/get_liked_video_ids/get_song/delete_song`,
  `HistoryRepository.add_entry/get_history/get_history_count`,
  `DownloadRepository.get_downloads/get_download/get_available_video_ids`.
- REC-03A: `artwork.resolve_artwork/cover_fields`, `local_metadata`,
  `offline_cache`, `NetworkMonitor`. `explore.py` ausente → aplazado.

Formatos: Home `{greeting,spotlight(≤1),tiles(≤6),horizontal(≤45),songs(≤16),
sections,personal[{title,items≤6}]}`; periodos
`{first_id,last_id,first_at,last_at,track_count,listen_time_ms,title,subtitle,
navigate=playlist?id=session:a:b:cutoff,thumbnail_url,artwork_sources}`;
playlists `{playlist_id,is_local,title,author,track_count,thumbnail_url,tracks[],
downloaded_count,is_fully_downloaded,local_meta[],limit,offset,has_more}`;
stats legacy `{time_listened,total_plays,unique_artists,top_songs[5],chart[7]}` y
`Experience.stats` completo.

Sin dependencias circulares nuevas: `home_composer→Experience` (top) +
`ListeningPeriods/DownloadRepository` (perezosos); `listening_periods→
Experience/LocalLibrary` (top) sin que `Experience` importe periodos;
`playlist_data→cover_fields` (top) + repos/`ListeningPeriods` (perezosos);
`stats_data` todo perezoso. Sin Qt/QML/viewmodels/controladores en los 4
módulos; sin red en importación (solo `urllib.parse`, `sqlalchemy`, `stdlib`).

| Módulo/función | Dependencias reales | Límites | FS bloqueante | Riesgo escritura en lectura | Decisión |
|---|---|---|---|---|---|
| `identity/diverse_tracks/compose_home` | ninguna (puras) | 6/6/16/45/1 + ≤2/artista | ninguno | ninguno (deepcopy) | RECUPERABLE (03C.1) |
| `personalized_home` | `continue/quick/smart×6(limit=100)/recent(3)/get_available` + `cover_fields` | 6 consultas acotadas + visibles | heredado `cover_fields/is_file` (≤~50 checks) | ninguno (solo lee + anota `is_downloaded`) | RECUPERABLE (03C.1, tests DB en 03C.2) |
| `ListeningPeriods.recent` | SQL window + `songs/downloads` + `cover_fields(≤4/periodo)` | `limit` 1..1000 (default 12) | heredado covers | ninguno | RECUPERABLE (03C.2) |
| `ListeningPeriods.tracks` | CTE miembros + `H/Song/Download` bacheado 500 + `track_data` | `limit/offset` opcionales (default completo compat) | `track_data is_file` necesario para offline correcto | ninguno | RECUPERABLE (03C.2, con paginación) |
| `save_as_playlist` (comando) | `ensure_songs→create→append` | periodo completo (unidad lógica) | mismo que tracks | ESCRIBE (nueva uuid; `append` atómico; `create+append` 2 Tx con limpieza best-effort) | RECUPERABLE como comando aislado, NO idempotente (03C.2) |
| `Wrapped.summary` | `Experience.stats(start/end)` local→UTC | año/mes validados | heredado stats | ninguno | RECUPERABLE (03C.2) |
| `gather_stats(period)` | `Experience.stats` | agregación SQL (supera 500) | heredado stats | ninguno | RECUPERABLE (03C.2) |
| `gather_stats()` legacy | `get_history(500)` + ≤5×2 lookups + `Counter` + chart 7d | 500 explícito + top5 | ninguno nuevo | ninguno | RECUPERABLE (03C.2, con `today` inyectable) |
| `enrich_artist_portraits` | `yt.search/get_artist` + `resolve_artwork` + `remember_collections` | semáforo 3/timeout 10 | red + escritura `Collection` desde presentación | ESCRIBE en lectura | APLAZADO (forma original) |
| `gather_playlist session:/local-list:/smart:` | 1 llamada acotada + `cover_fields` + filtro offline memoria | `limit/offset` (default 1000/0) + `has_more` | `track_data is_file` necesario | ninguno | RECUPERABLE (03C.3) |
| `_gather_local(local_)` | `get_downloads + get_liked` | slice `limit/offset` + `has_more` | ninguno | ninguno | RECUPERABLE (03C.3) |
| `_gather_remote` | `yt.get_playlist + get_downloads + get_liked` | proveedor (sin paginación propia) | ninguno | ninguno | RECUPERABLE + `artists` (03C.3) |
| `gather_home` wrapper con `explore` | `explore_categories` ausente | — | — | — | APLAZADO (sin stub) |

## 2. Alcance aplicado (sin QML/controladores/viewmodels)

- **REC-03C.1**: `services/home_composer.py` idéntico al rescate (109L).
- **REC-03C.2**: `services/listening_periods.py` (validación límites, `tracks`
  con `limit/offset` + bacheo IN 500 + orden `(played_at,id)`, `save_as_playlist`
  con limpieza best-effort y doc no-idempotente); `ui/screens/stats_data.py`
  (`gather_stats(period,today)` sin `enrich`, legacy 500 + chart inyectable).
- **REC-03C.3**: `ui/screens/playlist_data.py` (ramas `session:/local-list:/
  smart:` + `cover_fields` + `artists`, `gather_playlist(limit,offset)` con
  `has_more`, `local-list/session` delegan paginación —nunca `limit=None`—,
  `smart` over-fetch+slice, `local_` slice, remota completa documentada).
- No se tocan migraciones, modelos, QML, controladores, viewmodels, Rust,
  ni instalación (salvo docs/tests). Sin nuevas dependencias ni red en
  import/tests (mocks). `gather_home` con `explore` sigue aplazado sin stub.

## 3. Integridad y decisiones estructurales

- `save_as_playlist`: `ensure` falla→sin playlist (bien); `create` OK + `append`
  falla→borrado best-effort del vacío (evita huérfanas); `append` solo es
  atómico (REC-03B). `create+append` siguen siendo 2 Tx (sin unidad cross-repo
  en la arquitectura); reintentos crean NUEVA uuid (no idempotente, documentado
  en docstring + tests). No se prometió idempotencia.
- Paginación sin truncado silencioso: `limit/offset/has_more` en resultado;
  páginas posteriores con `offset+limit`; offline puede dar páginas cortas
  (no disponibles ocultos, no contados) —documentado.
- **REC-03C.4 (correcciones P1/P2)**:
  - `ExperienceRepository.smart_tracks` gana parámetros aditivos
    `offset=0` (paginación SQL con desempate determinista `Song.video_id`
    tras el orden de cada regla) e `include_unavailable=False` (filas con
    `is_file` fallido quedan marcadas `is_downloaded=False/local_path=None`
    en lugar de descartarse). Firmas previas intactas: llamantes existentes
    (`home_composer limit=100`, tests REC-03B) no requieren cambios y
    conservan el comportamiento heredado por default.
  - `playlist_data._paginate_visible`: paginación sobre el conjunto VISIBLE
    (ventana `limit+1`, crecimiento ×4 con tope 1.000 = tope de los tres
    repositorios, nunca clamped), salta desaparecidos sin consumir página,
    cursa `has_more` por evidencia `limit+1` y nunca revisita posiciones
    (sin N+1 y sin bucle infinito: terminación garantizada por finitud del
    store y crecimiento del cursor).
  - `ListeningPeriods.tracks`: corte de página en SQL (`LIMIT/OFFSET` en
    CTE de miembros, `ORDER BY played_at, id`); camino `limit=None` intacto
    para `save_as_playlist` (sigue no idempotente, ensure/create/append
    2 Tx sin transacción global —no se cambió esa semántica de
    optimización—). Mismos baches IN ≤500 por límite de variables SQLite.
- Borrados: canciones borradas no se autoborran del historial (`tracks`
  inner-join las oculta en la vista; historial intacto —test).
- Determinismo: `identity` con params ordenados; `compose_home` deepcopy +
  orden estable; SQL `ORDER BY (played_at,id)/(position,url)`; `Wrapped` por
  año/mes; `gather_stats(today=)` inyectable.
- `videoId/local_path/offline`: `track_data` + `get_available` + filtros
  `offline_only`/offline; desaparecidos→`local_path None/is_downloaded False`.
- Thumbnails: `cover_fields/resolve_artwork` solo leen (salvo `_refresh_cover`
  ya en REC-03B y `enrich` aplazado que sí escribía).

## 4. Pruebas (ver REC03C-RESULTS.md)

Focalizadas 40 (10+16+14) con SQLite `:memory:`/tmp + XDG aislados + mocks;
completa 514 passed; nativas 17; packaging 16. Workflows
`linux-appimage/linux-portable` ejecutan `pytest tests/ -q` (nuevos
`test_rec03c_*` autodetectados). Smoke no reclama funcionalidad Home/stats/
playlists.

Tras correcciones P1/P2 (REC-03C.4): 5 tests de regresión añadidos
(beyond-1000 smart, offline visible local-list/session, sesión extensa
620 SQL pushdown + evidencia de binds, IDs intercalados) → 45 focalizadas,
519 completa, nativas 17, packaging 16, `git diff --check` limpio.
Filtros `paths` de `linux-appimage.yml` ampliados (aditivos) para que el
PR #12 dispare el job `appimage` (suite completa) con los cambios de esta
fase. El estado VERIFIED sigue condicionado al CI verde.

## 5. Riesgos pendientes y árboles

- `is_file` heredado en `track_data/cover_fields/Experience` (necesario
  para offline; acotado; `get_available` ya usa `to_thread`). REC-03C.4
  evalúa el bloqueo para paginación visible: ~32 µs/stat y ≤ `limit+1
  stats/llamada pequeña` (40 ms/1000 stats medidos en ext4 local); ventanas
  crecen ×4 cap 1.000, así que el peor caso sigue un solo barrido acotado
  —no se introduce `to_thread` nuevo ni se re-firma `track_data` (REC-03B).
- `smart:` offline/offline-only: la pertenencia por regla usa `now` fijo
  por llamada `gather_playlist` (ventanas y página comparten frontera
  30/60 días); entre PÁGINAS distintas, un `now` de reloj distinto puede
  mover cut-off sub-second —inherente al contrato actual (no empeorado).
- Offline `smart:`/`liked` vía SQL pre-filtra
  (`file_path/local_path NOT NULL`): las filas sin ninguna ruta grabada no
  son candidatos (nunca fueron disponibles); filas CON ruta muerta sí
  entran y se marcan (`include_unavailable`) para el corte visible.
- `has_more` con `limit=1000`: ventana pedida 1001 se satura al tope de
  repositorio 1000; el helper resuelve evidencia escaneando la siguiente
  ventana (coste acotado, sin falso `False`).
- Lock `append/delete` proceso-local; `position` PK puede colisionar
  multiproceso (heredado REC-03B).
- `remember_collections` puede vaciar thumb con `""` (heredado).
- Orphans `local_playlist_tracks` sin `Song` ocultos sin limpieza (heredado).
- `stats sum(listen)` incluye inválidos (heredado, preservado).
- Licencias: publicación pública BLOQUEADA. No fusionar/tags/releases.
- Árboles: rescate sin escrituras nuevas; principal y worktrees previos
  intactos; REC-03C solo añade 3 fuentes + 3 tests + 2 docs (REC-03C.4
  modifica 3 fuentes existentes + 2 tests + 2 docs + 1 workflow de CI,
  rama apilada sobre REC-03B).
