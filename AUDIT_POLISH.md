# Doremi Functional & Polish Audit

## 1. Executive Summary

**Estado de la auditoría inicial:** se ejecutó el suite completo con `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests -q`: **304 passed**. El resultado era una buena base de regresiones unitarias, pero no demostraba que las funciones visibles cumplieran su promesa de extremo a extremo.

Se confirmaron **0 bugs Critical, 8 High, 8 Medium y 3 Low**. Hay **21 features fantasma o parcialmente implementadas** entre 42 preferencias/configuraciones rastreadas. Los riesgos más graves para una release son: navegación Back que no conserva rutas profundas, acciones de cola que pueden borrar una descarga en lugar de retirar una canción de la cola, métricas de escucha incorrectas, y varias acciones “Añadir a playlist” que envían la miniatura como título.

La UI QML activa usa correctamente `ThemeBridge` para sus colores generales y los principales flujos tienen loading básico. La migración, sin embargo, dejó código QtWidgets duplicado y controles QML hechos como `Rectangle + MouseArea` que no reciben teclado, foco ni nombre accesible.

| Métrica | Resultado |
|---|---:|
| Bugs confirmados | 19 |
| Critical / High / Medium / Low | 0 / 8 / 8 / 3 |
| Features fantasma o parciales | 21 |
| Bugs con pruebas relacionadas existentes | 5 |
| Bugs con una prueba de regresión que falle hoy | 0 |
| Nuevas pruebas de regresión necesarias | 19 |

**Límites de evidencia:** no hubo una sesión gráfica real ni cuenta YouTube/Discord/Last.fm disponible. Los bugs descritos como confirmados se derivan de flujos ejecutables y de rastrear la señal hasta su efecto; los hallazgos visuales de contraste y accesibilidad se limitan al QML activo y deben rematarse con una pasada manual en light/dark, lector de pantalla y red real.

## Implementation Status (2026-09-27)

Esta auditoría pasó a fase de corrección. Los hallazgos siguientes ya tienen
cambio de producto y pruebas de regresión focalizadas: BUG-001 a BUG-016,
excepto la cobertura manual de red/VLC real; BUG-018 se resolvió para blur,
proxy y calidad de stream, y las opciones de normalización, silencio, gapless,
color dinámico, interlineado y estilo de animación se retiraron de la UI porque
no existía motor que las pudiera cumplir. BUG-019 queda resuelto para la
sidebar compacta; el tamaño global de fuente sigue siendo una clave de
compatibilidad no expuesta en la UI.

La semántica de `stop_on_close` también invalida y cancela una extracción
pendiente antes de detener VLC: sin esa invalidación una pista podía comenzar
después de ocultar la ventana. La regresión se cubre en
`test_stop_on_close_cancels_pending_play_request`.

También se añadieron estados de error/reintento para Home, Biblioteca,
Playlist, Álbum y Artista; controles de ciclo de vida de descargas; feedback
de creación de playlist; y foco/nombres accesibles en SongRow, MediaCard y el
mini reproductor/controles principales de Now Playing y Header. El límite de caché
offline ahora poda los archivos existentes al reducirse. MPRIS se expone en
Ajustes y se inicia/detiene sin reiniciar. Last.fm y Discord se retiraron por
completo del producto (UI, configuración, credenciales, controladores,
callbacks, dependencias y pruebas), por lo que ya no se intentan conectar
durante el arranque. Proxy, calidad de stream y precarga están expuestos en
Ajustes y ya afectan al extractor/reproductor. La confirmación
de borrar descargas se migró de `QMessageBox` a `ModalDialog` QML. Dentro del
sandbox, `aiosqlite` no despierta el event loop tras su worker y bloquea las
pruebas de base de datos; se reprodujo como un límite de infraestructura. La
misma suite se ejecutó fuera del sandbox y cerró correctamente con **384
passed en 11,96 s**, por lo que no queda una prueba funcional pendiente por
ese síntoma.

`ModalDialog`, usado por las confirmaciones activas, recibió foco por tab,
Enter/Espacio, nombres accesibles y anillo de foco en cerrar/cancelar/confirmar.
Home, la cola y Similares de Now Playing recibieron la misma semántica: cada
fila y tarjeta se puede activar con Tab + Enter/Espacio, los menús se abren con
Menu o Shift+F10 y los movimientos de cola deshabilitados comunican el límite
correcto. El hero dejó de prometer reproducción cuando sólo podía abrir el
álbum o playlist destacado; ahora ofrece una única acción **Abrir**. También
se corrigió el icono de Play de las filas de Home, que era blanco sobre fondo
transparente al aparecer por hover y podía resultar invisible según el tema.

**Lectura de las secciones históricas:** las fichas BUG-001 a BUG-019 y la
tabla de la sección 3 describen el estado encontrado al inicio; no son la
lista de pendientes actual. Para que otro agente pueda retomar el trabajo sin
reinvestigar, el estado vigente es:

| Área | Estado posterior a la corrección | Evidencia automática |
|---|---|---|
| Navegación, rutas y Back | Corregido, incluida invalidación de resoluciones artist/album lentas | `test_controllers.py`, `test_audit_regressions.py` |
| Cola, shuffle, duplicados y quitar de cola | Corregido, incluida la primera inserción en cola vacía | `test_queue.py`, `test_now_playing_qml.py` |
| Historial y estadísticas de escucha | Corregido, con migración validada | `test_audit_regressions.py`; upgrade Alembic SQLite desde baseline |
| Descargas y reconciliación DB/archivo | Corregido, incluida navegación de tarjetas de colección y registros externos obsoletos en vistas de grupo | `test_downloads_qml.py`, `test_audit_regressions.py`, `test_offline_cache.py` |
| Settings con efecto runtime | Corregido para blur, compact sidebar, stop-on-close, proxy/calidad/precarga, integraciones, MPRIS, caché offline y las cinco preferencias de letras aún visibles | `test_settings_qml.py`, `test_controllers.py`, `test_offline_cache.py`, `test_now_playing_qml.py` |
| Cola y posición tras reinicio | Corregido: la cola se restaura sin autoplay; `resume_on_startup` controla sólo reproducir/seek | `test_controllers.py` |
| Preferencias sin motor | Retiradas de la UI QML; claves legacy preservadas para QtWidgets | inspección de Settings QML |
| Carga/error/retry y acciones principales | Corregido en las pantallas activas auditadas | pruebas QML focalizadas |
| Accesibilidad de componentes compartidos y reproductor | Corregido en SongRow, MediaCard, EmptyStateView, MiniPlayer, Home, cola y controles principales de Now Playing | `test_audit_regressions.py`, `test_home_qml.py`, `test_now_playing_qml.py` |
| Tema claro/oscuro y contraste de acciones accent | Corregido: `text_on_accent` se elige por ratio WCAG y hover oscurece, no aclara, el fondo con texto/icono | `test_audit_regressions.py` |
| Tema del sistema | Corregido: se usa `QStyleHints.colorScheme()` multiplataforma y se observa su cambio | `test_audit_regressions.py` |

La última pasada integrada en este árbol ejecutó **385 passed en 12,87 s**:
incluye las regresiones de auditoría, controllers, base de datos y
migraciones, settings, Now Playing/MiniPlayer, Library, Downloads, cola/cache
offline, rutas QML, Search/Header, notificaciones, detalle, Stats y Home. Las
tres pruebas que el sandbox bloqueaba por `aiosqlite` también pasan en esa
ejecución; no hay exclusiones de cobertura en la validación final.

Se verificó además el recorrido real YouTube → extractor → VLC con una pista
remota: URL M4A válida, estado `PLAYING` y avance de posición, a volumen cero
y con liberación limpia. Siguen necesariamente manuales/externas las cuentas
de Last.fm/Discord, crossfade/EQ sostenido y una pasada visual con lector de
pantalla en light/dark. No deben marcarse como bugs abiertos sin esa evidencia.

En una sesión KDE/Wayland real se inició además Doremi con directorios XDG
temporales y se consultó `org.mpris.MediaPlayer2.doremi` por DBus: el servicio
se registró y devolvió `PlaybackStatus=Stopped`. El aviso de portal que puede
verse al ejecutar desde el árbol fuente depende del registro desktop del
sistema (no existe en el XDG temporal); no invalida el servicio MPRIS ni se
reproduce como un error de código QML.

La misma ejecución aislada se capturó visualmente en tema oscuro y tema claro
con el acento por defecto: Home en `LOADING`, sidebar, iconos, barra de
búsqueda y foco activo se renderizan de inmediato y no mostraron texto/iconos
invisibles ni contraste insuficiente evidente. Es evidencia de arranque y
themado real; no sustituye la revisión manual de cada pantalla con contenido
remoto, lector de pantalla y estados de error.

Con red real, Home también completó su carga en la sesión gráfica y mostró
destacado, canciones, playlists y recomendaciones. Un extractor de un medio
aislado devolvió el error transitorio de proveedor “The page needs to be
reloaded”, pero no bloqueó ni vació el feed visible; la reproducción concreta
mantiene sus rutas de error/reintento documentadas arriba.

Como comprobación separada de reproducción real, se extrajo una URL M4A de una
de esas canciones, se abrió con VLC a volumen cero y se observó estado
`playing` con posición creciente. La misma pista que había provocado el aviso
transitorio pudo comenzar normalmente, por lo que no hay evidencia de una
regresión sistemática de extractor o motor.

Finalmente, un escenario aislado de `MainWindow` ejecutó la secuencia completa
de inicialización (directorios, migraciones, QML, MPRIS y controlador), inició
una pista remota y verificó simultáneamente que VLC avanzaba, MiniPlayer tenía
el título/estado `playing` correcto y Now Playing tenía el mismo título/estado.
La cola automática también se pobló durante el mismo recorrido. Se conserva
como smoke manual de integración porque depende de YouTube/VLC/DBus reales.

### Correcciones descubiertas durante el remate de release

