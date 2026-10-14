# REC-03B — Repositorios de datos de producto: informe de recuperación

Fase: REC-03B (recuperación controlada de persistencia para biblioteca local y experiencia).
Rama: `recovery/rec03b-data-repositories` sobre `recovery/rec03a-metadata-services @ e657b06c18b0915b45f5473c2fe2971ce3701447`.
Worktree: `/home/eirom/Proyectos/Doremi/worktrees/rec03b-data-repositories`.
Rescate (solo lectura): `/home/eirom/Proyectos/Doremi/Doremi-Rust-Rescate @ c00d772`
(working-tree con modificaciones sin commit; sin `.venv`/cachés/builds creados).
Principal intacto: `/home/eirom/Proyectos/Doremi/Doremi-Rust @ 80aaf1e` (limpio).
REC-02 worktree intacto: `38c1a1d`. REC-03A worktree intacto: `e657b06`.
PRs previos abiertos sin fusionar: REC-02 `https://github.com/Eirom16/Doremi-Rust/pull/9`,
REC-03A `https://github.com/Eirom16/Doremi-Rust/pull/10`.
Estado: VERIFIED para el alcance validado (cierre documental post-CI).
CI: `https://github.com/Eirom16/Doremi-Rust/actions/runs/38648459157`
(completed / success) sobre HEAD `04f3b2e9299dbfe939362ca6285a2a0c383fa5c0`.
PR REC-03B: `https://github.com/Eirom16/Doremi-Rust/pull/11` (abierto, apilado
sobre REC-03A, sin fusionar).

## 1. Matriz de auditoría y procedencia exacta del código

Procedencia: los dos candidatos son working-tree untracked-modified en el rescate
(no recuperables por cherry-pick directo; contienen contratos incompatibles si se
copian sin adaptar por falta de rollback/validación).

- `src/doremi/db/local_library_repository.py`: 189 líneas, sha256
  `e9d226e5330fffbcb2a370d442d14b154e283f6b7c76aeafd74687e939c94fab`,
  modificado sobre rescate `11f15a8 feat: add playback origins, listening insights
  and local collections` (diff +83/-15: enriquece reimport con `read_metadata`,
  `cover_map` con `row_number`, `_refresh_cover` en `append`/`remove`).
- `src/doremi/db/experience_repository.py`: 277 líneas, sha256
  `b3650a18d671fe22bf56bbd7172cd77efd71a2a1f40e2f4155023bed71926dc7`,
  modificado sobre `11f15a8` (diff +34/-?: integra `resolve_artwork`,
  `cover_map` en `quick_access`/`continue_listening`/`stats`, retratos de artista).
- `src/doremi/db/repository.py` (rescate): 428 líneas; REC-02 difirió
  `SongRepository.ensure_songs` (+16L) y `DownloadRepository.get_available_video_ids`
  (+10L + `asyncio`/`Path` imports). REC-03A baseline (400L) no los tiene.
- Modelos idénticos: `diff models.py` rescate vs REC-03A = vacío (0).
- Servicios REC-03A ya disponibles: `artwork.py` idéntico (`diff` vacío),
  `local_metadata.py` solo docstring (82L rescate vs 97L REC-03A, mismo comportamiento).
- Migraciones 0003/0004: mismos `revision` y esquema que rescate `11f15a8`,
  pero idempotentes en REC-02 (guardas `_tables/_columns/_indexes`); `diff`
  muestra solo adaptación idempotente, sin cambio de esquema.

