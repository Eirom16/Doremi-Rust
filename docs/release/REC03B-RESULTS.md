# REC-03B — Repositorios de datos de producto: resultados

Rama: `recovery/rec03b-data-repositories` → destino `recovery/rec03a-metadata-services`.
Base: `e657b06c18b0915b45f5473c2fe2971ce3701447`. Rescate (lectura): `c00d772`
(+ working-tree modificado auditado con sha256 `e9d226e5…`/`b3650a18…`).
PR: `https://github.com/Eirom16/Doremi-Rust/pull/11` apilado sobre
`recovery/rec03a-metadata-services` (abierto, sin fusionar, sin tags/releases).
Fecha: 2026-10-14 (UTC). Solo `tmp_path`/`XDG_*` temporales.
Estado: VERIFIED para el alcance validado (cierre documental post-CI).

## 1. Pruebas nuevas (26 passed)

Comando (venv del worktree REC-03A reutilizado por misma deps, Python 3.12):

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ~/Proyectos/Doremi/worktrees/rec03a-metadata-services/.venv/bin/python -m pytest tests/test_rec03b_data_repositories.py -q
```

Resultado: **26 passed in ~4s**.

Cobertura (ETAPA 4 completa):

- Imports sin red/Qt: `test_rec03b_imports_without_network_or_qt`,
  `test_rec03b_no_qt_controllers_in_repos` (mock `urlopen`/`create_connection` a fallo).
- `ensure_songs`: inserta missing + retiene likes/plays + idempotente,
  batch 510, rechaza malformados + early-return vacío.
- `get_available`: solo candidatos + archivos reales, missing/unrecorded
  excluidos, vacío sin I/O, dedup, `ValueError` en `None`.
- Biblioteca: `import` filtra extensiones/dirs/missing + enriquece sin duplicar;
  no reescribe música + sin red; `search` solo locales + `limit` 1..1000 +
  `icontains(autoescape)` (`100%`→`[]`); CRUD playlists preserva
  ficheros/songs/historial + validación es; `append` atómico (falla sin parcial,
  reintento OK) + duplicados deliberados; `tracks` paginación `limit/offset` +
  missing→`("",[])`; `remove` huecos `[0,2]` + inválidos→`False`;
  borrado tras import→`local_path None/is_downloaded False`;
  `cover_map([])=={}`; volumen 600 (append/tracks/get por ids);
  concurrencia 2 `append` misma DB archivo (`asyncio.gather` → `[0,1]`);
  sin escrituras fuera de `tmp` (música intacta, caché contenida).
- Experiencia: pins orden `[Pinned,Frequent,Fallback]` + `is_pinned`/`pinned_routes`
  + `reorder` conjunto completo + `ValueError` (`session:`, kind, `None`);
  `continue` resume 42000 + skip excluye + `limit` valida;
  `continue offline_only` exige archivo (borrado→`[]`, online sigue);
  `smart` repeat `["heard","seek"]` + liked/offline/recent + `ValueError`;
  `stats` vacío + `total_plays 1/listen 120000` (suma incluye inválidos, heredado)
  + `session:` excluido + `period_bounds` + `ValueError`;
  volumen 510 `total_plays 510`; upgrade `0002→head` preserva + repos operan;
  `period_bounds` calendario half-open + `collection_route` encoding.

## 2. Suite completa + nativas + packaging

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/ -q
```

Resultado: **474 passed in ~17s** (448 baseline REC-03A +26 nuevas).
Desglose: 457 no-nativas +17 nativas. Sin skips forzados, sin fallos.

Evidencia CI verificada
(`https://github.com/Eirom16/Doremi-Rust/actions/runs/38648459157`,
completed / success, merge-ref
`c1bb73e9d6a3c5880f6a510b6358f43b6cece42d` correspondiente a REC-03B HEAD
`04f3b2e` sobre REC-03A `e657b06`): suite completa **474 passed in 12.96s**,
nativas **17 passed**, packaging **16 passed**, AppImage Type 2 construido
correctamente, ejecución FUSE PASS, smoke 9/9 PASS.