| ID | Hallazgo confirmado inicial | Corrección aplicada | Prueba |
|---|---|---|---|
| BUG-025 | El CTA “Reproducir” del hero navegaba siempre a un álbum/playlist porque el spotlight no tiene `videoId`; el CTA “Explorar” hacía exactamente lo mismo. | Se elimina la duplicación y el CTA pasa a llamarse “Abrir”, con navegación por teclado y nombre accesible. | Carga QML: `test_home_qml.py` |
| BUG-026 | El icono Play de una fila de Home quedaba `text_on_accent` (blanco) mientras su fondo seguía transparente cuando sólo se hacía hover sobre la fila. | El icono usa `text_primary` hasta que el botón recibe hover y pinta su fondo accent; entonces usa `text_on_accent`. | Carga QML: `test_home_qml.py` |
| BUG-027 | Las filas de cola, Similares y tarjetas Home eran activables sólo con `MouseArea`; subir/bajar no exponía estado disabled a tecnología asistiva. | Se añadieron foco, roles, nombres, atajos Enter/Espacio y menú contextual; los extremos de reordenación quedan deshabilitados semánticamente. | `test_now_playing_qml.py`, `test_queue.py`, `test_home_qml.py` |
| BUG-028 | Filas de canción de Album/Playlist/Artist y tarjetas de álbum/artista relacionado sólo respondían al ratón. | Se añadió foco, nombre/rol y activación por Enter/Espacio; las filas exponen su menú con Menu o Shift+F10. Los CTAs propios de Artist respetan disabled y teclado. | `test_album_qml.py`, `test_artist_qml.py`, `test_playlist_qml.py` |
| BUG-029 | La acción de un toast era sólo un `MouseArea`; además, el foco de “Abrir artista” de una notificación estaba en el título de la canción, no en el artista que se abría. | Toast expone botón accesible y Enter/Espacio. El enlace accesible, foco y atajos se mueven al label del artista real. | `test_notification_qml.py`, `test_qml_only_routes.py` |
| BUG-030 | ComboBox, sliders, inputs y botones ± de Ajustes dependían de su texto visual —o del glifo `+`/`−`—; además, los extremos del stepper aceptaban foco aunque no podían cambiar valor. | Se añaden nombre/descripción accesibles por setting, nombres contextuales a `HeaderButton` y disabled real en los límites del stepper. | `test_settings_qml.py`, `test_audit_regressions.py` |
| BUG-031 | Now Playing y MiniPlayer anunciaban el título como un enlace al artista, pero el control que abría ese artista era el label distinto; el seek principal tampoco tenía nombre/posición para tecnología asistiva. | El foco y semántica se sitúan en el artista visible de cada reproductor; el seek describe posición actual y duración total. | `test_now_playing_qml.py`, `test_mini_player_qml.py`, `test_audit_regressions.py` |
| BUG-032 | La caché offline automática mandaba la cookie del llavero como header a yt-dlp; versiones actuales pueden rechazarla y dejar el feed sin audio, registrándolo sólo en logs. | Si esa descarga autenticada falla, se borran parciales y se reintenta sin Cookie, preservando user-agent. El manifiesto sólo recibe audio completado. | `test_offline_cache.py::test_download_track_retries_without_rejected_cookie_header` |
| BUG-033 | `sleep_timer_minutes` se persistía y la UI lo mostraba seleccionado tras reiniciar, pero ningún contador se iniciaba hasta cambiar otra vez la opción. | `SettingsController.restore_persisted_sleep_timer()` inicia un intervalo nuevo y explícito al crear MainWindow, sin inventar tiempo transcurrido. | `test_controllers.py::TestSettings::test_persisted_sleep_timer_starts_on_new_window` |
| VER-001 | Las preferencias de letras restantes podían parecer decorativas al no existir una prueba del trayecto Settings → ViewModel → QML. | Se verificó que tamaño, alineación, glow, auto-scroll y delay llegan al ViewModel; el delay modifica el cálculo de la línea activa y auto-scroll/glow se consumen en `NowPlayingScreen.qml`. | `test_now_playing_qml.py::test_lyrics_style_is_observable_and_delay_changes_active_line`, `test_visible_lyrics_preferences_are_applied_on_create_and_update` |
| BUG-034 | `resume_on_startup=False` impedía llamar incluso a `restore_playback_session()`: la cola, la pista actual y la posición se perdían tras reiniciar. | La restauración de cola es independiente del autoplay; la pista se muestra detenida y sólo `resume_on_startup=True` solicita reproducción y seek. | `test_controllers.py::TestSession::test_initialize_restores_queue_without_autoplay_when_resume_is_off` |
| BUG-035 | Al desactivar “Caché inteligente”, una sincronización automática ya iniciada seguía descargando/rotando archivos hasta completarse. | `OfflineCacheManager.cancel_sync()` cancela la tarea viva; Settings lo invoca al apagar la preferencia, sin borrar archivos ya disponibles offline. | `test_offline_cache.py::test_cancel_sync_stops_an_inflight_automatic_refresh`, `test_controllers.py::TestSettings::test_disabling_offline_cache_cancels_its_current_sync` |
| BUG-036 | La resolución asíncrona de artista/álbum podía terminar después de una nueva selección o navegación y abrir una pantalla obsoleta. | `NavigationController` usa un token de intención, cancela la resolución anterior y cancela una carga de ruta aún activa al iniciar una nueva resolución. | `test_controllers.py::TestNavigation::test_new_artist_resolution_cancels_an_older_slow_one`, `test_explicit_navigation_invalidates_a_slow_artist_resolution` |
| BUG-037 | La acción de `EmptyStateView` (incluido Reintentar) era un `Rectangle + MouseArea`: sin Tab, teclado, nombre accesible ni anillo de foco; además usaba `bg_base` como texto sobre accent. | Se añade semántica de botón, foco, Enter/Espacio y `text_on_accent`, de modo que todos los estados vacíos que reutilizan el componente quedan corregidos a la vez. | `test_audit_regressions.py::test_empty_state_action_supports_keyboard_and_accessible_focus` |
| BUG-038 | En tema claro, `text_on_accent` se forzaba a blanco según el tema, no según el color de fondo: con los acentos disponibles podía bajar hasta 1,67:1. Además, el hover aclaraba botones con texto, reduciendo aún más el contraste. | ThemeManager elige la tinta blanca u oscura por el mayor contraste WCAG del acento; los hover de botones con texto/icono se oscurecen (`Qt.darker`) y preservan ≥4,5:1 para todos los presets. | `test_audit_regressions.py::test_text_on_accent_uses_the_best_available_aa_contrast` |
| BUG-039 | El modo de tema `system` dependía de `gsettings`; fuera de GNOME podía caer siempre a oscuro y la cache `(system, accent)` impedía reaccionar a un cambio del sistema. | Se resuelve con `QStyleHints.colorScheme()` de Qt (con `gsettings` sólo como fallback) y se escucha `colorSchemeChanged`; la clave usa el modo efectivo claro/oscuro. | `test_audit_regressions.py::test_system_theme_uses_qt_color_scheme_before_gsettings` |
| BUG-040 | Añadir la primera pista a una cola vacía conservaba `_index=-1`; por tanto no había pista actual y Repeat One podía acceder a `queue[-1]`. | `add_next` y `add_to_end` establecen el índice 0 al crear la cola; `next_item` exige una pista actual antes de calcular repetición. No inicia audio por sí mismo. | `test_queue.py::test_adding_first_item_establishes_current_without_autoplaying`, `test_add_next_to_empty_queue_establishes_current_and_repeat_one_is_safe` |
| BUG-041 | Tras añadir la primera canción a una cola con VLC idle/error, Play/Pause invocaba `resume()` y no reproducía nada. | En IDLE o ERROR el control inicia `_play_current()`; `resume()` queda reservado para una pausa real. | `test_audit_regressions.py::test_play_control_starts_current_queue_item_when_vlc_cannot_resume` |
| BUG-042 | Previous en los primeros 3 s de la primera pista reiniciaba la misma entrada mediante `_play_current()`, pero antes la clasificaba como skip y creaba una sesión de escucha artificial. | En la primera pista Previous siempre hace seek a 0; en pistas posteriores conserva el salto y registro de skip. | `test_audit_regressions.py::test_previous_on_first_track_restarts_without_recording_a_skip`, `test_previous_before_three_seconds_on_later_track_marks_current_as_skipped` |
| BUG-043 | Next manual al final de una cola sin repeat/autoplay finalizaba la sesión como skip pero VLC seguía reproduciendo la misma pista. | Si no se pudo avanzar ni añadir autoplay y la solicitud fue manual, PlaybackController detiene explícitamente VLC. | `test_audit_regressions.py::test_next_on_last_track_stops_manual_playback_when_no_autoplay_exists` |
| BUG-044 | Las tarjetas de álbumes/playlists descargadas llamaban a `screenVm.navigate(...)`, método inexistente en `DownloadsViewModel`; click, teclado y lector de pantalla no abrían la colección local. | Todas las superficies de tarjeta invocan el slot real `group_navigate(index)`, que emite la ruta del modelo. | `test_downloads_qml.py::TestDownloadsScreenQml::test_group_cards_call_the_viewmodel_navigation_slot`, `TestDownloadsViewModel::test_navigate_groups` |
| BUG-045 | Sólo la lista de canciones reconciliaba registros cuyo archivo se eliminó fuera de Doremi; las pestañas de grupos seguían mostrando colecciones locales vacías. | `gather_download_groups()` valida el archivo y elimina el registro obsoleto igual que la lista de canciones. | `test_audit_regressions.py::test_download_group_listing_reconciles_records_for_deleted_files` |
| A11Y-001 | `HeaderButton` omitía estado visual disabled aunque los steppers de Ajustes ya impedían la operación en el límite. | El componente compartido reduce opacidad, usa `text_disabled` e inhabilita su `MouseArea`; foco y `Accessible.onPressAction` ya respetaban `enabled`. | `test_audit_regressions.py::test_header_button_has_a_visible_and_non_interactive_disabled_state` |
| BUG-046 | Los CTAs Play/Shuffle de Artist usaban la propiedad QML inexistente `screenVm.title` como nombre accesible. | Se sustituyó por `artistName`, propiedad publicada por `ArtistViewModel`. | `test_artist_qml.py::TestArtistScreenQml::test_play_ctas_name_the_actual_artist_for_accessibility` |
| BUG-047 | MPRIS reducía todo estado no PLAYING a Paused; al habilitarse durante una reproducción no publicaba la pista, posición, volumen ni estado existentes, y `Play` no podía iniciar una cola con VLC idle. | MPRIS recibe el estado completo y un snapshot al activarse; Play/Stop llaman los límites correctos de PlaybackController. | `test_controllers.py::TestIntegrations::test_enabling_mpris_publishes_the_current_playback_snapshot`, `test_mpris_receives_stopped_not_paused_when_player_is_idle`, `test_mpris_play_and_stop_use_playback_state_boundaries`, `test_audit_regressions.py::test_external_play_starts_a_queued_song_when_vlc_is_idle`, `test_external_stop_finalizes_listening_before_stopping_vlc` |
| BUG-048 | Restaurar una copia usaba `ZipFile.extractall()` y cerraba el motor DB antes de saber si el ZIP era válido. | Se acepta sólo `doremi.db`/`settings.toml` planos, sin duplicados/symlinks, se valida antes de `dispose()` y se copian archivos de forma atómica. | `test_backup.py::test_backup_restore_rejects_path_traversal_before_disposing_database` |
| BUG-049 | Activar Discord podía fallar por IPC sin que el usuario recibiera feedback; el toggle quedaba visualmente activo y el motivo sólo aparecía en logs. | `DiscordRPC` expone conexión efectiva y el cambio manual muestra aviso no bloqueante si no puede conectar; conserva reintento al reproducir. | `test_controllers.py::TestIntegrations::test_discord_toggle_reports_a_failed_manual_connection` |
| BUG-050 | El sistema de videoclip introducía un segundo reproductor y estados QML frágiles. | Retirado del producto el 2026-09-29; Now Playing vuelve a ser exclusivamente de audio. | Cobertura de rutas y controles de Now Playing conservada sin el subsistema visual. |

## 2. Confirmed Bugs

### BUG-001 — El historial y las estadísticas cuentan una canción antes de escucharla

**Severidad:** High

**Archivos:**

`src/doremi/ui/controllers/playback_controller.py:425,474,563,692`  
`src/doremi/db/models.py:31`  
`src/doremi/ui/screens/stats_data.py:34`

**Problema**

En cuanto VLC informa que inició la reproducción, `_play_current_request()` agenda `_save_play_history(item)`. Ese método inserta una entrada y llama `record_play()` sin esperar un umbral de escucha. La estadística suma después `PlayHistory.duration_ms`, es decir, la duración completa del audio, no el tiempo reproducido.