| Método público | Entrada / Salida | Tablas/índices | Deps ausentes | CRUD | Tx/excepciones | Dedup/identidad | Colecciones/playlists/historial | Compat 0002→0004 | Riesgos | Recuperable independiente |
|---|---|---|---|---|---|---|---|---|---|---|
| `local_identity(path)` | `path->"local:"+sha256(resolved)` | — | — | — | pura | path-based (misma ruta=mismo id; contenido igual+ruta distinta=ids distintos) | — | — | `resolve()` sigue symlinks; mudanza genera duplicado (esperado) | Sí |
| `track_data(song, dl_path)` | `Song+path->dict(videoId,title,artist,album,thumbnail,duration,local_path,is_liked,is_downloaded,result_type)` | — + `Path.is_file` | — | R | pura + FS check | — | `is_downloaded` exige archivo real; borrado→`local_path None` | NULLs (`album/thumbnail/duration` → `""`/0) | — | Sí |
| `LocalLibrary.import_files(paths)` | `list[str]<=1000 -> int` | `songs` (batch 500), `local_playlist_tracks` (afectados), `collections` (covers) | `read_metadata`, `cover_fields` (disponibles REC-03A) | R+I+U | 1 sesión `flush+commit`; rescate sin `rollback` → adaptado con `rollback` | dict por identidad; reimport enriquece sin borrar (`if value or not getattr`) | No toca historial/descargas; refresca covers de playlists afectadas | `local_path` NULL en viejas → excluidas de `search` (correcto) | Sin lock (carrera crea `IntegrityError`); 1000 cap; solo `artwork_cache` escribe | Sí (con `to_thread`) |
| `search(query,limit=100)` | `str,int->list[track_data]` | `songs.local_path IS NOT NULL` + `icontains(autoescape)` orden `title` | — | R | read-only | — | Solo locales; remotas excluidas | Viejas NULL excluidas | `limit` sin validar en rescate → adaptado 1..1000 | Sí |
| `create_playlist(title)` | `str->"local-list:"+uuid` | `collections` PK(type,id) | — | I | `commit`; rescate sin rollback → adaptado | UUID único (no idempotente, correcto) | Crea `playlist/local-list:*` título ≤200 | — | Título vacío→`ValueError` (es) | Sí |
| `playlists()` | `->list[id,title,navigate,thumbnail,subtitle]` | `collections` WHERE `local-list:` orden `title` + `cover_map` | `cover_map` | R | read-only | — | Solo locales; `subtitle="Playlist local"` | — | — | Sí |
| `cover_map(session,ids)` | `session+list->dict[id->cover_fields]` | `local_playlist_tracks` PK + `ix_video_id`, `songs.thumbnail` + window `row_number` | `cover_fields` | R | read-only, usa sesión ajena | Top 4 por `(position,url)` particionado | — | — | Requiere SQLite ≥3.25 (CI moderno OK) | Sí |
| `rename_playlist(id,title)` | `->None` o `ValueError` | `collections` PK get | — | U | `commit` + adaptado rollback | — | Solo `local-list:`; inexistente→`ValueError` | — | — | Sí |
| `delete_playlist(id)` | `->None` o `ValueError` | `delete tracks` + `delete collection` bajo `asyncio.Lock` | — | D | serializado proceso-local; adaptado rollback | Idempotente si no existe (0 filas) | Preserva `songs`/historial/archivos (no borra ficheros) | — | Lock no cross-process; colisión `position` PK en multiproceso | Sí |
| `remove_occurrence(id,pos,vid)` | `->bool` | `delete WHERE (playlist,position,video)` + `_refresh_cover` | — | D | `commit` + adaptado rollback | Posiciones con huecos `[0,2]` deliberado (no renumera) | Preserva archivos/historial | — | Inválido→`False` (no excepción) | Sí |
| `append(pid,vids)` | `->None` o `ValueError` | `collections` get + `songs` batch 500 check + `max(position)` + inserts + `_refresh_cover` | — | I | Lock + `flush+commit` atómico (check antes de insertar); adaptado rollback | `dict.fromkeys` para check pero inserta duplicados deliberados (600 en test) | Mezcla local+remoto; exige metadatos conocidos | — | Lock proceso-local; `IN ()` evitado con early-return | Sí |
| `tracks(id,limit?,offset?)` | `->(title,list[track+local_position])`; missing→`("",[])` | `Song JOIN track INNER + Download LEFT` orden `position` | — | R | read-only | Duplicados conservados con posiciones originales | Orphan (song borrado) invisible (inner join) sin limpieza | — | Rescate sin paginación → adaptado `limit/offset` opcionales | Sí |
| `Experience.pinned_routes/is_pinned` | `->list[route]/bool` | `collections.pinned_at NOT NULL` orden `(position,pinned_at)` | — | R | read-only | — | `session:` nunca pineado | — | — | Sí |
| `remember_collections(items)` | `list[{title,navigate,thumbnail}]->None` | `collections` batch `tuple_ IN` 250 | — | I+U | `commit` + adaptado rollback; ignora `search/queue` y sin id | Upsert por `(type,id)`; sobrescribe título/thumb ("" si falta → riesgo menor) | Cache compartida orígenes + pins ordenados | — | — | Sí |
| `set_pin/reorder_pins` | `->None/bool` o `ValueError` | `collections` + `max(position)` | — | I+U | `commit` + adaptado rollback; `reorder` exige conjunto completo (stale→`False`) | `position` max+1 (carrera mismo valor); `session:`→`ValueError` | Pins ordenados por `position` | — | — | Sí |
| `quick_access(limit=6)` | `->list[title,type,navigate,pinned]` | `collections playlist !session:` + actividad 90d (`sum plays/max recent`) + `cover_map` locales | `cover_map` lazy | R | read-only, `limit` | Orden pinned→position→plays→recent→title | Excluye `session:` | — | — | Sí |
| `continue_listening(limit=4,offline_only)` | `->list[title,subtitle,navigate,video_id,position_ms,completed]` | `play_history` window `row_number` partición contexto (latest wins) + `collections` + `songs` + `downloads` | `cover_map` lazy | R | read-only; `position_ms` 0 si `completed` o `skip` | Latest attempt wins (incl. skips); skip deliberado no reanuda | `offline_only` exige prefijos + archivo real (`is_file` Python) | `position_ms` default 0 en viejas | FS checks en loop (≤limit, acotado) | Sí |
| `smart_tracks(rule,limit,now,offline_only)` | `rule∈SMART_TITLES ->list[videoId,...,score]` o `ValueError` | `play_history` afinidad `2+completion+min(listen/60k,5)` agregada por video + `songs` + `downloads` | — | R | read-only; `order_by(rule)+video_id` determinista | `repeat(score>0)`,`liked`,`offline`,`forgotten(plays≥3,recent<60d)`,`discoveries(first≥30d,score≥3)`,`recent` | Virtual (no almacenada); `offline`/`offline_only` filtran `is_file` | NULLs via `outerjoin/coalesce` | — | Sí |
| `stats(period/start/end)` | `->dict[time_listened,plays,unique_*,completion,skip,discoveries,top_songs/artists/collections,peak_hour,active_day,chart,_error]` | `play_history` múltiples agregados + `songs` top5 + retratos artista (single-identity) + `collections` top10 + `cover_map` locales + `date(localtime)` chart 31d | `DownloadRepository.get_available` + `cover_map` lazy | R | read-only; límites 5/10/31d acotados | `known_artist` excluye `"",Unknown` ; `session:` excluido de colecciones | Historial fuente verdad; denormalizado sobrevive borrado `songs` | `played_at` NULL (0002 sin valor) excluido por `<end` (tests deben dar `played_at`) | Pesada pero acotada; `sum(listen)` incluye inválidos (rescate, preservado) | Sí (exige `get_available`) |
| `SongRepository.ensure_songs(items)` | `list[{video_id,title,artist,...}]->None` | `songs` batch 500 `IN` | — | I | `commit` + adaptado rollback + validación | Solo inserta missing (retiene likes/plays); `dict` dedup | — | — | Rescate `KeyError` si falta clave → adaptado `ValueError` | Sí |
| `DownloadRepository.get_available_video_ids(ids)` | `list->set` filtrado `is_file` | `downloads` batch 500 `(video_id,file_path)` | — | R | read-only + `to_thread(is_file)`; vacío→`set()` sin I/O | Dedup `dict.fromkeys` | Stale DB paths no son offline | — | — | Sí |

