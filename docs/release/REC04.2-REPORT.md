# REC-04.2 — Playlists funcionales

## Base y alcance

Base exacta: `96f3a455beec7dc725463b3999207ad04fe09060`, rama
`recovery/rec04-ci-hardening`, [PR #16](https://github.com/Eirom16/Doremi-Rust/pull/16).
Su [CI final 40109946499](https://github.com/Eirom16/Doremi-Rust/actions/runs/40109946499)
fue comprobado completed/success antes de crear este worktree. Incluyó Docker
22.04 y 24.04 reales, negativo exit=42, JSON estricto y ausencia de VLC del sistema.

Trabajo aislado en `worktrees/rec042-ui-playlists`, rama
`recovery/rec04-ui-playlists`, apilada sobre CI-HARDENING. No se reescribe REC043.

## B1: paginación y representación

El Repeater anterior creaba una fila por ocurrencia. Antes de habilitar listas
extensas se midió el componente real en procesos separados: con 1.007 filas,
10.641,13 ms y 526.208 KiB de RSS incremental. La solución es un único ListView
con el hero como header y el estado/paginación como footer. Mantiene el scroll,
mini-player, filas, menú contextual, botón Atrás y estilos existentes; no exige
cambiar la navegación ni el diseño general. Activa reuseItems y cacheBuffer=144.

«Cargar más» aparece solo para namespaces locales con hasMore, reclama busy
sincrónicamente y llama al load_more() existente. Loading deshabilita el control;
un error conserva filas y ofrece reintento de la misma página. El VM conserva
pageLimit/pageOffset, loadedCount, totalCount y las señales append existentes.
La paginación remota continúa siendo responsabilidad del proveedor, sin botón
local ni solicitudes artificiales. Un total desconocido se presenta como
«canciones cargadas», sin inventarlo a partir de la página.

No se deduplica por videoId: cada ocurrencia conserva su posición. Los controles
de generación y de página de REC043 siguen rechazando páginas repetidas y
resultados tardíos. Añadir filas no reemplaza la cola ya en reproducción. Una
selección posterior puede reproducir una fila añadida con local_path y contexto
REC041. Los menús se cierran al reciclar una fila. Una carga primaria cierra las
confirmaciones antiguas, incluso cuando se recarga la misma identidad, evitando
que un índice de eliminación antiguo se aplique a una lista nueva.

## B2: operación única D7

Se añade el consumidor real «Guardar como playlist» para identidades session
válidas (IDs positivos ordenados y cutoff interpretable según el servicio).
El diálogo existente de Qt Quick/Dialog/HeaderButton permite introducir título;
botón, Enter y accesibilidad usan el mismo slot del VM y el mismo boundary
sincrónico del controlador.

_request_save_session valida identidad/título/estado, captura
(first_id,last_id,cutoff,title), activa _save_busy y publica el estado ANTES de
programar la coroutine. Un segundo evento no crea otra tarea. La operación vive
en PlaylistScreenQml, fuera de las tareas de carga que cancela la navegación.
Guardar otra sesión también espera a que termine la operación actual.

El controlador posee la tarea de escritura y espera mediante asyncio.shield.
Cancelar el waiter de UI no cancela la escritura ni libera busy: se espera la
misma tarea, sin repetir el comando. MainWindow.async_shutdown espera la
operación antes del cleanup y del cierre de DB. Navegar no cancela, reinicia ni
libera el guard. Los resultados solo se publican para la identidad de origen;
al volver se recupera el resultado o el busy todavía vigente.

Éxito muestra el resultado y permite abrir la identidad local-list: mediante la
navegación existente. Al terminar se permite un nuevo guardado intencional, que
crea otra playlist. Un error muestra «No se pudo confirmar el guardado. Revisa
tus playlists antes de guardar de nuevo.» No hay reintento automático, incluido
el caso donde el commit ocurrió pero la respuesta no pudo confirmarse.

ListeningPeriods.save_as_playlist permanece byte a byte idéntico a la base:
no cambia su no idempotencia, compensación ni sus dos transacciones. D7 queda
implementado en el boundary activo de UI, sin lock decorativo en el servicio.

## Contratos añadidos

- VM: isLocalCollection, playlistId, isSession; saveBusy, saveError,
  savedPlaylistId, saveMessage; slots load_more(), save_session(title),
  open_saved_playlist() y señales correspondientes. Los contratos antiguos
  de carga/modelo siguen vigentes, sin modificar PlaylistTrackModel.
- PlaylistScreenQml: argumento opcional keyword-only on_navigate; boundary de
  paginación y guard de guardado; finish_session_save_for_shutdown().
- collection_identity.session_identity(): validación sin consultas ni red.
- QML: ListView y controles accesibles de paginación/guardado/resultado.
- CI: filtros de todos los archivos nuevos y artefacto siempre intentado con
  capturas reales de interacción y métricas de delegados.

## Pruebas y rendimiento

Ver REC04.2-RESULTS.md y REC04.2-PERFORMANCE.json. Las pruebas instancian
PlaylistScreen.qml en QQuickWidget y pulsan controles reales mediante QTest,
teclado y QAccessible. Usan SQLite y archivos sintéticos temporales, sin VLC
real ni datos del usuario. Se revisaron visualmente las capturas de lista,
diálogo, busy y éxito; no se sustituye interacción por un smoke de arranque.

Con ListView, la muestra fría comparable de 1.007 filas crea 8 delegados,
306,44 ms y 44.364 KiB; 10.007 filas también crea 8 delegados, 298,57 ms y
44.320 KiB. La prueba de scroll a la última fila mantiene la asignación acotada
(8 iniciales/17 finales). La carga del modelo sigue siendo proporcional a las
filas cargadas; se evita crear miles de componentes QML simultáneamente.
Son muestras de este host offscreen/software, no un SLA de tiempo ni prueba de
FPS en otros equipos. El gate reproducible de CI verifica cotas de delegados.

## Riesgos y límites

- Una terminación abrupta del proceso o pérdida de energía puede dejar resultado
  incierto: el servicio sigue sin clave idempotente ni transacción global.
  La UI informa y exige revisar las playlists; no repite automáticamente.
- La paginación por offset no congela una colección modificada externamente
  entre páginas. No se introduce un snapshot persistente ni se elimina una
  ocurrencia legítima para ocultar esa limitación heredada.
- Solo se guardan resultados de la operación más reciente en este controlador;
  no se añade registro persistente de operaciones ni experience_events.
- Pruebas offscreen de interacción y capturas sintéticas; no se afirma audio
  audible ni verificación manual con YouTube o música real.
- No se cambian modelos DB, migraciones, Rust ni transacciones. Sin merges,
  tags, releases o publicación pública; licencias pendientes. No REC-04.3,
  Home personalizado ni estadísticas.