**Cómo reproducir**

1. Iniciar una canción de 5 minutos.
2. Saltar inmediatamente a otra pista o cerrar antes de escucharla.
3. Abrir Historial o Estadísticas.
4. La pista cuenta como reproducción y añade 5 minutos completos a “tiempo escuchado”.

**Causa raíz**

`_save_play_history()` se invoca en las ramas de éxito de local, stream precargado y stream nuevo. `PlayHistory` sólo tiene `duration_ms`; `gather_stats()` hace `sum(entry.duration_ms ...)`.

**Impacto**

Historial, top songs, artistas únicos, actividad diaria y tiempo escuchado pierden credibilidad. Un usuario que prueba muchas canciones ve estadísticas infladas.

**Solución recomendada**

Crear un registro de sesión de escucha al empezar, no una reproducción final. Persistir al pausar/cambiar/terminar/error con al menos `listen_time_ms`, `completion_ratio`, `completed`, `skipped`, `context_type` y `context_id`. Contar `play_count` sólo al superar una regla explícita (por ejemplo, 30 s o 50 %, coherente con Last.fm), y sumar `listen_time_ms` en estadísticas. No reutilizar `duration_ms` para tiempo escuchado.

**Test de regresión**

Simular 10 s de una pista de 300 s y un Next: debe guardar `listen_time_ms≈10_000`, `skipped=True`, `completed=False`, no incrementar play count. Simular fin natural y verificar `completed=True`, ratio cercano a 1 y una sola entrada aunque haya reintento de stream.

### BUG-002 — Back restaura el índice, no la ruta ni sus parámetros

**Severidad:** High

**Archivos:**

`src/doremi/ui/controllers/navigation_controller.py:248`  
`src/doremi/ui/controllers/playback_controller.py:911`  
`src/doremi/ui/main_window.py:58`

**Problema**

`NavigationController.set_stack_index()` guarda únicamente el índice de pantalla en `_nav_history`. `_go_back()` restaura ese índice directamente; no restaura `path`, query params, `_current_route` ni el estado de la vista.

**Cómo reproducir**

1. Abrir `Playlist A`.
2. Abrir `Playlist B`.
3. Pulsar Back.
4. Se muestra la misma pantalla Playlist con los datos que quedaron cargados para B; no se recarga A. También quedan desactualizados `activeRoute` y `_current_route`.

**Causa raíz**

La historia es `list[int]` y no contiene identidad de destino. El Back evita `NavigationController.navigate()` y por tanto evita `set_active()`, el parser de query y `load_screen_with_query()`.

**Impacto**

Falla cualquier retorno de ruta profunda: Home → Playlist A → Album → Back, Search → Playlist → Back, Artist → Album → Back y Now Playing → minimizar. Es una inconsistencia de navegación visible, no sólo de estado interno.

**Solución recomendada**

Reemplazar la pila por entradas inmutables como `{path, route, query, screen_state}`. Registrar la ruta completa antes de cada navegación y hacer que Back pase por un único método de restauración que actualice stack, `_current_route`, sidebar, mini-player y carga de la pantalla. No apilar una entrada cuando la navegación es una restauración.

**Test de regresión**

Cubrir exactamente: Playlist A → Playlist B → Back carga A; Home → Playlist A → Album X → Back carga A; Search con query → Playlist → Back conserva query; minimizar Now Playing restaura pantalla, sidebar y mini-player correctos.

### BUG-003 — Todas las playlists rápidas del sidebar aparecen activas a la vez

**Severidad:** High

**Archivos:**

`src/doremi/ui/controllers/navigation_controller.py:50`  
`src/doremi/ui/qml/Doremi/NavigationSidebar.qml:156-158`

**Problema**

Al navegar a una playlist, el controlador guarda `activeRoute = "playlist"`, no la ruta completa. Cada acceso rápido se considera activo si `activeRoute === "playlist"`, así que todas las playlists se resaltan simultáneamente.

**Cómo reproducir**

1. Tener dos o más accesos de playlist en el sidebar.
2. Abrir una de ellas.
3. Observar que todos los accesos de playlist tienen estado activo.

**Causa raíz**

La expresión del delegate mezcla un route completo (`playlist?id=…`) con un estado sin query (`playlist`).

**Impacto**

El sidebar deja de comunicar dónde está el usuario y contradice la selección visible.

**Solución recomendada**

Conservar `activePath` completo o un `activePlaylistId`; comparar el acceso rápido con esa identidad. Separar `activeSection` de `activePath` si se necesita iluminar la sección genérica sin seleccionar todas las filas.

**Test de regresión**

Montar tres rutas y verificar que sólo `playlist?id=B` es activa cuando la ruta actual es B, incluido después de Back y de navegación programática.

### BUG-004 — Una búsqueda con `?` se interpreta como navegación interna

**Severidad:** High

**Archivos:**

`src/doremi/ui/controllers/navigation_controller.py:36-39,221-227`

**Problema**

`on_search_submitted()` trata cualquier texto que contenga `?` como ruta y llama `navigate_to(query)`. Por ejemplo, `What Was I Made For?` se parte como route `What Was I Made For` y query vacío; como no existe esa route, termina en el índice Home. Además `load_screen_with_query()` usa `split("=", 1)`, sin decodificación ni parsing de pares.

**Cómo reproducir**

1. Buscar `What Was I Made For?` en el header.
2. Pulsar Enter.
3. En vez de resultados aparece Home (route desconocida resuelta al índice 0).

**Causa raíz**

El dato de usuario se usa como sintaxis de route. El parser artesanal tampoco distingue `&`, `=`, `%`, Unicode, hash o valores repetidos.

**Impacto**

Las búsquedas habituales con interrogación fallan; también son frágiles queries con `&`, `=`, `#`, `%`, emojis y navegación rápida entre categorías.

**Solución recomendada**

Separar APIs: `submit_search(query)` siempre construye `search?query=` con `urllib.parse.urlencode`; deep links sólo proceden de sugerencias tipadas. Parsear rutas con `urlsplit/parse_qs` (o una estructura de route interna equivalente), validar la route contra `ROUTES`, y preservar la cadena decodificada para la búsqueda.

**Test de regresión**

Parametrizar `What Was I Made For?`, `a&b=c`, `100%`, `#tag`, emoji, Unicode, espacios y una cadena larga. Todos deben llegar una vez a `search_screen.search()` con el texto idéntico. Añadir carrera: query A lenta, query B rápida, y B es la única visible.

### BUG-005 — “Quitar de la cola” intenta borrar una descarga y no retira la fila

**Severidad:** High

**Archivos:**

`src/doremi/ui/qml/NowPlayingScreen.qml:668-681`  
`src/doremi/ui/viewmodels/now_playing_vm.py:684-705`  
`src/doremi/ui/main_window.py:418-419`

**Problema**

El menú de Queue muestra “Quitar de la cola”, pero dispara `queue_action(index, "delete_download")`. El ViewModel emite `delete_download_requested`, que MainWindow conecta a `DownloadController.delete_download_async()`. `PlayQueue.remove_at()` no se invoca desde esta acción.

**Cómo reproducir**

1. Añadir una canción descargada a la cola.
2. Abrir Queue → menú de la fila → “Quitar de la cola”.
3. Se abre la confirmación de eliminar descarga; al confirmar se borra el archivo/DB. La canción sigue perteneciendo a la cola de la sesión.

**Causa raíz**

Se reutilizó un action string de Downloads para una intención distinta y no existe una señal `remove_queue_item_requested`.

**Impacto**

Acción destructiva equivocada y pérdida de contenido offline confirmada por el usuario. Incluso al cancelar, no cumple la acción prometida.

**Solución recomendada**

Introducir la intención explícita `remove_queue_item(index)` en `NowPlayingViewModel`, conectar a `PlayQueue.remove_at(index)`, actualizar modelo y decidir el comportamiento de pista actual (seguir con siguiente o detener según especificación). Mantener borrar descarga como una acción separada y con copy exacto.

**Test de regresión**

Con una cola de tres y una descarga local: seleccionar “Quitar de la cola” debe reducir la cola a dos y no llamar a `delete_download_async` ni tocar filesystem/DB. Cubrir pista actual, próxima, duplicados y cola vacía.

### BUG-006 — “Añadir a playlist” pasa el artwork como título en siete superficies

**Severidad:** High

**Archivos:**

`src/doremi/ui/viewmodels/home_vm.py:467,487`  
`src/doremi/ui/viewmodels/search_vm.py:367`  
`src/doremi/ui/viewmodels/history_vm.py:148`  
`src/doremi/ui/viewmodels/stats_vm.py:198`  
`src/doremi/ui/viewmodels/playlist_vm.py:273`  
`src/doremi/ui/viewmodels/album_vm.py:257`  
`src/doremi/ui/viewmodels/artist_vm.py:247`  
`src/doremi/ui/viewmodels/now_playing_vm.py:701,731`

**Problema**

La señal tiene contrato `(video_id, title)`, pero las acciones anteriores emiten `(vid, thumb)`. La cola de Descargas y el menú de pista actual son las excepciones correctas.

**Cómo reproducir**

1. En Home/Search/History/Stats/Playlist/Album/Artist/Queue/Similares abrir el menú de una canción.
2. Elegir “Añadir a playlist”.
3. El diálogo y sus mensajes usan una URL de miniatura en vez del título de canción.

**Causa raíz**

Duplicación de mapeos de context menu con parámetros posicionales incompatibles.

**Impacto**

La operación puede completarse en YouTube Music, pero el feedback al usuario es incorrecto y expone texto técnico; la incoherencia depende de la pantalla.

**Solución recomendada**

Definir un DTO/intención común de canción o al menos una función central que reciba `video_id,title,artist,thumbnail`. Corregir todos los `emit(vid, thumb)` a `emit(vid, title)` y usar pruebas parametrizadas de todas las superficies.

**Test de regresión**

Parametrizar cada ViewModel y comprobar que la señal produce `(videoId, title)`, nunca la URL `thumbnail_url`.

### BUG-007 — “Eliminar descargas” de Settings deja DB y disco desincronizados

**Severidad:** High

**Archivos:**

`src/doremi/ui/screens/settings_qml.py:191-196`  
`src/doremi/services/download_manager.py:253-271`  
`src/doremi/db/repository.py:224-244`

**Problema**

La acción de Settings borra sólo archivos directamente bajo `AppDirs.downloads`; no borra subcarpetas de playlists/álbumes, no borra filas `downloads` de la DB, no cancela tareas y comunica éxito sin confirmación.

**Cómo reproducir**

1. Descargar una canción individual y una playlist.
2. Settings → Almacenamiento → “Eliminar descargas”.
3. La canción raíz desaparece, la playlist anidada permanece. Ambas entradas siguen apareciendo como completadas por la DB; la canción borrada falla localmente y hace fallback a streaming.

**Causa raíz**

`_clear_downloads()` implementa un borrado de filesystem independiente de `downloads_data.delete_download_files()` / `DownloadRepository`.

**Impacto**

La biblioteca offline miente sobre disponibilidad; se acumulan entradas huérfanas y la operación es irreversible sin confirmación.

**Solución recomendada**

Reutilizar un único flujo transaccional de borrado: pausar/cancelar tareas seleccionadas, eliminar cada audio/lyric, eliminar su fila sólo después del éxito y reportar fallos parciales. Borrar directorios vacíos al final. Pedir confirmación QML con cantidad/espacio y refrescar Downloads inmediatamente.