Comprobaciones específicas exigidas:
- No depende de migraciones futuras: usa solo `songs(video_id,title,artist,album,duration_ms,thumbnail_url,is_liked,last_played,play_count,local_path)`,
  `play_history(+listen_time_ms,completion_ratio,skip_count,completed,was_played,context_type,context_id,position_ms,played_at)`,
  `collections(type,id,title,thumbnail,pinned_at,position)`, `local_playlist_tracks(playlist_id,position,video_id)`,
  `downloads(...)`; todo existe en 0004; NULLs manejados.
- No depende de controladores ni rutas antiguas: imports solo `sqlalchemy`,
  `stdlib`, `db.database/models`, `services.artwork/local_metadata`; sin
  `controllers/viewmodels/QML/red/Rust`; `AppDirs.artwork_cache/cache/offline`
  frozen-safe (`bundle_package_dir`, `sys._MEIPASS`); sin ` downgrade` como recuperación.
- Sin FKs por diseño (denormalizado): validación manual (`playlist` existe,
  `songs` conocidos, prefijos `local-list:`, `session:` rechazado).

## 2. Alcance mínimo decidido y aplicado

Aprobado `Aprobar alcance completo` (ambos independientes y compatibles con REC-02,
sin nuevas migraciones ni cambios de arquitectura):

