# Doremi Product Experience

## Implemented

- El historial conserva el origen de cada intento de escucha y la posición final. La cola transporta ese origen incluso al reordenarse o restaurarse.
- Acceso rápido en la barra lateral con pins persistentes, orden manual, carátulas y ranking por uso reciente. Los cambios de colección se notifican sin reiniciar.
- Inicio combina secciones personales (continuar, acceso rápido, sesiones y colecciones inteligentes) con el feed de YouTube Music; omite secciones vacías. Las tarjetas remotas reutilizan MediaCard, con Play y More independientes. Play carga y reproduce la colección; esa orden no queda guardada en Back.
- Seis playlists inteligentes locales: En repetición, Últimamente, Favoritas, Descubrimientos, Olvidadas y Descargadas.
- Estadísticas por calendario local (hoy, semana, mes, año, todo), sesiones musicales separadas por inactividad y resumen mensual/anual basado en el historial.
- Biblioteca local importable, búsqueda local, playlists locales mixtas y reproducción offline. Los archivos locales no se envían a las operaciones remotas de YouTube Music.
- Menús compartidos de canción y colección, controles de Me gusta/volumen/menú en MiniPlayer, restauración de estado de navegación, arrastre de pistas a cola o playlist, reordenación de cola/pins e importación por drop. Favoritos y disponibilidad offline actualizan las filas sin reiniciar sus modelos. Los pins tienen feedback optimista con reversión ante un fallo de persistencia.
- La sección de playlists de sidebar tiene scroll independiente del botón de contraer. Las notificaciones de descargas utilizan el panel QML vigente y conservan la acción VER del toast. Los diálogos locales tienen ancho acotado; las tarjetas muestran fallback de artwork fallido y evitan repetir la misma URL durante cinco minutos (hasta 128 URLs por motor QML).
- Paleta de comandos con Ctrl+K y atajos de reproducción; referencia en Ajustes.
- Filtros compactos compartidos (`FilterSelect`): tipo/estado en Descargas y período en Estadísticas, sincronizados con el ViewModel y accesibles por teclado. Wrapped reúne sus acciones mensual/anual en un menú de generación de resumen.

## Architecture

`PlayHistory` es la fuente de verdad de hábitos. `QueueItem` lleva origen hasta `PlaybackController`; `ListeningSession` mide el intento y el repositorio persiste un evento al terminar. `ExperienceRepository` consulta agregados acotados para Inicio, smart playlists, estadísticas y pins. `HomeComposer` prioriza y deduplica; `ListeningPeriods` deriva sesiones sin duplicar eventos. Los viewmodels exponen estado; QML solo presenta e invoca acciones. Las playlists locales usan `LocalLibraryRepository` y el selector QML `DesktopController`.

Las acciones comunes pasan por `track_actions`, que emite intenciones hacia los controladores existentes y bloquea operaciones remotas sobre IDs locales. Los menús de colección preservan el orden al insertar un lote como siguiente. Se reutilizan metadatos conocidos antes de consultar el extractor. Los eventos solo invalidan o notifican cambios confirmados; no son otra base de datos. Importar o añadir lotes verifica IDs en consultas de hasta 500 candidatos, sin una consulta por pista. La disponibilidad comprueba únicamente candidatos visibles y realiza la inspección de archivos fuera del hilo UI.

Se adelantaron las colecciones locales al arrastre y al guardado de sesiones para compartir el mismo repositorio, en vez de crear tres mecanismos distintos.

## Data model changes

- `20260929_0003`: `play_history.position_ms`, índice `(context_type, context_id, played_at)` y tabla `collections` para metadatos/pins (`pinned_at`, `position`). El contexto existente en historial se reutiliza; no se añadió otra columna de título al historial.
- `20260929_0004`: `songs.local_path` y `local_playlist_tracks` ordenada. Los IDs locales derivan de la ruta del archivo; la lista local puede contener IDs remotos.
- Ambas migraciones conservan el historial anterior. El test de upgrade empieza desde `20260926_0002` y comprueba los datos originales.

## Smart playlist rules

- En repetición: solo intentos válidos de los últimos 30 días; cada intento aporta 2 puntos, hasta 5 por minutos escuchados y hasta 1 por escucha/duración real. Un salto o buscar hasta el final no fabrica afinidad.
- Últimamente: último intento válido más reciente primero.
- Favoritas: canciones marcadas como Me gusta.
- Descubrimientos: primer intento válido en los últimos 30 días y afinidad de al menos 3 puntos.
- Olvidadas: al menos 3 escuchas válidas y ninguna en 60 días, ordenadas por frecuencia histórica.
- Descargadas: archivo descargado o importado que todavía existe en disco.

Las colecciones virtuales muestran hasta 100 candidatos por consulta; no se presenta este límite como el tamaño completo de la biblioteca.

## Home ranking rules

Las secciones personales preceden al feed remoto. Se conservan primero sus candidatos y después se deduplican pistas o rutas entre secciones, tiles, spotlight, rails y canciones. Las órdenes transitorias de continuar o reproducir no cambian la identidad de una colección. Límites: seis elementos por sección personal, seis tiles, un spotlight, 45 elementos horizontales y 16 canciones. Los tiles limitan a dos pistas por crédito de artista si hay alternativas, y rellenan con las restantes si no las hay. Si no hay datos personales, el feed remoto permanece. Offline se filtran colecciones y pistas reproducibles, y no se solicitan categorías remotas.

Explore fusiona hasta ocho categorías de `get_explore().moods_and_genres` con categorías estables de Doremi, deduplicadas sin distinguir acentos. Sus botones buscan el nombre de la categoría; no se presentan como recomendaciones derivadas de géneros del historial.

