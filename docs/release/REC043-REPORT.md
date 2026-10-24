# REC-04.1.3 + REC-04.1.4 — Reproducción local, paginación y comandos

Fecha: 2026-10-24. Rama `recovery/rec043-playback-pagination`.
Worktree `/home/eirom/Proyectos/Doremi/worktrees/rec043-playback-pagination`.

## Base y preparación

Base exacta: `c58cc97f7bdb473a804c582027da4d3a6ca95048`, rama
`recovery/rec042-navigation-resume`, PR [#14](https://github.com/Eirom16/Doremi-Rust/pull/14).
Se volvieron a consultar el PR, la referencia publicada y los estados locales
antes de crear el worktree. Todos coincidían con ese SHA. El último CI del
HEAD, [40055058283](https://github.com/Eirom16/Doremi-Rust/actions/runs/40055058283),
estaba `completed / success`; no se infirió del informe anterior.

No existían la rama ni el directorio de destino. Se creó un worktree separado
sin mover los ocho árboles anteriores. Se guardó un snapshot de HEAD y del
porcelain completo, incluidos los cambios no versionados previos.

## REC-04.1.3A — D2: archivos locales en reproducción manual

La auditoría confirmó que `session:`, `local-list:` y `smart:` aportaban rutas
válidas en los tracks, pero `_on_vm_play_queue()` las descartaba. `local_`
seguía otro camino: `local_meta` → `_on_vm_play_local()` →
`PlaybackController._play_local_playlist()`.

Cambios mínimos:

- `available_local_path()` centraliza la disponibilidad de reproducción:
  archivo regular, no vacío y legible; captura errores de filesystem y nunca
  escribe ni borra música. `is_downloaded=True` no sustituye esa comprobación.
- El productor de cola conserva videoId, ruta real, flag local y tipo/ID/título
  REC-04.1.1. Play, Shuffle y fila conservan todas las ocurrencias; no se
  filtran miembros remotos online ni se deduplica por videoId.
- El productor `local_` conserva el contrato de metadatos existente, añadiendo
  `playback_context` cuando conoce su colección. La captura ocurre antes de
  la siguiente navegación/fade. No modifica los metadatos del ViewModel y
  respeta orígenes explícitos ya estampados. Callers antiguos sin identidad
  de pantalla conservan el fallback contextual de REC-04.1.1.
- `_play_local_playlist()` comprueba los archivos al construir QueueItem.
  El formato persistente de QueueItem y sus campos permanecen sin cambios.
- El reproductor prioriza una ruta válida ya capturada antes de consultar
  descargas; normaliza archivos desaparecidos. Una identidad importada
  `local:` no se envía al extractor como fallback remoto. Los IDs remotos
  conservan su fallback online y la semántica existente de fallo/skip.
- Después del await de descargas se comprueba `_current_play_id` y la identidad
  del objeto, tanto en éxito como en excepción, antes de aplicar resultados
  o consultar caché. Un resultado tardío no cambia el QueueItem reutilizado
  por otra reproducción.

REC-04.1.2 permanece compatible: no se cambia NavigationController, su token,
la semántica `resume/position/next`, ni el seek protegido de MusicPlayer.
El reproductor vuelve a validar al iniciar, porque un archivo puede desaparecer
entre la acción y la reproducción. El fallo de un archivo importado no se
convierte en una petición de streaming de su identidad local.

Pruebas rojas: 13 fallos / 8 pases sobre la base exacta. Se descartó una primera
invocación con un fixture faltante, que no se cuenta como evidencia roja.
Se añadieron dos regresiones posteriores, cada una roja antes del cierre:
excepción tardía de descargas y captura `local_` con la ruta de ventana ya
cambiada. Batería A final: 23 casos.

Se actualizó únicamente el fixture de una prueba REC-04.1.1: el supuesto
`/tmp/no-file.mp3` se sustituyó por un archivo sintético temporal. Las
aserciones de origen y ruta se mantienen; ya no dependen de considerar
reproducible un archivo inexistente. No se reescriben commits ni informes
previos ni se modifica un worktree anterior.

## REC-04.1.3B — Contrato incremental de Playlist

PlaylistViewModel y PlaylistTrackModel solo los consume PlaylistScreenQml;
la ampliación es aditiva y no altera los ViewModels de otras pantallas.
No se añade botón QML ni se reescribe la pantalla.

| API / estado | Contrato |
|---|---|
| `load(playlist_id, *, limit=1000, offset=0)` | Sustituye el rango visible; la llamada antigua sigue siendo válida. Validación y límite máximo de 1000 iguales al loader. |
| `load_more() -> bool` | Añade la siguiente página local; true si se aplicó, false si ocupada/final/error/obsoleta. CancelledError se propaga. |
| `pageOffset`, `pageLimit` | Offset de la última página aplicada y tamaño solicitado efectivo. La siguiente usa offset + limit. |
| `hasMore` | Evidencia entregada por gather_playlist; no se deduce de llenar una página. |
| `loadedCount` | Filas actualmente cargadas, incluidas ocurrencias repetidas legítimas. |
| `totalCount` | -1 si desconocido; solo se conoce el total visible al completar el rango desde offset cero. Remotas conservan el total del proveedor. |
| `loadingMore`, `loadMoreError` | Estado incremental separado de loading/errorText de la carga inicial. |
| `append_page(data) -> bool` | Solo acepta el siguiente offset de la misma identidad y limit; rechaza páginas repetidas o desordenadas. |
| `PlaylistTrackModel.append_items()` | beginInsertRows/endInsertRows, sin reset de filas anteriores ni deduplicación por videoId. |

El header identifica filas «cargadas» cuando no hay total conocido. No se
muestra un denominador cero como total de una página parcial. Los contadores
de descargas del loader son snapshots/agregados, no cantidades que se sumen
otra vez por cada página.

Una sola tarea incremental puede solicitar la página siguiente. Un refresh,
incluso de la misma identidad, aumenta `_load_generation`, cancela/invalida
carga inicial y página pendiente, y restablece el estado de la nueva carga.
Resultados y errores que sobreviven a la cancelación se descartan. El finally
antiguo no limpia el busy de una solicitud nueva. La actualización asíncrona
de contadores tiene el mismo guard de generación/identidad.

Los errores incrementales conservan las filas y el cursor para reintentar;
los errores iniciales mantienen el error y retry existentes. El callback de
retry conserva limit/offset explícitos. No se puede iniciar reproducción de
filas antiguas mientras se carga otra identidad ni después de cancelar esa
carga dejando el VM anterior.

El cursor, y no el videoId, evita duplicados por repetir una página. Un mismo
videoId en dos posiciones sigue apareciendo dos veces, también si una de las
ocurrencias cae al comienzo de otra página. Se prueba una colección real de
SQLite offline con 1005 canciones distintas y 1007 ocurrencias.

La rama remota mantiene el payload completo y su paginación del proveedor:
limit/offset no recortan artificialmente tracks remotos y load_more no envía
peticiones adicionales para esas identidades. `isLocal` conserva su significado
previo de descarga `local_`; no se confunde con las otras colecciones locales.

Pruebas rojas iniciales: 16 fallos. Antes del commit se reprodujeron además
3 fallos de carga/retry/contadores tardíos y 1 de cancelación dejando filas
anteriores. Los cierres posteriores cubren refresh de la misma identidad y
contadores agregados, con regresión roja del denominador ficticio. Batería B
final: 23 casos.

## REC-04.1.4 — D6 / D7

D6: `collection_identity.py` centraliza los namespaces reservados y la política
de descarga. El comando acepta IDs opacos ASCII del proveedor; rechaza URLs,
rutas, vacíos, formas codificadas y namespaces locales incluso malformados.
También examina el ID efectivo después del prefijo VL que el cliente elimina.
El ID remoto original se mantiene al llamar al cliente.

El wrapper valida antes de programar una coroutine y el método async valida
antes de mensajes, notificaciones o acceso al proveedor/repo/gestor. El rechazo
es limpio, sin tareas ni estado de descargas. No se exige una allowlist nueva
de prefijos de YouTube que rompa IDs remotos ya admitidos por el cliente.
La clasificación de namespace se comparte con el modo de paginación; no
sustituye la validación estricta de rutas offline de REC-04.1.2.

Pruebas D6: 17 fallos / 6 pases antes del cambio; 23 pases después. Se comprueba
la ausencia de llamadas a YouTube y tareas para todas las formas locales.

D7: no hay consumidor activo en producto para guardar sesiones. El servicio
`save_as_playlist()` permanece byte a byte igual a la base, no idempotente y
con sus transacciones intactas. No se introduce un lock decorativo. El punto
de futura protección, contrato de operación única y matriz de pruebas están en
[REC043-SAFETY.md](REC043-SAFETY.md). Estado: auditado y especificado, guard de
UI diferido a su consumidor futuro; no se afirma que esté implementado.

## Riesgos residuales y alcance verificado

- La reproducción usa el rango cargado en el momento de Play/Shuffle/fila.
  Añadir páginas después no modifica una cola que ya está reproduciendo.
  La futura UI todavía debe conectar la carga incremental; no se declara
  una funcionalidad visual nueva ni verificada por los smokes.
- La paginación es por offset sobre datos visibles, no un snapshot transaccional
  entre páginas. Cambios concurrentes de biblioteca, reglas temporales o
  disponibilidad pueden mover posiciones; se debe recargar tras esos cambios.
  No se inventa una deduplicación por videoId que destruya ocurrencias reales.
- Los archivos se revalidan, pero pueden desaparecer o fallar después; siguen
  los fallos/skips/fallback del reproductor. No se garantiza acceso físico a
  un archivo únicamente por una bandera persistida.
- D7 y la UI incremental no están conectados todavía. No se inicia REC-04.2
  ni REC-04.3 en esta unidad.
- Los probes Docker heredados tienen un falso positivo conocido por chmod de
  un montaje :ro. Se propone una reparación aislada con pipefail y smoke real
  en [REC043-SAFETY.md](REC043-SAFETY.md). No se certifica compatibilidad Docker
  con esas marcas PASS, ni se mezcla la reparación con D2/D6.
- Tests con SQLite/filesystem temporales y red/VLC simulados; smokes de bundle
  con el alcance que indiquen sus logs. No equivalen a verificación visual ni
  a audio real audible. Publicación pública bloqueada por licencias.

No hay cambios de QML, esquema, migraciones o Rust. Sin merges, tags, releases
ni publicación pública. Los ocho árboles previos conservan HEAD y porcelain
completos, incluidos Rescate y los no seguidos de REC-03A; el trabajo se escribe
solo en el worktree nuevo. Resultados, commits y CI: [REC043-RESULTS.md](REC043-RESULTS.md).