**Test de regresión**

Crear descarga raíz y anidada, ejecutar la acción, verificar que ambos archivos y filas se eliminan; simular fallo de unlink y verificar que su fila permanece y se muestra error parcial. Cubrir tareas activas.

### BUG-008 — Last.fm y Discord no se aplican al cambiar el toggle en runtime

**Severidad:** High

**Archivos:**

`src/doremi/ui/controllers/settings_controller.py:25-42`  
`src/doremi/ui/controllers/integrations_controller.py:187-197`  
`src/doremi/ui/controllers/playback_controller.py:589-596`

**Problema**

Settings crea o elimina `main_window.scrobbler`, pero no actualiza `playback_controller.scrobbler` ni `integrations_controller.scrobbler`, que son quienes scrobblean y evalúan posiciones. El toggle Discord se persiste pero `SettingsController` no crea/desconecta RPC ni actualiza `playback_controller.discord`. Sólo `setup_integrations()` lo hace al inicio.

**Cómo reproducir**

1. Arrancar con Last.fm/Discord desactivados.
2. Activarlos durante una sesión y reproducir otra canción.
3. No hay scrobble/Rich Presence hasta reiniciar (y Discord puede permanecer conectado al desactivarlo).

**Causa raíz**

Hay varias referencias inyectadas a las integraciones, sin un punto único de propiedad ni método de reconfiguración.

**Impacto**

Los toggles muestran estado activo que el backend ignora durante la sesión: una feature fantasma especialmente engañosa.

**Solución recomendada**

Centralizar el ciclo de vida en `IntegrationsController.reconfigure(settings)`: crear, conectar, desconectar y asignar la misma instancia a todos los consumidores; al activar, publicar inmediatamente la pista actual; al desactivar, desconectar y limpiar estado. Mostrar loading/error en Settings.

**Test de regresión**

Cambiar cada toggle durante reproducción con fakes: verificar connect/update al activar, disconnect al desactivar y que player/integrations/main window referencian exactamente la misma instancia.

### BUG-009 — Shuffle puede volver a poner canciones ya escuchadas como próxima pista

**Severidad:** Medium

**Archivos:**

`src/doremi/audio/queue.py:157-174`

**Problema**

Al activar shuffle, la cola se rehace con `remaining = [i for i in self._queue if i is not current]`. Ese conjunto incluye historial anterior y próximas canciones. Tras reproducir la canción 7 de una playlist, una canción 1–6 puede quedar inmediatamente siguiente.

**Cómo reproducir**

1. Reproducir secuencialmente varias canciones de una playlist.
2. Activar shuffle estando avanzada.
3. Pulsar Next repetidas veces; canciones ya oídas pueden reaparecer antes de agotar las no oídas.

**Causa raíz**

`PlayQueue` sólo modela un array e índice. No diferencia historial de sesión, actual y próximas.

**Impacto**

Shuffle se percibe repetitivo e impredecible, especialmente en listas grandes.

**Solución recomendada**

Como corrección acotada, al activar shuffle barajar primero los elementos posteriores al índice actual y conservar los anteriores como historial no reproducible salvo Previous. Para un rediseño posterior, modelar explícitamente `history`, `current`, `up_next` y origen autoplay.

**Test de regresión**

Con una lista de 10 en índice 6, activar shuffle y avanzar hasta agotar las tres siguientes: ninguna de 0–5 debe ser siguiente. Probar ON → OFF, Repeat All y duplicados.

### BUG-010 — Duplicados de cola se muestran como varias canciones “actuales”

**Severidad:** Medium

**Archivos:**

`src/doremi/ui/viewmodels/now_playing_vm.py:526-541`

**Problema**

La fila actual se decide con `vid == self._video_id`. Dos ocurrencias del mismo `video_id` son soportadas por `PlayQueue` (por identidad de objeto), pero ambas quedan resaltadas en QML.

**Cómo reproducir**

1. Añadir la misma canción dos veces a la cola.
2. Reproducir una de ellas.
3. Las dos filas aparecen como current.

**Causa raíz**

El ViewModel convierte una identidad de ocurrencia en una identidad de canción.

**Impacto**

El usuario no sabe qué ocurrencia está reproduciéndose y puede mover/eliminar la equivocada.

**Solución recomendada**

Pasar `current_index` o un `queue_entry_id` estable al modelo y marcar sólo esa fila.

**Test de regresión**

Con dos `QueueItem` con mismo video id y distintos índices, comprobar que exactamente una fila tiene `is_current=True` antes y después de mover.

### BUG-011 — Home y Biblioteca convierten errores de red en una pantalla vacía silenciosa

**Severidad:** Medium

**Archivos:**

`src/doremi/ui/screens/home_qml.py:99-120`  
`src/doremi/ui/viewmodels/home_vm.py:320-396`  
`src/doremi/ui/screens/library_qml.py:123-154`

**Problema**

Home sólo registra la excepción y apaga loading; no tiene propiedad error/retry. Library vacía el modelo ante excepción, indistinguible de “no tienes elementos”, y tampoco expone error/retry. La creación de playlist también registra el error sin feedback (`library_qml.py:91-100`).

**Cómo reproducir**

1. Abrir Home o Biblioteca con API que falla después de que se detecta conectividad.
2. Esperar a que desaparezca el spinner.
3. Se ve contenido vacío sin explicación ni reintento, y crear una playlist fallida no avisa.

**Causa raíz**

Los wrappers consumen excepciones en logs sin estado `errorText` ni acción de retry, a diferencia de Search.

**Impacto**

El usuario interpreta un fallo transitorio como pérdida de biblioteca o una app inacabada.

**Solución recomendada**

Adoptar el contrato de Search: `loading`, `errorText`, `retryRequested`, empty state separado de error y botones disabled durante mutaciones. Para creación, mantener dialog abierto con busy/error y refrescar sidebar después de éxito.

**Test de regresión**

Forzar excepciones de `gather_home`, cada tab de Library y `create_playlist`; verificar error visible, Retry que relanza, estado vacío sólo para respuesta exitosa vacía y feedback de éxito/error.

### BUG-012 — Las descargas fallidas no se pueden reintentar desde UI y las activas no se pueden controlar desde Descargas

**Severidad:** Medium

**Archivos:**

`src/doremi/services/download_manager.py:154-186`  
`src/doremi/ui/qml/DownloadsScreen.qml:350-459`  
`src/doremi/ui/widgets/notification_panel_qml.py:37-39`

**Problema**

El manager expone pause/resume/retry/cancel, pero `DownloadsScreen` sólo muestra progreso y menú de acciones de completadas. Cancelar está escondido en NotificationPanel; no hay botones de retry/pause/resume junto al estado error/active.

**Cómo reproducir**

1. Provocar error de yt-dlp.
2. Ir a Descargas → filtro Error.
3. No existe “Reintentar”. Para una activa, tampoco hay Cancelar/Pausar/Continuar en su fila.

**Causa raíz**

Las capacidades del manager no están expuestas por `DownloadsViewModel` ni por la pantalla que representa las tareas.

**Impacto**

El usuario debe descubrir el panel de notificaciones y aun así sólo puede cancelar; un error queda sin recuperación visible.

**Solución recomendada**

Añadir acciones dependientes de `status` al modelo de Descargas: Cancelar para queued/downloading, Pausar/Continuar cuando aplique y Reintentar para error. Deshabilitarlas mientras se procesa y actualizar fila sin recarga completa.

**Test de regresión**

Para cada estado, comprobar las acciones visibles/disabled y que llegan a `DownloadManager`; simular retry exitoso/error y comprobar progresión de UI.

### BUG-013 — `stop_on_close` no se consulta nunca

**Severidad:** Medium

**Archivos:**

`src/doremi/config/settings.py:24`  
`src/doremi/ui/main_window.py:895-919`

**Problema**

La preferencia “Parar al cerrar” se muestra y se persiste, pero no tiene ninguna lectura fuera de su definición/UI. `closeEvent()` decide sólo por `minimize_to_tray`; el apagado libera el player independientemente de este toggle.

**Cómo reproducir**

1. Alternar “Parar al cerrar”.
2. Cerrar forzadamente Doremi con el toggle en ambos valores.
3. No hay diferencia de comportamiento atribuible a la preferencia.

**Causa raíz**

Configuración declarada sin integración con el flujo de close/tray.

**Impacto**

Una opción de reproducción visible no hace lo que promete.

**Solución recomendada**

Definir semántica inequívoca con `minimize_to_tray` (por ejemplo: si se minimiza, parar sólo si `stop_on_close`; si se sale, siempre liberar) y ejecutar `player.stop()` antes de ocultar/cerrar cuando corresponda. Si no se desea ese comportamiento, eliminar la opción.

**Test de regresión**

Cubrir las cuatro combinaciones tray/stop y afirmar hide vs shutdown y llamada exacta a `player.stop`.

### BUG-014 — Algunos ajustes de subtítulos son decorativos en la UI QML

**Severidad:** Medium

**Archivos:**

`src/doremi/config/settings.py:56-62`  
`src/doremi/ui/screens/now_playing_qml.py:459-468`  
`src/doremi/ui/viewmodels/now_playing_vm.py:543-550`

**Problema**

La pantalla Settings permite `line_spacing` y `animation_style`, y el modelo tiene colores activo/inactivo, pero el puente QML sólo transfiere font size, alignment, glow, auto scroll y delay. No hay lectura de `line_spacing`, `animation_style`, `text_color_active` ni `text_color_inactive` en la ruta QML activa.

**Cómo reproducir**

1. Abrir Now Playing → Letras.
2. Cambiar espaciado, estilo de animación o colores (si se cargan vía config).
3. La apariencia no cambia; persiste una preferencia sin efecto.

**Causa raíz**

La implementación QtWidgets histórica sí tenía parte de la lógica, pero el ViewModel QML no recibió esos campos.

**Impacto**

Settings ofrece personalización inexistente y crea diferencias entre rutas legacy y activas.

**Solución recomendada**

O bien implementar esos parámetros en el modelo/QML, o retirar/ocultar las opciones hasta que estén listas. Incorporar `lineSpacing`, animation enum y colores en `set_lyrics_style` y bindings QML.

**Test de regresión**

Cambiar cada setting y comprobar que el ViewModel QML recibe y notifica el valor; una prueba QML debe observar el binding de tamaño/espaciado/color/animación.

### BUG-015 — Los controles esenciales de MiniPlayer no son operables por teclado ni tienen nombre accesible

**Severidad:** Medium

**Archivos:**

`src/doremi/ui/qml/MiniPlayer.qml:117-278`  
`src/doremi/ui/qml/Doremi/MediaCard.qml:21-105`  
`src/doremi/ui/qml/DownloadsScreen.qml:239-460`

**Problema**

Artist, seek, Previous, Play/Pause, Next y Expand del MiniPlayer son `MouseArea` dentro de `Rectangle` sin `activeFocusOnTab`, `Keys`, `Accessible.role/name` o tooltip. El componente compartido `MediaCard` y filas de Descargas repiten el patrón.

**Cómo reproducir**

1. Usar Tab desde el header hasta MiniPlayer o una tarjeta.
2. Los controles no reciben foco operativo ni responden a Enter/Espacio.
3. Un lector de pantalla no obtiene un nombre de acción fiable.

