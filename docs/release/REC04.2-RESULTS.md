# REC-04.2 — Resultados

## Estado de la entrega

Base validada: `96f3a455beec7dc725463b3999207ad04fe09060` (CI-HARDENING).
Rama: `recovery/rec04-ui-playlists`; worktree: `rec042-ui-playlists`.
PR [#17](https://github.com/Eirom16/Doremi-Rust/pull/17), sobre CI-HARDENING.
**VERIFIED para las interacciones y matriz ejecutadas en el HEAD indicado abajo.**
Este sellado documental será comprobado además en su propio CI antes de entregar;
el resultado final de su SHA exacto se anotará en el PR. El verde de otro SHA no
se traslada automáticamente al commit documental.

## Commits por unidad

- `243c864`: pruebas rojas de paginación interactiva/virtualización.
- `7e3af11`: ListView, control accesible y boundary de carga incremental.
- `e924042`: prueba roja de guardado interactivo con guard sincrónico.
- `3e3f677`: guardado, estados, navegación al resultado y cierre ordenado.
- `ec03fe2`: cierre de confirmaciones obsoletas ante recarga/cambio de lista.
- `e32d3b0`: evidencia de interacción en CI y herramienta de medición.
- Los commits documentales posteriores constan en el log de la rama.

## Evidencia roja y posterior

| Cambio | Antes | Después |
| --- | --- | --- |
| Controles reales de paginación/ListView | 2 failed | B1 + paginación/playlist: 39 passed |
| Guardado de sesión desde QML | 1 failed (control ausente) | Comando y controles operativos |
| Cierre ordenado con escritura pendiente | 1 failed | Cleanup espera escritura real |
| Confirmación obsoleta, otra/misma identidad | 2 failed | 2 passed tras cierre en carga |

B2 + paginación/resume/playlist: **91 passed**, 32,05 s.
Interacción QML final: **27 passed**, 11,83 s.
Suite completa final: **712 passed**, 57,30 s (685 + 27).
Nativas **17**, packaging **16**, harness CI **12**: **45 passed**, 2,18 s.
`git diff --check 96f3a45..HEAD`: limpio.

Entorno local: Python 3.12.14, Qt 6.12.0; QT_QPA_PLATFORM=offscreen,
QT_QUICK_BACKEND=software, PYTHONDONTWRITEBYTECODE=1, pytest sin cacheprovider.
El entorno virtual previo solo se lee; DB/config/archivos sintéticos temporales.

## Matriz de interacción real

- 1.007 ocurrencias en SQLite: carga inicial 1.000, clic añade exactamente 7,
  offset=1.000; videoIds duplicados conservados en sus posiciones.
- Clic y Enter durante busy: una solicitud; error/reintento conserva canciones.
- Back y carga rápida de otra identidad: éxito/error tardío no modifica la vista.
- Fila 1.006 añadida: clic produce cola de 1.007 QueueItems con ruta local y
  contexto correctos; la cola anterior de 1.000 no se altera al paginar.
- Colección local offline: sin llamadas a get_playlist; remoto sin botón local.
- Menú contextual por teclado y acción real; confirmaciones antiguas se cierran
  al recargar incluso la misma identidad.
- Sesión válida: diálogo con título, guardar por clic y por Enter, busy/error/
  éxito y apertura del resultado mediante la navegación existente.
- Doble activación inmediata: guard adquirido antes de ejecutar el servicio;
  una playlist. Segundo guardado intencional terminado: nueva identidad.
- Navegar durante append, volver antes/después, cancelar waiter y cerrar:
  guard conservado, escritura no cancelada, resultado no publicado en otra vista.
- Fallos antes de crear, después de crear (append compensado) y después del
  commit: respectivamente 0/0/1 playlists; cero reintentos automáticos.
- Interfaces QAccessible reales: rol Button, nombre, disabled durante busy,
  acción Press sin duplicación y estado de recuento accesible.
- 10.007 filas y scroll al final: 8/17 delegados, cotas <40/<60 verificadas.

## Evidencia exportada

El workflow conserva el artefacto `playlist-ui-interaction-evidence` durante
7 días: playlist-offline-1007.png, session-save-dialog.png,
session-save-busy.png, session-save-success.png, tres capturas de error y
virtualization-10007.json. En local: `/tmp/doremi-rec042-ui-evidence/`.
Las capturas son escenarios sintéticos; no contienen datos del usuario.

La medición fría completa y su procedencia están en REC04.2-PERFORMANCE.json.
Comando reproducible: `python tools/measure_playlist_qml.py REPO_ROOT 1007`
(o 10007). Ejecutar cada muestra en un proceso nuevo, con el mismo entorno Qt.
No escribir en árboles anteriores: el script desactiva bytecode y usa XDG temporal.

## Integridad

Snapshot y comparación de HEAD + porcelain completo de los diez árboles
protegidos (principal, Rescate, REC02, REC03A/B/C, REC041/042/043 y CI-HARDENING):
sin cambios. Los estados preexistentes de Rescate y REC03A se conservan.
ListeningPeriods byte-idéntico y ausencia de cambios DB/migraciones/Rust
comprobados contra la base. Solo se escribe en este nuevo worktree.

## CI real y artefactos comprobados

- HEAD de código e informe inicial: `4923372919f51d720e4f94b125487fd5bd62dfb0`.
- [Run 40113678478](https://github.com/Eirom16/Doremi-Rust/actions/runs/40113678478):
  completed/success comprobado; job `120930430478`.
- Suite **712 passed**, 43,13 s; nativas **17 passed**, 0,20 s;
  packaging **16 passed**, 0,18 s. Sin skips forzados.
- SMOKE_A/B/C, FUSE, X11_XVFB y persistencia XDG: PASS en el alcance de sus
  probes. No equivalen a probar controles de playlist ni audio audible.
- Negativo Docker real: CLEAN_ENV_2204=FAIL exit=42 seguido de
  NEGATIVE_PROBE=EXPECTED_FAILURE_42, sin falso PASS.
- Docker 22.04 obligatorio y 24.04 informativo: ambos PASS real,
  SYSTEM_VLC_ABSENT, JSON ok=true/frozen=true y los nueve checks true.
  Se descargaron y verificaron ambos JSON y logs del artefacto
  [clean-container-evidence](https://github.com/Eirom16/Doremi-Rust/actions/runs/40113678478/artifacts/12567598019).
- Se descargó el artefacto
  [playlist-ui-interaction-evidence](https://github.com/Eirom16/Doremi-Rust/actions/runs/40113678478/artifacts/12567468068)
  y se revisaron capturas reales del runner (lista final y error tras commit).
  Métrica CI de 10.007 filas: 8 delegados iniciales, 17 finales; 127,85 ms y
  1.608 KiB RSS incremental en proceso caliente. Las muestras frías locales
  permanecen separadas en el JSON de rendimiento.

GitHub mantuvo el estado global in_progress varios minutos después de cargar
los artefactos y respondió con 502/timeouts al detalle de jobs. Se esperó hasta
comprobar completed/success y obtener el log final. No se canceló ni reejecutó
el run, no se ocultó ningún fallo y no se debilitó ninguna prueba.

Los artefactos temporales expiran a los 7 días; estos resultados y los logs del
run documentan su alcance. El commit de este sellado debe tener CI propio verde
antes de la entrega, sin commits adicionales no comprobados después.
