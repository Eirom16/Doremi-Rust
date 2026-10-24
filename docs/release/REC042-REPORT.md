# REC-04.1.2 — Navegación offline y reanudación segura

Fecha: 2026-10-23. Rama `recovery/rec042-navigation-resume`.
Worktree: `/home/eirom/Proyectos/Doremi/worktrees/rec042-navigation-resume`.

## Preparación y procedencia

Se consultó el PR [#13](https://github.com/Eirom16/Doremi-Rust/pull/13)
antes de crear la rama. Su HEAD publicado era
`a4cb9f23e8f55149f084e12ce0b2bfc996e92434`, coincidente con el fetch
remoto. El último CI documental de ese SHA, ejecución
[39085705408](https://github.com/Eirom16/Doremi-Rust/actions/runs/39085705408),
estaba `completed / success`, incluido el job AppImage. No se dedujo ese
estado de los informes anteriores, que citaban una ejecución de otro SHA.
El worktree nuevo parte exactamente de ese HEAD; REC-04.1.1 no se reescribe.

## REC-04.1.2A — D3

`NavigationController.should_show_offline_state(route, params=None,
*, is_connected=None)` centraliza la política. Los callers antiguos con
solo `route` conservan el bloqueo conservador. La nueva navegación usa los
parámetros de su destino, nunca los de `_current_path` anterior.

Solo `playlist` admite la excepción de colección local:

- `session:` valida estructura, límites de IDs y cutoff mediante el parser
  existente de `ListeningPeriods`.
- `local-list:` y `local_` requieren sufijo no vacío compuesto por letras,
  números, guion o guion bajo, compatibles con las identidades producidas.
- `smart:` requiere una regla de `SMART_TITLES`.

Las rutas externas, fragmentos y los IDs de query repetidos se rechazan como
rutas internas; el fallback existente sigue siendo Home. Identidades vacías,
malformadas o remotas no reciben el bypass. No cambian `ONLINE_ROUTES` ni las
reglas de las otras pantallas.

Una navegación permitida limpia `_offline_blocked_path`. La pérdida de red
consulta la misma política con el valor explícito de la transición, conserva
la query remota para reintentar y mantiene visible una colección local. Esta
última se recarga sin entrada de historial ni acción de reanudación para
aplicar el filtrado de disponibilidad de REC-03C, también a smart. Los loaders
locales siguen resolviendo SQLite/filesystem sin YouTube Music. Atrás conserva
la identidad y el orden del historial.

Prueba roja inicial: 10 fallos / 14 pases. La prueba adicional de pérdida de
red sobre smart falló antes de añadir la recarga (1 fallo). Batería final:
25 pases.

## REC-04.1.2B — D4 y decisión de compatibilidad

Se inspeccionaron `home_composer.personalized_home()`,
`ExperienceRepository.continue_listening()` y `_resume_collection()` en el
árbol Rescate, exclusivamente mediante lectura. El contrato real es:

| Parámetro | Significado |
|---|---|
| `resume` | videoId del último intento dentro de la colección |
| `position` | posición en milisegundos; el productor emite cero al completar |
| `next=1` | el intento anterior terminó: seleccionar el siguiente miembro |
| `next=0` / ausente | seleccionar el miembro indicado por `resume` |

Fue viable implementar el mínimo sin cambios de señales, QML, ViewModels,
modelos ni migraciones: los modelos ya exponen `tracks.all_items()`, y
`MusicPlayer.play_url()` ya espera el evento de inicio de VLC. No se trasplantó
el seek sin protección de Rescate ni su autoplay de navegación.

Cambios de contrato:

1. Navegación mantiene un token de intención, invalidado al elegir otra ruta,
   incluso una ruta bloqueada. `_current_nav_task` conserva su cancelación;
   el token protege también frente a loaders que absorben la cancelación.
2. La selección comprueba `_load_generation`, identidad de pantalla y VM
   cargado, sin error. Una reproducción elegida durante la animación o carga
   invalida la reanudación. Se exige pertenencia del videoId al conjunto
   cargado; si está ausente, no se cambia la cola. `next=1` avanza una sola
   posición dentro de ese conjunto, sin wrap; un valor no reconocido no
   dispara reproducción.
3. Los `QueueItem` llevan tipo/ID/título explícitos y las rutas locales ya
   disponibles en tracks o `local_meta`. Se llama una sola vez a `_play_song`
   con cola explícita, reutilizando el límite existente de ListeningSession y
   persistencia REC-04.1.1. No se añade escritura de historial en navegación.
4. Sin conexión se exige archivo local existente para el destino y se omiten
   de la cola los miembros no disponibles. Una bandera de descarga sin archivo
   no basta. No se inicia extracción remota para esos miembros.
5. `MusicPlayer.seek(position_ms, *, is_current=None)` añade una comprobación
   opcional dentro de `_play_lock`, inmediatamente antes de tocar VLC. Los
   callers anteriores siguen siendo válidos. La reanudación comprueba el token
   de navegación, generación de carga, identidad del objeto de cola,
   `_current_play_id`, videoId del medio y estado PLAYING. Esto cierra la
   carrera de comprobar antes de esperar el lock y ejecutar después de un
   reemplazo. No cambia el pipeline de reproducción ni sus señales.
6. Posición acepta solo enteros decimales no negativos de hasta 18 dígitos;
   un valor inválido/negativo inicia desde cero. Se acota a la duración conocida
   y a la longitud real de VLC dentro del lock. `next=1` siempre comienza desde
   cero. Nunca se hace seek antes de que termine el inicio del medio ni cuando
   VLC no informa longitud positiva.
7. Historial/sidebar y `_offline_blocked_path` guardan solo la ruta de colección:
   `resume`, `position`, `next` y `autoplay` son acciones de una sola navegación.
   Atrás/reconexión no repiten reproducción; `autoplay` no está implementado.

Prueba roja B, repetida con la batería final contra el código A: 23 fallos /
10 pases. La prueba adicional de selección durante la animación falló también
contra la primera implementación B, y se corrigió antes del commit. Batería
final: 33 pases.

## Límites y riesgos pendientes

- D2 permanece pendiente: no se corrige la pérdida de rutas locales del
  pipeline global ni los productores de reproducción manual existentes.
  Este nuevo consumidor conserva los campos que ya recibe.
- Se reanuda solo sobre los miembros de la página cargada (máximo existente
  de 1000). Un videoId fuera de ella no se busca ni se reproduce por fallback.
- En colecciones con videoId repetido se usa la primera ocurrencia, como en
  Rescate: la ruta no contiene identidad de ocurrencia. `next` opera en el
  orden visible, incluido el filtrado offline existente.
- Si VLC inicia sin longitud positiva, se omite el seek; no se inventa una
  duración ni se deja un seek diferido que pueda aplicarse a otra pista.
- Los tests usan VLC/red simulados y archivos sintéticos, no demuestran audio
  audible ni validación de dispositivo de audio real.
- Sin Home nuevo, estadísticas, `experience_events`, QML, ViewModels, modelos,
  migraciones o Rust. Sin REC-04.1.3 ni REC-04.2.
- La publicación pública continúa bloqueada por licencias. No merge, tags ni
  releases. El AppImage del CI es evidencia temporal del workflow existente.

## Evidencia e integridad

Ver [REC042-RESULTS.md](REC042-RESULTS.md) para comandos, commits, resultados y
estado preciso del CI. Antes y después se compararon HEAD y salida completa
`git status --porcelain=v1 --untracked-files=all` de todos los worktrees
anteriores y de Rescate. Sus estados previos se conservan, incluidos los
cambios existentes de Rescate y los archivos no seguidos de `.venv` en REC-03A.
Solo se escriben cambios de producto en el worktree nuevo.