**Causa raíz**

La accesibilidad se añadió selectivamente a `HeroButton`, `HeaderButton`, sidebar y Like de Now Playing, pero no a los controles hechos a mano.

**Impacto**

La app no es operable con teclado en la zona de reproducción principal. También hay affordances que sólo se descubren por hover.

**Solución recomendada**

Crear un `IconButton` QML accesible reutilizable para los iconos y un control de slider accesible para seek; sustituir los `MouseArea` de acciones. Añadir focus ring, Enter/Espacio, Escape para menús y ToolTip para iconos sin texto.

**Test de regresión**

Instanciar cada componente y verificar `activeFocusOnTab`, Accessible.name no vacío, activación Enter/Espacio y `enabled` correcto. Completar manualmente con navegación Tab real y lector de pantalla.

### BUG-016 — Al limpiar una descarga borrada manualmente, la UI sigue mostrándola como offline

**Severidad:** Medium

**Archivos:**

`src/doremi/ui/screens/downloads_data.py:40-55`  
`src/doremi/ui/controllers/playback_controller.py:329-415`

**Problema**

Downloads construye las filas desde DB sin comprobar que `file_path` existe. Playback detecta tarde que el fichero no existe y cambia a streaming; la entrada descargada no se repara ni elimina.

**Cómo reproducir**

1. Descargar una canción.
2. Borrar el archivo desde el gestor de archivos.
3. Descargas aún dice “completed”; offline puede fallar y playback hace fallback online sólo al intentar reproducir.

**Causa raíz**

No hay reconciliación DB↔filesystem al cargar descargas ni al cambiar a offline.

**Impacto**

La disponibilidad offline se representa de forma falsa y la acción de play tiene resultado distinto al indicado por UI.

**Solución recomendada**

Al cargar o al iniciar, marcar faltantes como unavailable y ofrecer “Quitar entrada”/“Redescargar”; no anunciarla como completed. Opcionalmente, reconciliar y eliminar DB sólo tras una política explícita.

**Test de regresión**

Crear fila DB con path ausente: `gather_downloaded_songs()` no debe devolver `completed` reproducible; debe exponer estado missing y acción de recuperación.

### BUG-017 — El estado de carga del reproductor no bloquea Next/acciones repetidas de cola

**Severidad:** Low

**Archivos:**

`src/doremi/ui/qml/MiniPlayer.qml:205-279`  
`src/doremi/ui/qml/NowPlayingScreen.qml:417-455`  
`src/doremi/ui/controllers/playback_controller.py:213-228,798-816`

**Problema**

La cancelación de requests protege muchos casos de carrera, pero los botones siguen visualmente activos durante `LOADING` y no informan qué acción ganó. La pista se puede cambiar varias veces y los modelos de cola se actualizan por tareas asíncronas separadas.

**Cómo reproducir**

1. Con extracción lenta, pulsar Play A, Next, Next y Play/Pause rápidamente.
2. La implementación intenta cancelar correctamente, pero la UI no deshabilita/indica la operación y puede mostrar por instantes información de A mientras B/C es la request vigente.

**Causa raíz**

Existe `PlayerState.LOADING`, pero no se expone como política de interacción coherente a todos los controles ni hay token de operación para actualizaciones de cola/feedback.

**Impacto**

No es un crash confirmado gracias a las defensas existentes, pero se siente inestable bajo red lenta.

**Solución recomendada**

Mantener los botones de navegación permitidos si ésa es la decisión de producto, pero deshabilitar duplicados de la misma operación, mostrar el título “Cargando…”, y hacer que la UI sólo aplique resultados con el play id actual.

**Test de regresión**

Extender `test_playback_request_races.py` con assert de estado de MiniPlayer/Now Playing: A nunca recupera título/progreso tras B y la acción de pausa durante loading tiene feedback visible.

### BUG-018 — Las preferencias de color dinámico, blur, normalización, silencio, gapless, proxy y calidad no cambian ningún comportamiento

**Severidad:** Low

**Archivos:**

`src/doremi/config/settings.py:11-12,18-19,23,37-38`  
`src/doremi/ui/viewmodels/settings_vm.py:258-299`

**Problema**

Estas opciones están expuestas por Settings o config, se guardan y no tienen lecturas de backend/QML activo fuera de su propia UI.

**Cómo reproducir**

1. Alterar cualquiera de las opciones.
2. Reiniciar y comparar el comportamiento descrito.
3. No cambia el color por artwork, fondo blur, procesamiento de audio, reproducción gapless, proxy ni calidad de stream.

**Causa raíz**

Modelo de settings más amplio que la implementación actual.

**Impacto**

Opciones decorativas erosionan confianza y hacen difícil soporte técnico.

**Solución recomendada**

Quitar temporalmente de UI las opciones que no tienen motor, o implementar cada ruta completa. No conservar toggles “próximamente” como configuraciones activas.

**Test de regresión**

Para cada setting que se mantenga, un test de comportamiento, no sólo de persistencia: por ejemplo, mock de extractor recibe calidad/proxy; state de artwork cambia con blur/dynamic; motor recibe la configuración de audio.

### BUG-019 — Los ajustes de sidebar y fuente global no tienen el mismo alcance que promete la UI

**Severidad:** Low

**Archivos:**

`src/doremi/config/settings.py:13-14`  
`src/doremi/ui/controllers/settings_controller.py:78-89`  
`src/doremi/ui/widgets/nav_sidebar_qml.py:21-24`

**Problema**

`compact_sidebar` funciona en runtime, pero el estado visual inicial siempre arranca `_collapsed = False`; se aplica sólo cuando la pantalla Settings emite un cambio, no al construir sidebar. `AppearanceSettings.font_size` existe pero no está en la UI ni tiene uso en QML/QSS.

**Cómo reproducir**

1. Activar sidebar compacta y reiniciar sin volver a tocar Settings.
2. La barra vuelve expandida aunque settings contenga `true`.
3. No hay forma visible de modificar ni observar el font size global.

**Causa raíz**

El presenter del sidebar no recibe settings iniciales y el campo font size no se integra en tokens/QML.

**Impacto**

Persistencia visual inconsistente y configuración muerta.

**Solución recomendada**

Inicializar `NavSidebarQml._collapsed` desde settings antes de MainShell, con ancho correspondiente; decidir si font size global se implementa como token escalable o se elimina del modelo.

**Test de regresión**

Instanciar MainWindow/Sidebar con `compact_sidebar=True` y comprobar collapsed/ancho desde el primer frame; añadir test de font size o eliminarlo.

### BUG-020 — Cerrar al tray podía reactivar una reproducción que seguía cargando

**Severidad:** High — **Corregido (2026-09-26)**

**Archivos:**

`src/doremi/ui/controllers/playback_controller.py` — `PlaybackController.stop_for_window_close`

**Problema**

Con `minimize_to_tray` y `stop_on_close` activos, la ventana detenía VLC pero
no invalidaba una extracción/arranque asíncrono ya iniciado. Si dicho arranque
terminaba después, podía volver a llamar a `play_url` mientras Doremi estaba
oculta.

**Cómo reproducir (estado previo)**

1. Iniciar una pista remota y cerrar/minimizar mientras sigue en `LOADING`.
2. Tener activado “Parar al cerrar”.
3. Esperar a que la URL de stream termine de resolverse.

**Causa raíz**

`stop_for_window_close` sólo programaba `player.stop()`. La identidad
`_current_play_id` y `_play_task`, que protegen al resto de la máquina de
estados contra respuestas tardías, permanecían válidos.

**Impacto**

Audio inesperado desde el tray y UI/estado de reproducción divergentes tras
un cierre que prometía detenerla.

**Solución aplicada**

Incrementar `_current_play_id`, cancelar `_play_task`, limpiar el reinicio
pendiente y cancelar el crossfade antes de finalizar la sesión y detener VLC.

**Test de regresión**

`tests/test_audit_regressions.py::test_stop_on_close_cancels_pending_play_request`
verifica la cancelación, la nueva identidad y una única llamada a `stop`.

### BUG-021 — Un retry de búsqueda idéntico podía ocultar su propio loading

**Severidad:** Medium — **Corregido (2026-09-26)**

**Archivos:**

`src/doremi/ui/screens/search_qml.py` — `SearchScreenQml._schedule_fetch`, `_fetch`

**Problema**

Al reintentar la misma consulta y categoría, la tarea anterior se cancelaba
pero su bloque `finally` seguía viendo la misma query/categoría y ponía
`loading=False` mientras el nuevo request aún estaba esperando red.

**Impacto**

La interfaz podía mostrar resultados vacíos sin spinner durante un retry, aun
cuando el botón indicaba que la operación había comenzado.

**Solución aplicada**

Cada petición tiene una generación monotónica. Sólo la generación vigente
puede actualizar modelos, caché, error o loading; la comparación ya no depende
solamente de query/categoría.

**Test de regresión**

`tests/test_audit_regressions.py::test_search_retry_ignores_cancelled_request_loading_state`
simula un request cancelado que termina después de que el retry ya está activo.

### BUG-022 — Recargar Inicio podía mezclar la respuesta de una carga anterior

**Severidad:** Medium — **Corregido (2026-09-26)**

**Archivos:**

`src/doremi/ui/screens/home_qml.py` — `HomeScreenQml.force_reload`, `load`, `_load`

**Problema y causa raíz**

`force_reload()` creaba tareas sin identidad ni referencia. Una respuesta vieja
podía escribir su feed/error/loading tras una recarga nueva; además, después de
un `await load()` se conservaba por error la tarea llamadora como tarea activa.

**Solución aplicada**

Se usa generación de carga, se cancela el request sustituido y se libera la
referencia a una llamada pública al terminar. Sólo la generación vigente puede
mutar el ViewModel.

**Test de regresión**

`test_home_reload_ignores_cancelled_response_state` cubre una respuesta tardía
que ignora la cancelación.

### BUG-023 — Cambiar pestaña de Biblioteca podía apagar el loading de la nueva

**Severidad:** Medium — **Corregido (2026-09-26)**

**Archivos:**

`src/doremi/ui/screens/library_qml.py` — `LibraryScreenQml._schedule_load`, `_load_tab`

**Problema y causa raíz**

La cancelación de una carga de pestaña anterior no distinguía su `finally` de
la carga nueva. Una respuesta/cancelación tardía podía modificar loading, error
o datos visibles de otra pestaña.

**Solución aplicada**

Las cargas tienen generación y tab de destino; sólo la generación cuyo tab es
el actual actualiza el ViewModel. La caché se mantiene por tab sin contaminar
la superficie visible.

**Test de regresión**

`test_library_tab_switch_ignores_cancelled_loading_state` cambia de Canciones
a Álbumes mientras el primer request se cancela tarde.

### BUG-024 — Cargas tardías podían desincronizar pantallas de datos asíncronos

**Severidad:** High — **Corregido (2026-09-26)**

**Archivos:**

`src/doremi/ui/screens/playlist_qml.py`, `album_qml.py`, `artist_qml.py`,
`history_qml.py`, `stats_qml.py`, `downloads_qml.py`

**Problema**

Las pantallas cancelaban algunas solicitudes previas, pero una dependencia que
terminase tarde podía ejecutar `finally` o escribir datos de una ruta,
pestaña o filtro anterior. En particular, Playlist A → Playlist B podía dejar
loading incorrecto o contenido A.

