# REC-04.1.3 + REC-04.1.4 — Resultados

Fecha: 2026-10-24. Rama `recovery/rec043-playback-pagination`.
Worktree `/home/eirom/Proyectos/Doremi/worktrees/rec043-playback-pagination`.

## HEAD inicial y preparación

`c58cc97f7bdb473a804c582027da4d3a6ca95048`, PR
[#14](https://github.com/Eirom16/Doremi-Rust/pull/14), confirmado de nuevo por
metadata del PR, ls-remote y estado local antes de crear la rama.
CI de ese HEAD: [40055058283](https://github.com/Eirom16/Doremi-Rust/actions/runs/40055058283),
`completed / success`. Baseline 601 / 17 nativas / 16 packaging.

## Commits independientes

| Commit | Unidad y resultado |
|---|---|
| `342dfad` | A: batería de regresión de rutas locales y resultados obsoletos |
| `0bdac44` | A: disponibilidad real, rutas en cola, fallback y guards |
| `7e83589` | B: regresiones del contrato incremental |
| `7389504` | A: descartar también errores tardíos antes de consultar caché |
| `59f31a4` | B: append de filas, cursor, estados y generación |
| `d0f97ff` | D6: regresiones de descarga de identidades locales |
| `b6658d2` | D6: política central antes de programar o cambiar estado |
| `051a362` | D7 y deuda Docker: auditoría, contrato y propuesta aislada |
| `1a2b082` | B: total desconocido y snapshots de descargas, refresh misma identidad |
| `9db7f10` | A: contexto local_ capturado en el productor |
| `a6e0adf` | CI: paths aditivos de código, pruebas y documentos |
| `ef34c1b` | REPORT/RESULTS con evidencia local completa |
| `6d63d7e` | Primer sellado CI (antes del cierre de semántica offline) |
| `2be870b` | A: conservar boundary de fallo/skip para medios locales desaparecidos offline |

HEAD de código probado localmente:
`2be870b19a9bd21e5ce7eb9ea9584c5e20b6c625`.
Los commits documentales posteriores se identifican en git log y en el PR.
Ningún commit de las fases anteriores se reescribe.

## Archivos

- Reproducción: `services/local_playback.py`, `controllers/playback_controller.py`,
  `screens/playlist_qml.py` (bajo `src/doremi`).
- Paginación: `screens/playlist_qml.py`, `viewmodels/playlist_vm.py`.
- D6: `services/collection_identity.py`, `controllers/download_controller.py`;
  la clasificación se reutiliza en la paginación.
- Pruebas nuevas: `tests/test_rec043_local_playback.py`,
  `tests/test_rec043_pagination.py`, `tests/test_rec043_download_safety.py`.
- Un fixture de `tests/test_rec041_playback_context.py` utiliza ahora un
  archivo sintético temporal existente, manteniendo sus aserciones de contexto.
- `.github/workflows/linux-appimage.yml`: solo filtros de paths, sin reparar
  silenciosamente el harness Docker.
- Documentos `docs/release/REC043-{REPORT,RESULTS,SAFETY}.md`.

No se modifica el formato de QueueItem, QML, esquema, migraciones o Rust.
NavigationController/MusicPlayer y el servicio de D7 permanecen intactos.

## Pruebas rojas reales

| Bloque | Estado anterior a su arreglo |
|---|---|
| D2 inicial, batería de 21 casos contra c58cc97 | **13 failed / 8 passed** |
| D2 error tardío de DB → caché | **1 failed** |
| D2 origen local_ durante cambio de ruta | **1 failed** |
| D2 medio importado/recuperado desaparecido offline | **2 failed / 1 passed** |
| D2 metadatos local_ sin archivo offline | **1 failed / 1 passed** |
| B contrato inicial | **16 failed** |
| B filas previas / refresh de contadores / retry explícito | **3 failed** |
| B cancelación dejando filas de otra identidad | **1 failed** |
| B contador parcial sin total | **1 failed** (denominador 3/0) |
| D6 identidades locales y remotas | **17 failed / 6 passed** |

La primera invocación de A detectó un fixture qapp faltante (21 errores de
setup), que se corrigió y no se contabiliza como roja de producto. La repetición
contra la base exacta sustituyó temporalmente los dos archivos Python en el
worktree nuevo y los restauró con finally; no se tocó ningún árbol anterior.
Los cierres de errores/cancelación/contexto se probaron antes de implementarlos.

## Validación local final

Entorno existente leído sin instalar dependencias ni escribir en él:
`/home/eirom/Proyectos/Doremi/worktrees/rec03c-product-composition/.venv/bin/python`.
Imports desde src del worktree REC043. Variables
`QT_QPA_PLATFORM=offscreen`, `PYTHONDONTWRITEBYTECODE=1` y flag
`-p no:cacheprovider` en todas las invocaciones pytest. SQLite y archivos
sintéticos temporales, red/extractor/VLC simulados; sin DB o música reales.

| Bloque | Comando (python -m pytest) | Resultado |
|---|---|---|
| A, B, D6, contexto REC041 y reanudación REC042 | `tests/test_rec043_local_playback.py tests/test_rec043_pagination.py tests/test_rec043_download_safety.py tests/test_rec041_playback_context.py tests/test_rec042_collection_resume.py -q` | **129 passed**, 21.77 s |
| Integración ampliada anterior al último cierre | mismos REC043 + REC041/REC042, playback_request_races, playlist_qml, controllers y REC03C playlist/listening_stats | **203 passed**, 30.75 s |
| Cierre de productor local_ + contratos de contexto/Playlist | `tests/test_rec043_local_playback.py tests/test_rec041_playback_context.py tests/test_playlist_qml.py -q` | **53 passed**, 5.03 s |
| Cierre de contadores/refresh B + contratos Playlist | `tests/test_rec043_pagination.py tests/test_playlist_qml.py -q` | **31 passed**, 3.64 s |
| Suite completa final | `tests/ -q` | **673 passed**, 46.57 s (601 + 72) |
| Nativas + packaging | `tests/test_native_rs.py tests/test_linux_packaging.py tests/test_linux_appimage.py -q` | **33 passed**, 0.95 s (17 + 16) |
| Diff | `git diff --check` | limpio |
| Workflow | YAML + comparación de todos los paths modificados | válido y cubierto para pull_request/push (se conserva restricción de rama push) |
| Servicio D7 | comparación de bytes con c58cc97 | idéntico |

Baterías nuevas: A 26 casos, B 23, D6 23 (72 en total). Incluyen Play/Shuffle/fila,
las cuatro clases de colección local, remoto online, archivos ausentes/vacíos/
directorios, bandera de descarga insuficiente, orden y duplicados, 1007
ocurrencias offline sobre SQLite, señales de inserción, concurrencia de página,
refresh con mismo/diferente ID, errores tardíos y cancelación, retry y contexto.
La suite mantiene las protecciones de reanudación/seek de REC042.

Logs operativos locales: `/tmp/rec043-*.log`. Las carreras usan asyncio.Event;
los tests de filas comprueban señales Qt, no equivalen a verificación visual.

## CI y publicación

**VERIFIED para D2, contrato incremental B y D6 en el alcance automatizado.**
D7 está auditado/especificado, con implementación de UI diferida; no se declara
un guard inexistente ni funcionalidad visual verificada.

PR [#15](https://github.com/Eirom16/Doremi-Rust/pull/15), base
`recovery/rec042-navigation-resume` exacta, nunca main.

| Evidencia remota comprobada | Resultado |
|---|---|
| HEAD de rama | `2be870b19a9bd21e5ce7eb9ea9584c5e20b6c625` |
| Checkout de integración del PR | `c17af7b4204ec7ecbdb47b8a9491adf17603b5a5` |
| Run | [40105872522](https://github.com/Eirom16/Doremi-Rust/actions/runs/40105872522) — completed / success |
| Job | `120907320158` — completed / success |
| Suite completa | **673 passed**, 35.61 s |
| Nativas | **17 passed**, 0.18 s |
| Packaging | **16 passed**, 0.17 s |
| Bundle | PyInstaller/AppImage; smoke A/B/C, FUSE, X11, VLC y persistencia confirmados en logs |

Este sellado documental es posterior al HEAD de la tabla. Se comprobará su
propio CI antes de entregar y el HEAD/run exactos se registrarán también en el
PR; no se infiere su resultado del run de código. La entrega no requiere ni
realiza merge del PR.

Los logs de este run vuelven a mostrar `chmod: Read-only file system` en los
probes Docker, aunque el paso termina verde. Se excluye esa compatibilidad
Docker de lo certificado; sí se informan los smokes ejecutados realmente.

El workflow representativo ejecuta suite completa, nativas, packaging,
PyInstaller/AppImage y sus smokes. Los nuevos paths incluyen ambos helpers,
PlaylistViewModel, DownloadController, tests REC043 y todos estos documentos;
playlist_qml/playback_controller y la prueba REC041 ya estaban cubiertos.

Los marcadores Docker heredados NO prueban compatibilidad de contenedor
limpio. Defecto y reparación aislada propuestos en [REC043-SAFETY.md](REC043-SAFETY.md).
No se modifica ese probe en esta unidad ni se usa su falso PASS como evidencia.

## Integridad y estado de seguridad

Después de las pruebas se compararon HEAD y estado porcelain completo con el
snapshot previo. Los ocho árboles anteriores son idénticos:

| Árbol | Estado conservado |
|---|---|
| Doremi-Rust principal | limpio, HEAD 80aaf1ed |
| Doremi-Rust-Rescate | solo lectura, HEAD c00d772f y sus 137 entradas previas de estado |
| rec02-data-foundation | limpio, HEAD 38c1a1d1 |
| rec03a-metadata-services | HEAD e657b06c y sus 70 entradas no seguidas previas de .venv |
| rec03b-data-repositories | limpio, HEAD 03324773 |
| rec03c-product-composition | limpio, HEAD 51e8541c |
| rec041-playback-context | limpio, HEAD a4cb9f23 |
| rec042-navigation-resume | limpio, HEAD c58cc97f |

D6 implementado; D7 auditado y diferido al futuro boundary de UI, sin lock ni
cambio de idempotencia/transacciones. Riesgos: datos mutables entre offsets,
reproducción del rango cargado, archivos que desaparecen y probe Docker no
validado. Contratos y límites: [REC043-REPORT.md](REC043-REPORT.md).

Siguiente paso recomendado: corregir el harness Docker en una unidad aislada y
validarlo realmente; después, con alcance explícito, conectar la UI incremental
y el guard de guardado. No se inicia REC-04.2 ni REC-04.3 aquí. Sin merges,
tags, releases o publicación pública; las licencias continúan pendientes.