- **REC-03B.1 Biblioteca local**: `local_library_repository.py` completo
  (`local_identity`, `track_data`, `EXTENSIONS`, 9 métodos + `cover_map`,
  `_refresh_cover`) + `ensure_songs` + `get_available_video_ids`.
- **REC-03B.2 Experiencia**: `experience_repository.py` completo
  (`SMART_TITLES`, `collection_route`, `period_bounds`, 8 métodos).
- Adaptaciones mínimas (sin refactors generales): `rollback` explícito en todo
  write, validación de refs/ids/límites, early-returns vacíos, `tracks(limit,offset)`
  opcional (default ilimitado, compatible), `limit` 1..1000 con cap, preservación
  de mensajes `ValueError` en español, preservación de atomicidad/duplicados/huecos,
  `to_thread` para `read_metadata`/`is_file` en `get_available`.
- Aplazado (documentado, no implementado a medias): controladores
  (`navigation/desktop/playback`), pantallas (`library_data/playlist_data/search_data/
  stats_data/artist_qml/...`), servicios (`home_composer/listening_periods/Wrapped`),
  QML/viewmodels, sincronización remota, Rust. Ningún stub incompleto.

## 3. Esquemas y contratos utilizados

- Migraciones REC-02 0001→0004 (idempotentes, mismos `revision` que rescate):
  `songs.local_path NULLABLE`, `play_history.position_ms DEFAULT 0` +
  `ix_history_context_time`, `collections` PK compuesta, `local_playlist_tracks`
  PK `(playlist_id,position)` + `ix_video_id`. Sin cambios en esta fase.
- Contratos: `video_id` único (`songs/downloads`), `local:sha256(resolved)`,
  `local-list:uuid4hex`, `(playlist_id,position)` único (duplicados en distintas
  posiciones permitidos), `(context_type,context_id)` PK colecciones,
  `pinned_at/position` orden pins, `limit/offset` paginación, consultas
  parametrizadas SQLAlchemy, `icontains(autoescape)` anti-wildcard.
- Separación: persistencia SQLite (`db/*`) vs lectura metadatos
  (`services/local_metadata.read_metadata` síncrono, `to_thread` en repo) vs
  UI (no importada). Sin red al importar (solo `urllib.parse`).

## 4. Evaluación de integridad de datos

- Preservación: `delete_playlist` no borra `songs`/historial/ficheros;
  `import` enriquece sin borrar (`if value or not getattr`); `ensure_songs`
  no toca conocidos; historial/descargas denormalizados sobreviven borrado
  `songs`; `HistoryRepository.add_entry` no recrea `local-list:` borrada.
- Rollback: todo write con `try/commit/except/rollback/raise`; `append`
  atómico (check previo, `flush` antes de covers); reintento válido tras fallo
  probado.
- Orphans: `tracks` inner-join oculta tracks sin `Song` (sin limpieza agresiva);
  `remember` puede sobrescribir thumb con `""` si falta (riesgo menor anotado).
- Concurrencia: `asyncio.Lock` proceso-local para `delete/append`; multiproceso
  puede colisionar `position` PK (SQLite single-writer, sin retry; riesgo pendiente).
- Rendimiento: batches 500/250, `import` cap 1000, `search/smart/quick/continue`
  con `limit`, `stats` top 5/10 + chart 31d; window `row_number` exige SQLite
  moderno (CI Linux/Windows OK).
- Downgrade nunca como recuperación (destructivo para 0003/0004, probado solo
  como guarda REC-02; esta fase solo `upgrade 0002→head` preservando).

## 5. Pruebas y resultados exactos

Ver `docs/release/REC03B-RESULTS.md` para comandos y detalle por test.
Resumen: focalizada 26 passed; completa 474 passed (448 baseline +26);
nativas 17 passed; packaging 16 passed. CI
(`https://github.com/Eirom16/Doremi-Rust/actions/runs/38648459157`,
completed / success) confirma sobre el HEAD exacto: suite completa
474 passed in 12.96s, nativas 17 passed, packaging 16 passed.

## 6. Estado de empaquetado y CI

- Workflows afectados: `linux-appimage/linux-portable/windows-portable`
  (ejecutan `pytest tests/ -q` + `test_linux_packaging/test_native_rs`);
  `native.yml/native-build.yml` no afectados (sin Rust).