**Solución aplicada**

Todas usan generación de solicitud; Descargas además ata la generación a la
pestaña y filtro. Sólo el request vigente modifica loading, error o modelos.

**Test de regresión**

`test_playlist_navigation_ignores_cancelled_response`,
`test_history_retry_keeps_loading_until_current_request_finishes` y
`test_stats_retry_keeps_loading_until_current_request_finishes` verifican el
patrón con dependencias que responden tras la cancelación.

### BUG-044 — Las tarjetas de colecciones descargadas no podían navegar

**Severidad:** High — **Corregido (2026-09-27)**

**Archivos:**

`src/doremi/ui/qml/DownloadsScreen.qml` — delegate de `GridView` de álbumes y playlists  
`src/doremi/ui/viewmodels/downloads_vm.py` — `DownloadsViewModel.group_navigate`

**Problema**

La UI prometía abrir el álbum o playlist local al activar su tarjeta. Sin
embargo, los cuatro caminos de activación (click, lector de pantalla, Enter y
Espacio) llamaban `screenVm.navigate(gridCell.navigate)`. Ese método no existe
en `DownloadsViewModel`; el único slot publicado es `group_navigate(index)`.

**Cómo reproducir (estado previo)**

1. Descargar al menos una playlist o álbum y abrir Descargas.
2. Entrar en la pestaña Playlists completas o Álbumes.
3. Pulsar una tarjeta, o enfocarla con Tab y usar Enter/Espacio.

**Causa raíz**

La migración QML reutilizó la convención de otros ViewModels que sí exponen
`navigate(route)`, pero el ViewModel de Descargas encapsula la ruta en el
modelo y sólo ofrece `group_navigate(index)`.

**Impacto**

Una colección visible y marcada como descargada era un CTA fantasma: no podía
abrirse por ningún método de entrada, incluida tecnología asistiva.

**Solución aplicada**

Las cuatro rutas invocan `screenVm.group_navigate(gridCell.index)`, que valida
el item y emite `navigate_requested` con su ruta local.

**Test de regresión**

`tests/test_downloads_qml.py::TestDownloadsScreenQml::test_group_cards_call_the_viewmodel_navigation_slot`
vigila el contrato QML/ViewModel, complementado por
`TestDownloadsViewModel::test_navigate_groups` para la emisión final.

### BUG-045 — Los grupos de descargas conservaban archivos eliminados externamente

**Severidad:** Medium — **Corregido (2026-09-27)**

**Archivos:**

`src/doremi/ui/screens/downloads_data.py` — `gather_download_groups`

**Problema**

`gather_downloaded_songs()` comprueba que cada `file_path` existe y elimina el
registro DB obsoleto. `gather_download_groups()` construía tarjetas directamente
desde la misma tabla sin esa comprobación. Por tanto, si el usuario eliminaba
un MP3 fuera de Doremi antes de abrir la pestaña de grupos, seguía viendo una
playlist/álbum local “completo”, pero sin audio reproducible.

**Cómo reproducir (estado previo)**

1. Descargar todas las canciones de una playlist.
2. Eliminar sus archivos desde el explorador de archivos.
3. Reiniciar Doremi y abrir Descargas → Playlists completas.

**Causa raíz**

La conciliación DB/filesystem se implementó sólo en la fuente de datos de la
lista de canciones, dejando a la fuente de datos de grupos con una segunda
vista inconsistente de la misma tabla.

**Impacto**

La UI podía prometer contenido offline que había desaparecido y dejar una DB
desincronizada hasta que el usuario visitara casualmente la pestaña Canciones.

**Solución aplicada**

Antes de agrupar, `gather_download_groups()` valida cada archivo y borra el
registro obsoleto de forma idéntica a la vista de canciones. Un error de borrado
se registra y no inventa una tarjeta válida.

**Test de regresión**

`tests/test_audit_regressions.py::test_download_group_listing_reconciles_records_for_deleted_files`
simula un registro de grupo cuyo archivo ya no existe y exige grupo vacío y
`remove_download(video_id)`.

### BUG-046 — Los botones de Artist anunciaban una propiedad inexistente

**Severidad:** Low — **Corregido (2026-09-27)**

**Archivos:**

`src/doremi/ui/qml/ArtistScreen.qml` — CTAs Play y Shuffle  
`src/doremi/ui/viewmodels/artist_vm.py` — propiedad pública `artistName`

**Problema y causa raíz**

Los nombres accesibles de ambos CTAs concatenaban `screenVm.title`, una
propiedad que `ArtistViewModel` no publica. La pantalla visual usaba el nombre
correcto (`artistName`), pero el lector de pantalla recibía “undefined”.

**Impacto**

La acción funcionaba, pero su etiqueta accesible no describía qué artista se
reproduciría y daba una señal clara de UI inacabada.

**Solución aplicada**

Los dos CTAs usan ahora `screenVm.artistName`, la misma fuente de verdad que
el encabezado.

**Test de regresión**

`tests/test_artist_qml.py::TestArtistScreenQml::test_play_ctas_name_the_actual_artist_for_accessibility`.

### BUG-047 — MPRIS no reflejaba correctamente una sesión ya activa

**Severidad:** High — **Corregido (2026-09-27)**

**Archivos:**

`src/doremi/ui/controllers/integrations_controller.py` — `reconfigure_mpris`, `_sync_mpris_snapshot`, `_wire_mpris_callbacks`, `on_state_changed_callback`  
`src/doremi/system/mpris.py` — `MprisPlayer.update_playback_status`  
`src/doremi/ui/controllers/playback_controller.py` — `resume_or_start`, `stop_playback`

**Problema**

MPRIS convertía cualquier estado que no fuera PLAYING en `Paused`, incluida
una reproducción terminada, detenida o con error. Además, al activar MPRIS en
medio de una pista sólo registraba el servicio: no enviaba metadata, posición,
volumen ni estado hasta que VLC generara otro evento. El método DBus `Play`
llamaba directamente a `MusicPlayer.resume()`, que no puede iniciar una canción
que sólo está en cola cuando VLC está IDLE; `Stop` tampoco finalizaba la sesión
de escucha.

**Cómo reproducir (estado previo)**

1. Reproducir una canción y activar MPRIS desde Ajustes.
2. Abrir los controles multimedia del escritorio: podían mostrar “Stopped” y
   ninguna pista hasta el siguiente evento.
3. Detener una pista: el escritorio mostraba Paused. Alternativamente, añadir
   una canción a una cola vacía y pulsar Play desde MPRIS: no comenzaba audio.

**Causa raíz**

`on_state_changed_callback()` descartaba el enum `PlayerState` y entregaba
sólo un booleano a MPRIS. La reconfiguración no sincronizaba el estado presente
ni delegaba Play/Stop en los límites de estado de `PlaybackController`.

**Impacto**

Los controles del sistema podían mentir sobre reproducción, no iniciar una
cola válida y dejar historial/estadísticas sin un cierre explícito al detener.

**Solución aplicada**

MPRIS acepta estado completo y publica `Playing`, `Paused` o `Stopped` según
corresponda. La activación emite un snapshot de estado, posición, volumen,
shuffle/repeat y metadata. Play usa `resume_or_start()`; Stop cancela una
solicitud pendiente, finaliza la escucha y detiene VLC mediante
`stop_playback()`.

**Test de regresión**

`tests/test_controllers.py::TestIntegrations::test_enabling_mpris_publishes_the_current_playback_snapshot`,
`test_mpris_receives_stopped_not_paused_when_player_is_idle`, y las pruebas
de PlaybackController citadas en la tabla de correcciones.

### BUG-048 — Importar una copia inválida podía alterar la sesión y extraer rutas arbitrarias

**Severidad:** High — **Corregido (2026-09-27)**

**Archivos:**

`src/doremi/utils/backup.py` — `BackupManager.export_backup`, `import_backup_async`  
`tests/test_backup.py`

**Problema**

La restauración invocaba `ZipFile.extractall()` sobre un archivo seleccionado
por el usuario. Un ZIP con `../` podía escribir fuera de la carpeta temporal.
Además, se hacía `get_engine().dispose()` antes de abrir y validar el ZIP: un
archivo corrupto o no compatible podía dejar la sesión actual sin conexiones
aunque el restore devolviera error.

**Cómo reproducir (estado previo)**

1. Elegir una copia ZIP corrupta o un ZIP con un miembro `../outside.txt`.
2. Iniciar Restaurar copia desde Ajustes.
3. La app podía cerrar su motor DB antes de devolver el error; el ZIP podía
   extraer archivos fuera del staging.

**Causa raíz**

Se trataba toda estructura ZIP como backup válido y el orden de operaciones
liberaba recursos de producción antes de completar la validación.

**Impacto**

Una función visible de restore podía dejar la sesión temporalmente degradada y
aceptar una copia maliciosa o equivocada, en vez de fallar sin efectos.

**Solución aplicada**

La copia sólo admite los nombres planos `doremi.db` y `settings.toml`, rechaza
extras, duplicados y symlinks, y copia su contenido a un staging único sin
`extractall`. Sólo después valida y libera el motor; cada destino se reemplaza
desde un archivo temporal. La exportación también usa staging único que se
limpia incluso si falla.

**Test de regresión**

`tests/test_backup.py::test_backup_restore_rejects_path_traversal_before_disposing_database`
usa un ZIP traversal, exige que no se toque la DB/configuración y verifica que
no se solicita el motor.

### BUG-049 — Fallo de conexión Discord invisible tras activar Rich Presence

**Severidad:** Medium — **Corregido (2026-09-27)**

**Archivos:**

`src/doremi/api/discord_rpc.py` — `DiscordRPC.is_connected`  
`src/doremi/ui/controllers/integrations_controller.py` — `reconfigure_discord`, `_connect_discord`

**Problema**

El checkbox Rich Presence se persistía y creaba el cliente, pero si el IPC de
Discord fallaba (cliente cerrado, socket no disponible) `connect()` sólo
escribía un warning en logs. Para el usuario la preferencia parecía aplicada
sin aclarar que no habría presencia activa.

**Solución aplicada**

El cliente publica si existe conexión efectiva. Tras un cambio manual, el
controlador muestra un toast de advertencia si no logró conectar y explica que
reintentará cuando haya reproducción. En el arranque no genera un toast
intrusivo; la reconexión existente se conserva.

**Test de regresión**

`tests/test_controllers.py::TestIntegrations::test_discord_toggle_reports_a_failed_manual_connection`.

**Estado posterior:** Discord Rich Presence se retiró posteriormente del
producto por decisión de alcance. Esta ficha se conserva sólo como historial
de auditoría; no existe ya UI, configuración ni cliente Discord activo.

### BUG-050 — Sistema de videoclip retirado

**Estado:** Retirado del producto (2026-09-29)

**Archivos:**

`src/doremi/ui/main_window.py` — `_build_now_playing_qml`  
`src/doremi/ui/screens/now_playing_qml.py` — `_find_main_window`,
`_show_video_clip`, `_sync_video_player`  
`src/doremi/ui/qml/NowPlayingScreen.qml` — loader del contenido y
`attachVideoSink`  
`src/doremi/ui/qml/HomeScreen.qml` — loader del contenido

**Problema (estado previo)**