Nativas:

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/test_native_rs.py -q
```

Resultado: **17 passed**.

Packaging:

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/test_linux_packaging.py tests/test_linux_appimage.py -q
```

Resultado: **16 passed**. Specs ya incluyen `sqlalchemy/aiosqlite/mutagen` y
`datas db/migrations`; nuevos `db/*.py` incluidos automáticamente; sin nuevas
deps; `AppDirs` frozen-safe.

## 3. Funciones recuperadas / adaptadas / aplazadas

- Recuperadas (contrato rescate preservado): `local_identity`, `track_data`,
  `LocalLibraryRepository.{import_files,search,create_playlist,playlists,
  cover_map,rename_playlist,delete_playlist,remove_occurrence,append,tracks}`,
  `collection_route`, `period_bounds`, `SMART_TITLES`,
  `ExperienceRepository.{pinned_routes,is_pinned,remember_collections,set_pin,
  reorder_pins,quick_access,continue_listening,smart_tracks,stats}`,
  `SongRepository.ensure_songs`, `DownloadRepository.get_available_video_ids`.
- Adaptadas (sin cambio esquema): `rollback` explícito en todo write,
  validación refs/ids/límites, `tracks(limit,offset)` opcional, `limit` cap
  1000, early-returns, preservación mensajes/duplicados/huecos/atomicidad.
- Aplazadas: controladores, pantallas, `home_composer/listening_periods/Wrapped`,
  QML/viewmodels, sync remota, Rust. Sin stubs.

## 4. Esquemas, integridad y riesgos

- Esquema REC-02 0004 sin cambios; `upgrade 0002→head` preserva
  `songs/history/downloads` (test con `played_at` explícito); `downgrade` nunca
  como recuperación.
- Integridad: sin borrados inesperados, rollback probado, denormalizado
  sobrevive, orphans documentados, `sum(listen)` heredado documentado.
- Riesgos: lock proceso-local, `is_file` en loop acotado, `remember` puede
  vaciar thumb, orphans sin limpieza, `local_identity` por ruta.
- Árboles: rescate sin escrituras nuevas; principal `80aaf1e` limpio;
  rec02 `38c1a1d` limpio; rec03a `e657b06` solo `.venv` preexistente;
  rec03b desde `e657b06` exacto con 4 ficheros código/tests +2 docs.

## 5. CI y entrega

- Workflows: `linux-appimage/linux-portable/windows-portable` ejecutan suite;
  `native*` no afectados. Cambios activan `test_rec03b_*` + suite.
- Smoke no reclama UI (repos sin UI; smoke 9/9 PASS del run citado corresponde
  al arranque/empaquetado, no a funcionalidad interactiva).
- Cierre VERIFIED para el alcance validado: CI
  `https://github.com/Eirom16/Doremi-Rust/actions/runs/38648459157`
  completed / success sobre HEAD exacto `04f3b2e` (merge-ref `c1bb73e9…`).
  No se afirman pruebas funcionales interactivas; no se declara una nueva
  verificación independiente de Windows portable ni de Linux portable más allá
  del alcance validado por dicho run.
- Riesgos que permanecen documentados: serialización de playlists limitada al
  proceso; `tracks(limit=None)` sin paginación automática; comprobaciones
  síncronas de archivos en algunos métodos de `ExperienceRepository`; posible
  pérdida de thumbnails al actualizar determinadas colecciones; referencias
  huérfanas aplazadas; identidad de canción local vinculada a la ruta;
  advertencias QML preexistentes; licencias pendientes (publicación pública
  BLOQUEADA).
- Commits pequeños + PR #11 apilado sobre `recovery/rec03a-metadata-services`.
  PR abierto y apilado. No fusionar, no tags/releases, no iniciar REC-03C.