- Cambios activan pruebas pertinentes (nuevos `test_rec03b_*` + suite completa).
- Empaquetados compatibles: sin nuevas dependencias (`sqlalchemy/aiosqlite/
  mutagen/PIL` ya en `pyproject`+`.spec`); `datas` ya colecta
  `db/migrations`; nuevos `.py` bajo `src/doremi/db` incluidos automáticamente;
  `AppDirs`/`bundle_package_dir` frozen-safe.
- Smoke test no reclama funcionalidad interactiva (repos sin UI).
- Cierre VERIFIED (alcance validado): CI
  `https://github.com/Eirom16/Doremi-Rust/actions/runs/38648459157`
  completed / success sobre HEAD `04f3b2e9299dbfe939362ca6285a2a0c383fa5c0`
  (merge-ref `c1bb73e9d6a3c5880f6a510b6358f43b6cece42d`, REC-03B sobre REC-03A
  `e657b06`): suite completa 474 passed in 12.96s, nativas 17 passed,
  packaging 16 passed, AppImage Type 2 construido correctamente, ejecución
  FUSE PASS, smoke 9/9 PASS.
- Alcance de la verificación: no se afirman pruebas funcionales interactivas;
  no se declara una nueva verificación independiente de Windows portable ni de
  Linux portable más allá del alcance validado por el run citado.

## 7. Riesgos pendientes

1. Serialización de playlists limitada al proceso (`asyncio.Lock` en
   `delete_playlist`/`append`): dos procesos anexando la misma playlist pueden
   colisionar PK o `max(position)` (requiere retry `busy` o serialización DB).
2. `tracks(limit=None)` sin paginación automática: por defecto devuelve la
   playlist completa (compatible con rescate); consumidores futuros deben usar
   `limit/offset` para listas potencialmente grandes.
3. Comprobaciones síncronas de archivos en algunos métodos de
   `ExperienceRepository` (`resolve_artwork`/`Path.is_file` en
   `quick_access`/`continue_listening`/`smart_tracks`/`stats`, acotado por
   `limit`; `get_available_video_ids` ya usa `to_thread`).
4. Posible pérdida de thumbnails al actualizar determinadas colecciones:
   `remember_collections` sobrescribe `thumbnail_url` con `""` si el item no
   trae thumbnail.
5. Referencias huérfanas aplazadas: `tracks` oculta `local_playlist_tracks`
   sin `Song` (inner join) sin limpieza agresiva (acumulación posible).
6. Identidad de canción local vinculada a la ruta (`local:sha256(resolved)`):
   mover el archivo o cambiar symlinks genera duplicado (sin identidad por
   contenido); `resolve()` sigue symlinks.
7. Advertencias QML preexistentes (fuera del alcance REC-03B; sin cambios QML
   en esta fase).
8. Licencias pendientes: publicación pública BLOQUEADA.
9. `stats` `sum(listen_time_ms)` incluye intentos inválidos (heredado del
   rescate; documentado, no cambiado para no alterar contratos).

## 8. Confirmación de integridad de todos los árboles

- Rescate solo lectura: sin `.venv`/cachés/builds/modificaciones nuevas
  (mismo `M` previo; `sha256` auditados).
- Principal `~/Proyectos/Doremi/Doremi-Rust @ 80aaf1e` limpio.
- `worktrees/rec02-data-foundation @ 38c1a1d` limpio.
- `worktrees/rec03a-metadata-services @ e657b06` solo `?? .venv/` preexistente.
- `worktrees/rec03b-data-repositories` rama `recovery/rec03b-data-repositories`
  desde `e657b06` exacto; cambios: `M repository.py` + `?? local_library…,
  experience…, test_rec03b…, docs REC03B-*` (sin tocar migraciones/modelos).
- Pruebas solo SQLite `:memory:`/archivo `tmp_path` + `XDG_*` a `tmp`; sin
  DB/música/config reales.

## 9. Siguiente fase recomendada

REC-03B queda VERIFIED para el alcance validado. La siguiente fase recomendada
(solo como propuesta, sin iniciar REC-03C ni fusionar ramas en esta entrega)
sería cablear `home_composer/listening_periods` + `playlist_data/library_data/
search_data/stats_data` sobre estos repositorios, con tests de composición
offline y `gather_playlist` mixta, manteniendo la prohibición de
QML/viewmodels/controladores hasta fase posterior.