La isla QML de Now Playing era un `QObject` sin padre. Sus intenciones de
transporte y vídeo buscan MainWindow recorriendo `parent()`, por lo que Play,
Previous, Next, Seek y la petición de stream podían no hacer nada. Además,
`VideoOutput` intentaba usar `screenVm.setVideoSink(...)` mientras la ruta se
construía con `screenVm` nulo. El resultado era un `TypeError` QML y, aun con
una URL válida, un `QMediaPlayer` sin destino visual.

**Solución aplicada**

MainWindow es ahora el padre explícito del presenter. ScreenHost recibe URL y
view-model mediante una única llamada atómica: antes, dos cambios de propiedad
sucesivos inyectaban por un instante la VM de Home en Now Playing (y a la
inversa). Home y Now Playing además sólo instancian sus bindings internos
después de recibir el view-model. Now Playing conserva el tipo concreto
`QVideoSink` —no un `QObject` borrado por el bridge de PySide— al crearse y al
reemplazar VM, por lo que `QMediaPlayer.setVideoSink` lo acepta. La carga de
vídeo registra la obtención y aplicación del stream. El handler de letras se
reemplazó por un timer, evitando un `Connections` a una señal Python que Qt no
podía descubrir de forma fiable.

**Evidencia de regresión**

Las pruebas cubren el puente de transporte, extracción, asignación de fuente,
arranque del reproductor y reassociación del sink al sustituir VM. Una sonda
local adicional con FFmpeg/Qt Multimedia decodificó un MP4 H.264 y recibió 16
fotogramas en `QVideoSink`, sin errores de `QMediaPlayer`. Con red real, el
mismo flujo extractor → `QMediaPlayer` seleccionó un MP4/H.264 720p de YouTube
y recibió 273 fotogramas, también sin error de reproducción.

## 3. Ghost / Partially Implemented Features

Clasificación: **FUNCIONAL** = flujo rastreado hasta efecto real; **PARCIALMENTE IMPLEMENTADO** = existe efecto pero falta una parte visible, runtime o persistencia; **IMPLEMENTACIÓN SOSPECHOSA** = implementado con fuente de verdad/timing frágil; **NO IMPLEMENTADO** = no hay consumidor activo; **IMPLEMENTADO PERO SIN TESTS** = efecto rastreado sin cobertura de comportamiento.

| Feature | UI | Config | Backend | Funciona | Tests | Acción |
|---|---|---|---|---|---|---|
| Tema claro/oscuro/sistema | Sí | Sí | ThemeManager + ThemeBridge | FUNCIONAL | Parcial | Probar visualmente system/light |
| Color de acento | Sí | Sí | ThemeManager | FUNCIONAL | Parcial | Mantener |
| Color dinámico por artwork | Sí | Sí | Sin lector | NO IMPLEMENTADO | No | Ocultar o implementar extracción→acento |
| Blur de artwork en fondo | Sí | Sí | Sin lector | NO IMPLEMENTADO | No | Ocultar o implementar |
| Sidebar compacta | Sí | Sí | Runtime sólo | PARCIALMENTE IMPLEMENTADO | No | Restaurar al inicio (BUG-019) |
| Tamaño de fuente global | No | Sí | Sin lector | NO IMPLEMENTADO | No | Eliminar o tokenizar |
| Idioma | Sí | Sí | i18n + reinicio | PARCIALMENTE IMPLEMENTADO | Parcial | Refrescar QML o declarar reinicio claramente |
| Volumen | Sí | Sí | VLC | FUNCIONAL | Sí, parcial | Añadir E2E/MPRIS |
| Normalizar volumen | Sí | Sí | Sin lector | NO IMPLEMENTADO | No | Ocultar o aplicar gain/normalización |
| Saltar silencios | Sí | Sí | Sin lector | NO IMPLEMENTADO | No | Ocultar o implementar motor |
| Crossfade | Sí | Sí | CrossfadeManager | IMPLEMENTADO PERO SIN TESTS | Parcial | Añadir E2E local/stream |
| Duración crossfade | Sí | Sí | CrossfadeManager | FUNCIONAL | Sí, parcial | Mantener |
| Reanudar al iniciar | Sí | Sí | SessionManager | IMPLEMENTACIÓN SOSPECHOSA | Parcial | Probar local/stream, seek y fallo |
| Gapless playback | Sí | Sí | Sin lector | NO IMPLEMENTADO | No | Ocultar o implementar prebuffer real |
| Parar al cerrar | Sí | Sí | Sin lector | NO IMPLEMENTADO | No | Corregir BUG-013 |
| Temporizador de apagado | Sí | Sí | SleepTimer | IMPLEMENTADO PERO SIN TESTS | Parcial | Test de reinicio/cancelación |
| Minimizar a bandeja | Sí | Sí | closeEvent/tray | FUNCIONAL | Parcial | Probar sin tray disponible |
| Shuffle | Now Playing | Sí | PlayQueue | IMPLEMENTACIÓN SOSPECHOSA | Sí, parcial | Corregir historial (BUG-009) |
| Repeat off/all/one | Now Playing/MPRIS | Sí | PlayQueue | FUNCIONAL | Sí, parcial | E2E con track ended |
| Ecualizador/preamp/bandas/preset | Sí | Sí | VLC EQ | FUNCIONAL | Sí, parcial | Probar VLC real/errores |
| Proxy | No | Sí | Sin lector | NO IMPLEMENTADO | No | Eliminar o pasar a HTTP/yt-dlp |
| Calidad de stream | No | Sí | Sin lector | NO IMPLEMENTADO | No | Añadir selector y extractor policy |
| Precargar siguiente | No | Sí | extractor/image cache | IMPLEMENTADO PERO SIN TESTS | No | Test de expiración/local/repeat |
| Caché inteligente offline | Sí | Sí | OfflineCacheManager | PARCIALMENTE IMPLEMENTADO | Parcial | Estado/progreso, limpieza y cancelación |
| Límite caché offline | Sí | Sí | Sólo próximo sync | PARCIALMENTE IMPLEMENTADO | No | Aplicar poda al bajar límite |
| Last.fm | Sí | Sí | Inicialización + scrobble | PARCIALMENTE IMPLEMENTADO | Parcial | Corregir runtime (BUG-008) |
| Discord RPC | Sí | Sí | Sólo startup | PARCIALMENTE IMPLEMENTADO | No | Corregir runtime (BUG-008) |
| MPRIS | No | Sí | Sólo startup | PARCIALMENTE IMPLEMENTADO | Parcial | Exponer toggle o quitar config; reconfigurar |
| Letras: alineación | Sí | Sí | NowPlaying VM | FUNCIONAL | No | Añadir binding test |
| Letras: tamaño | Sí | Sí | NowPlaying VM | FUNCIONAL | No | Añadir binding test |
| Letras: interlineado | Sí | Sí | No transferido a QML | NO IMPLEMENTADO | No | Corregir BUG-014 |
| Letras: delay | Sí | Sí | NowPlaying VM | FUNCIONAL | No | Añadir test |
| Letras: auto-scroll | Sí | Sí | NowPlaying VM | FUNCIONAL | No | Añadir test |
| Letras: animation style | Sí | Sí | No transferido a QML | NO IMPLEMENTADO | No | Corregir BUG-014 |
| Letras: glow | Sí | Sí | NowPlaying VM | FUNCIONAL | No | Añadir test |
| Letras: colores activo/inactivo | No | Sí | Sin lector | NO IMPLEMENTADO | No | Eliminar o implementar |
| `last_video_id` | No | Sí | SessionManager | IMPLEMENTACIÓN SOSPECHOSA | Parcial | Derivar de sesión, no duplicar |

## 4. UI/UX Polish Issues

### Sidebar

- **Confirmado:** todas las shortcuts de playlist se activan a la vez (BUG-003).
- **Confirmado:** el estado compact no se restaura al primer frame (BUG-019).
- **Riesgo visual:** la selección de route y playlist necesita una pasada light/dark real; las tokens base sí proceden de `ThemeBridge`.

### Header

- **Confirmado:** queries con `?` se tratan como deep links (BUG-004).
- **Riesgo:** `GlobalSearchBarQml._fetch_suggestions_async()` silencia errores de red (`except Exception: return`, `global_search_qml.py:175-180`); no hay mensaje de “sugerencias no disponibles”.

### Home

- **Confirmado:** ante fallo se queda vacío sin error/retry (BUG-011).
- **Confirmado:** context menus pasan thumbnail como title al añadir a playlist (BUG-006).
- **Accesibilidad:** botones/cards con `MouseArea` no tienen foco/teclado; los botones de Play/Menu aparecen sólo con hover.

### Search

- **Confirmado:** parser de rutas rompe caracteres especiales (BUG-004).
- **Fortaleza:** Search sí tiene loading/error/retry y cancela fetch de categoría anterior.
- **Confirmado:** add-to-playlist tiene parámetro incorrecto (BUG-006).

### Library

- **Confirmado:** error de carga y error creando playlist no dan feedback (BUG-011).
- **Riesgo:** al crear correctamente una playlist se invalida sólo cache local; no se refresca sidebar de playlists recientes.

### Playlist / Album / Artist

- **Confirmado:** Back no conserva identidad de playlist/album/anterior (BUG-002).
- **Confirmado:** add-to-playlist usa thumbnail como title (BUG-006).
- **Riesgo:** errores de carga se registran pero se deben verificar visualmente por pantalla; wrappers tienen `loading`, no un error uniforme.

### Downloads

- **Confirmado:** no hay Retry/Pause/Resume/Cancel en la pantalla de descargas (BUG-012).
- **Confirmado:** archivo borrado fuera de Doremi sigue como completed (BUG-016).
- **Confirmado:** bulk clear desde Settings desincroniza DB/disco (BUG-007).
- **Accesibilidad:** filas, Like, Play y menú son MouseAreas sin teclado/nombre accesible.

### Stats

- **Confirmado:** los números no miden escucha real (BUG-001).
- **Confirmado:** add-to-playlist transmite thumbnail (BUG-006).

### Queue

- **Confirmado:** “Quitar de la cola” ejecuta borrado de descarga (BUG-005).
- **Confirmado:** duplicados resaltan como actuales (BUG-010).
- **Confirmado:** shuffle no distingue ya escuchadas (BUG-009).

### MiniPlayer

- **Confirmado:** controles esenciales no son accesibles por teclado (BUG-015).
- **Riesgo UX:** la acción play/pause durante loading no comunica bien qué ocurre (BUG-017).

### NowPlaying

- **Confirmado:** minimizar se ve afectado por el historial de índices (BUG-002).
- **Confirmado:** letras tienen preferencias decorativas (BUG-014).
- **Accesibilidad:** tabs audio/video, minimizar, controles de transporte, filas Queue y el seek requieren teclado/nombres/tooltip.

### Settings

- **Confirmado:** hay 13 settings sin consumidor y 8 con implementación incompleta/sospechosa (tabla anterior).
- **Confirmado:** Discord/Last.fm muestran cambios de toggle que no aplican en runtime (BUG-008).
- **Confirmado:** “Eliminar descargas” no confirma ni realiza la operación que promete (BUG-007).

### Dialogs

- **Riesgo:** el diálogo legacy “Añadir a playlist” en `QueueController` es QtWidgets activo y usa `QDialog` con estilos propios. Debe verificarse en ambos temas y migrarse sólo después de extraer una acción común (ver refactors).

## 5. State Synchronization Problems