## Sidebar ranking

Hasta seis playlists en la barra lateral y en Inicio: pins primero por `position`, después reproducciones válidas y recencia de los últimos 90 días, con título como desempate. Si no hay playlists, la barra muestra un acceso a Biblioteca. La tabla de colecciones ya admite álbumes y artistas, pero no se exponen como pins antes de tener acciones específicas para ellos. La reordenación exige el conjunto exacto de pins vigente, evitando que un drop obsoleto sobrescriba el orden.

Reproducir una sesión musical no la convierte en una playlist del usuario: se excluye del ranking de sidebar y top playlists. Guardarla como playlist crea una colección local normal.

## Continue Listening rules

Se consideran playlists, álbumes y playlists inteligentes usados en los últimos 14 días. Gana el último intento por fecha e ID de desempate, no el orden de importación. Un intento inválido o saltado no invita a retomar una escucha anterior. La tarjeta vuelve a la colección y conserva pista/posición cuando el intento está incompleto y no fue un salto; si terminó, avanza dentro de esa colección. Si era la última pista, abre la colección sin repetirla. No se muestra un progreso `n / total` porque el historial no demuestra que se hayan escuchado todos los elementos de la colección. Es independiente de restaurar la reproducción al iniciar.

## Keyboard shortcuts

Espacio: reproducir/pausar; Ctrl+K: paleta; Ctrl+F: búsqueda; Ctrl+→/Ctrl+←: siguiente/anterior; L: Me gusta actual; Ctrl+P: reproducción actual. Los atajos musicales no se ejecutan mientras se escribe en un editor.

## Known limitations

- El resumen Wrapped es textual; exportar una imagen compartible queda para un renderer posterior sobre el resultado de `Wrapped.summary`, sin añadir dependencias gráficas a las consultas. La UI genera el mes/año actual; el servicio admite otros períodos, pero aún no hay selector histórico.
- Las sesiones se infieren con una brecha de 30 minutos entre intentos válidos, no con una entidad persistida. Sus horas son aproximadas a partir de eventos, no una medición continua de inicio y fin. Las tarjetas se limitan a 90 días y su ruta conserva ese límite. Una tarjeta de la sesión actual sigue funcionando si se añaden nuevas escuchas a ese período; no es un snapshot inmutable.
- Las acciones remotas, carátulas, metadatos y categorías de YouTube Music dependen de conexión/autenticación. La afinidad por género se aplaza porque el historial no tiene una taxonomía fiable; no se inventan géneros a partir de títulos.
- Descargas conserva sus menús específicos de pausa/reintento/cancelación. Detalles/créditos solo aparecen donde existe su carga de datos. Las tarjetas de colecciones todavía no cargadas no ofrecen añadir un lote a la cola: abrir/reproducir carga primero la colección; su pantalla sí permite esa acción.
- No hay preferencia global de movimiento reducido: las APIs de QStyleHints/QAccessibilityHints instaladas no exponen esa preferencia. Las animaciones nuevas son breves y usan los tokens existentes.
- El porcentaje real se conserva en Descargas y cabeceras de colección. No se propaga cada actualización del downloader a todas las tarjetas: estas reflejan disponibilidad confirmada. El contrato existente de pausa/error/cancelación no se sustituyó por otra máquina de estados.
- El importador reconoce `.mp3`, `.flac`, `.ogg`, `.opus`, `.m4a` y `.wav`; no escanea carpetas de forma recursiva ni analiza etiquetas embebidas. Usa el nombre del archivo y permite reproducir/registrar la pista sin un parser adicional.
- Las estadísticas cuentan los créditos textuales de artista almacenados, no entidades individuales desambiguadas en colaboraciones. Se excluyen vacíos y placeholders conocidos. La escucha media es tiempo realmente escuchado/duración, no avance obtenido mediante seek.

## Manual verification

Los tests automatizados cubren contexto y apariciones duplicadas de cola, upgrade desde 0002 con datos conservados, ranking/pins/rollback, deduplicación/diversidad, smart playlists, períodos estadísticos, sesiones importadas y límites temporales, colecciones locales mixtas y operaciones atómicas, disponibilidad real de archivos, navegación y autoplay transitorio, comandos, foco/flechas/Escape/Enter de la paleta, bindings dark/light y compilación de 19 componentes QML. También se instancian sidebar y diálogos para verificar geometría, acceso por teclado al botón de contraer y ausencia de warnings al abrir los diálogos. Los desplegables se prueban con teclado, cambios programáticos de filtro, apertura/cierre y colores de control/popup en ambos temas. Las regresiones de descarga comprueban encolado, notificaciones y acción VER con servicios simulados, no transferencias externas.

Suite completa verificada: **481 tests aprobados**. También pasan `compileall` y `git diff --check`.

El 3 de octubre de 2026 se arrancó la aplicación offscreen con configuración/datos/cache temporales: cargaron las pantallas QML y el shell sin errores QML, con VLC detectado y MPRIS registrado. El proceso se detuvo mediante timeout tras el arranque; no se probó reproducción real. El llavero de autenticación no estaba aislado, por lo que este smoke no demuestra funcionamiento sin credenciales. Durante el último arranque el caché automático intentó descargar audio y recibió HTTP 403 de YouTube: el arranque correcto no acredita descargas externas satisfactorias.

Pendiente verificar en escritorio real: apariencia y navegación visual, drops con gestor de archivos, reordenación mediante gesto, feed y descargas externos, comportamiento dark/light/system del entorno y reproducción VLC de los seis formatos. Los tests no se presentan como validación de esos servicios ni gestos.