> **Estado histórico de la auditoría.** Las filas de navegación, cola,
> integraciones, descargas, settings y estadísticas se corrigieron en la fase
> de implementación descrita arriba. Se conservan como trazabilidad de las
> fuentes de verdad que no deben volver a duplicarse; no son pendientes
> vigentes salvo las validaciones externas indicadas en el resumen.

| Dato | Fuentes de verdad actuales | Riesgo | Corrección |
|---|---|---|---|
| Ruta actual | `_current_route`, `sidebar.activeRoute`, `stack.currentIndex`, `_nav_history` | Back actualiza sólo índice | Un `NavigationState` con path completo |
| Playlist seleccionada | path, `PlaylistScreenQml._playlist_id`, índice 5 | Back no recupera A/B | Historia de rutas con params |
| Reproducción | VLC `PlayerStatus`, `_current_play_id`, `PlayQueue`, modelos Mini/NowPlaying, MPRIS/Discord/Last.fm | carreras y referencias inyectadas viejas | `PlaybackSession` observable y una única reconfiguración |
| Integraciones | `main_window.*`, `IntegrationsController.*`, `PlaybackController.*` | toggles actualizan sólo una referencia | Propietario único: IntegrationsController |
| Queue actual | índice/identidad `QueueItem`, VM por `videoId` | duplicados se desincronizan | `queue_entry_id` o índice estable |
| Descargas | DB, filesystem, `DownloadManager._tasks`, cache offline | borrado masivo/manual no reconcilia | servicio único de lifecycle/reconciliación |
| Settings | `AppSettings`, Settings VM, controles, instancias ya construidas | se guarda sin aplicar motor | `apply_settings` por dominio con resultado/error |
| Estadísticas | PlayHistory, Song.play_count, `PlayerStatus.position_ms` | historia registra inicio, no escucha | entidades de sesión de escucha |

## 6. Missing Feedback / Loading / Error States

> **Estado histórico.** Home, Biblioteca, pantallas de detalle, Historial,
> Estadísticas y Descargas ya poseen guardas de solicitud, error y reintento;
> la lista siguiente explica el hueco original. Quedan por comprobar en una
> sesión real los mensajes específicos que entregue cada proveedor externo.

- Home y Library: loading sí; error/retry no (BUG-011).
- Crear playlist: no busy, no botón disabled, no toast de éxito/error (BUG-011).
- Sugerencias del header: error de red silencioso.
- Descargas: progreso sí; retry/pause/resume/cancel no están en su pantalla (BUG-012).
- Settings integrations: toggles no muestran conexión, fallo ni que requieren restart (BUG-008).
- Clear downloads: no confirmación, conteo ni fallo parcial (BUG-007).
- Reproductor: loading existe visualmente en artwork, pero las acciones repetidas no comunican la request vigente (BUG-017).
- Lyrics: loading/empty básicos sí; no se diferencia explícitamente “sin conexión”, “no hay letras” y “falló proveedor” salvo texto contenido.

## 7. Accessibility Issues

> **Estado histórico.** Los componentes y superficies enumerados recibieron
> foco, teclado y nombres accesibles durante esta fase, incluidas Home, cola y
> Similares. Persisten las comprobaciones manuales de lector de pantalla,
> contraste y orden de foco real indicadas abajo.

- **Confirmado por código:** MiniPlayer, `MediaCard`, fila Downloads, tarjetas Home, múltiples tabs y controles NowPlaying usan `Rectangle + MouseArea` sin `activeFocusOnTab`, handlers de Enter/Space, `Accessible.role/name` ni tooltip. Ver BUG-015.
- **Confirmado por código:** los iconos de Previous/Next/Expand/Like/Menu dependen visualmente de glyphs y, en varios casos, de hover; no hay etiqueta accesible equivalente.
- **Riesgo visual/manual:** comprobar foco visible en light/dark para `ComboBox`, Slider y menú contextual, y tamaños de target. Los componentes `HeroButton`, `HeaderButton` y `NavigationItem` sí son buenos referentes: tienen foco, teclado y nombre accesible.
- **Diálogos:** validar Escape, foco inicial y foco retornado en cierre; `ModalDialog` necesita una prueba de trap de foco real, no sólo instanciación.

## 8. Persistence Problems

> **Estado histórico.** La restauración de rutas, sidebar compacta, sesión de
> cola y ajustes runtime fue corregida. La sección se mantiene para documentar
> las regresiones que cubren las pruebas.

- Compact sidebar no se restaura en el presenter inicial (BUG-019).
- Back no conserva rutas/params ni pantallas previas (BUG-002).
- `stop_on_close` se persiste pero no se aplica (BUG-013).
- Last.fm/Discord se persisten, pero los cambios vivos no llegan a consumidores existentes (BUG-008).
- Queue/restauración tiene una corrección importante ya implementada: SessionManager repunta queue en MPRIS, MiniPlayer, NowPlaying y controladores (`session_manager.py:56-76`). Falta E2E de playback real y restauración de shuffle/history.
- DB de descargas no se reconcilia con archivos eliminados externamente ni con clear downloads de Settings (BUG-007, BUG-016).
- Offline cache persiste feed/audio, pero no tiene limpieza inmediata al bajar límite ni indicación de estado; el toggle sólo afecta la próxima sincronización online.

## 9. Legacy QtWidgets vs QML

Las rutas principales activas se construyen exclusivamente con presentadores QML; `tests/test_qml_only_routes.py` lo vigila. Aun así continúan en árbol componentes QtWidgets con lógica paralela:

- `ui/screens/{home,library,history,downloads,settings,playlist,album,artist,now_playing,search,stats}.py` y `ui/screens/settings/*` son implementaciones legacy no importadas por `MainWindow` activo.
- `ui/widgets/{mini_player,nav_sidebar,notification_panel,queue_panel}.py` siguen siendo legacy; `test_nav_sidebar.py` todavía prueba `NavSidebar` legacy en vez de `NavSidebarQml`.
- `QueueController.show_add_to_playlist_dialog()` mantiene un `QDialog` QtWidgets activo y estilos propios, así que sí requiere mantenimiento en ambos temas.

No eliminar estos archivos sin una búsqueda de referencias fuera de `MainWindow`, tests y plugins. Prioridad: primero mover la acción activa de add-to-playlist a un componente/QML compartido; luego marcar legacy como deprecated y migrar tests a presenters QML.

## 10. Missing Regression Tests

Las pruebas actuales cubren bien modelos básicos, cola simple, carreras de reproducción concretas y carga de QML. No cubren el contrato completo que se rompe. Añadir, en este orden:

1. Back con ruta completa/params: Playlist A → B → Back; Artist → Album → Back; Search → Playlist → Back; NowPlaying → minimizar.
2. Sidebar: sólo una playlist activa y `activeRoute/currentRoute` consistentes después de Back.
3. Parser/search con `?`, `&`, `=`, `#`, `%`, emojis, Unicode, espacios y query larga.
4. “Quitar de la cola” nunca borra una descarga; cubrir actual/próxima/duplicado/vacía.
5. Todas las ViewModels de context menu emiten `(videoId,title)` para add-to-playlist.
6. Sesión de escucha: inicio, skip, pausa, end natural, seek, cambio rápido y error de stream.
7. Estadísticas suman `listen_time_ms`, no duración de medios.
8. Shuffle después de estar avanzada no reintroduce historial antes de próximas canciones.
9. Duplicados en Queue sólo muestran una fila actual.
10. Toggle Last.fm/Discord en runtime actualiza todas las referencias y maneja fallo.
11. `stop_on_close` × `minimize_to_tray` en las cuatro combinaciones.
12. Restauración inicial de sidebar compacta, queue, repeat/shuffle y seek.
13. Offline cache: enable/disable y cambio descendente de song limit podan correctamente.
14. Clear downloads: raíz + subcarpetas + DB + fallo parcial + tareas activas.
15. Archivo descargado borrado externamente se detecta y ofrece estado de recuperación.
16. Downloads: retry/cancel/pause/resume por estado y feedback.
17. Home/Library/create playlist: loading/error/empty/retry y doble click.
18. Settings: cada setting retenido causa un efecto observable en motor/QML tras reinicio.
19. Componentes QML interactivos: Tab, Enter, Space, Escape, accessible name y disabled state; completar con prueba manual de lector de pantalla.

## 11. Recommended Refactors

1. **NavigationState / Router único.** Sustituir el historial de índices por rutas tipadas y una restauración central. Soluciona BUG-002, BUG-003, BUG-004 y reduce carreras de navegación.
2. **SongAction payload compartido.** Un objeto `{video_id,title,artist,thumbnail_url,source}` para todos los context menus. Soluciona BUG-006 y evita contratos posicionales repetidos.
3. **Queue como historial + actual + próximas.** Primero aplicar el arreglo acotado de shuffle; después separar session history/up-next/autoplay. Soluciona BUG-005, BUG-009 y BUG-010 sin mezclar identidad de canción con ocurrencia.
4. **Playback/listen session.** Registrar tiempos por transición de estado y persistir una escucha final. Soluciona BUG-001 y da una base correcta a Last.fm/Stats.
5. **Download lifecycle service.** Centralizar delete/reconcile/retry/cancel; Settings, Descargas y Queue llaman al mismo servicio. Soluciona BUG-007, BUG-012 y BUG-016.
6. **QML AccessibleButton/IconButton.** Sustituir patrones `Rectangle + MouseArea` de controles críticos. Soluciona BUG-015 de forma sistemática.
7. **IntegrationsController como dueño de instancias.** Implementar `reconfigure()` y eliminar referencias duplicadas. Soluciona BUG-008.

## 12. Priority Roadmap

### P0 — Bloquea una release estable

1. BUG-005: corregir “Quitar de la cola” para que nunca borre descargas.
2. BUG-007: reemplazar clear downloads por borrado DB+filesystem transaccional con confirmación.
3. BUG-002 y BUG-003: ruta completa en Back/sidebar antes de exponer navegación profunda.
4. BUG-004: separar búsquedas de deep links y usar parser seguro.
5. BUG-001: dejar de registrar duración completa al inicio; definir y migrar sesión de escucha.

### P1 — Debe corregirse antes de considerar Doremi pulida

1. BUG-006: payload común de add-to-playlist en todas las pantallas.
2. BUG-008: lifecycle runtime de Last.fm/Discord y feedback.
3. BUG-009 y BUG-010: shuffle sin repetir historial y fila actual por ocurrencia.
4. BUG-011 y BUG-012: errores/retry/busy coherentes para Home, Library, playlists y descargas.
5. BUG-013 y BUG-019: cumplir/restaurar preferencias visibles.

### P2 — Mejora notable de UX/calidad

1. BUG-014: implementar u ocultar settings de letras sin efecto.
2. BUG-015: teclado, foco y accesibilidad de todos los controles críticos.
3. BUG-016: reconciliación DB/filesystem de descargas.
4. BUG-017: feedback de loading y acciones repetidas de reproducción.
5. Convertir todos los settings NO IMPLEMENTADOS de la tabla en implementación verificable u ocultarlos.

### P3 — Nice to have

1. Retirar/marcar código QtWidgets legacy tras demostrar cero referencias productivas.
2. Migrar el diálogo QtWidgets de add-to-playlist a QML compartido.
3. Pasada manual visual: temas claro/oscuro, contraste de iconos, hover/focus, resolución pequeña, VLC real y red inestable.
