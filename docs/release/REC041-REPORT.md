# REC-04.1.1 — Origen de reproducción e historial contextual: informe

Fase: REC-04.1.1 (primera unidad de REC-04.1, contratos de reproducción).
Rama: `recovery/rec041-playback-context` apilada sobre REC-03C exacto
`51e8541c980c2c027239bd0a0f0104bcb7e465dd`.
Worktree: `/home/eirom/Proyectos/Doremi/worktrees/rec041-playback-context`.
Rescate (solo lectura): `/home/eirom/Proyectos/Doremi/Doremi-Rust-Rescate` —
no modificado; solo consultas.
Worktrees previos intactos: rec02 / rec03a / rec03b / rec03c (sin cambios).
PR base: PR #12 (REC-03C, abierto, sin fusionar). PR propio: REC-04.1 apilado
sobre `recovery/rec03c-product-composition`, nunca sobre `main`.
Estado: **VERIFIED (para el alcance validado)** — CI run `39084863494`
(`Linux AppImage (F0B-3B)`, `completed`/`success`) sobre
`b5d55a3599269986f1aba2b9715236023106cf11` publicado en el PR #13.
Alcance validado: suite completa **541 passed in 16.32s** (519 REC-03C +
22 de esta unidad), nativas **17**, packaging regressions **16**,
`git diff --check`, PyInstaller + AppImage Type 2, smoke y persistencia
XDG. NO valida interacción QML/controles ni autoriza publicación
(licencias pendientes; sin fusionar/tags/releases).

## 1. Defecto D1 y alcance

`PlaybackController._persist_listen()` persistía `context_type="queue"`
para toda reproducción (línea 772), descartando la procedencia introducida
en REC-02 (`QueueItem.context_*`, `ListenResult.position_ms`,
`HistoryRepository.add_entry()` contextual, `services/playback_context.py`).

Alcance de esta unidad: **persistencia del origen**, sin QML ni ViewModels,
sin modelos/migraciones, sin Rust, sin CHANGE_D1-D5 ni D8. No emite eventos
globales ni introduce `experience_events`.

## 2. Regla arquitectónica aplicada

**Capturar el contexto cuando el usuario solicita reproducir, nunca
al finalizar la canción.** El contexto viaja dentro de cada `QueueItem`
durante avance manual/automático, shuffle, repeat, reanudación,
reemplazo de cola y skip; la navegación posterior del usuario no reatribuye
el origen. `_persist_listen()` solo lee ese `QueueItem` (incluido en
`ListenResult`) — no recalcúlala desde la ventana ni lee tardíamente la
posición del reproductor.

## 3. Matriz de productores (publ. tras auditoría de contratos)

| # | Productor (boundary) | Contexto | Implementación |
|---|---|---|---|
| P1 | `playlist_qml._on_vm_play_queue` | `playlist` o `smart` + `context_id=_playlist_id` + título | estampado en la construcción de cada `QueueItem` |
| P2 | `album_qml._on_vm_play_queue` | `album` + `context_id=_browse_id` + título | ídem |
| P3 | Reproducción simple (`_play_song_sync` → `_play_song`) | `playback_context(window)` capturado **sincrónicamente** en `_play_song_sync` | fallback aplicado solo a items `unknown`; los productores ya sellados no se reasignan (copia `dataclasses.replace`) |
| P4 | `playlist_qml._on_vm_play_local` → `_play_local_playlist` | `playback_context(main_window)` + override por-metadata | contexto capturado en el boundary; `local_path` preservado |
| P5 | `downloads` → `_play_local_wrapper` → `_play_local` | wrapper inyecta `playback_context`; fallback `{"context_type": "local"}` de llamada directa | sin identidad de colección inventada |
| P6 | `queue_controller.on_play_next/on_add_to_queue` | `playback_context(window)` en el wrapper sincrónico | fallback `"queue"` |
| P7 | `_fetch_and_populate_auto_queue` + expansión watch de `_advance_queue` | `context_type="autoplay"` — nunca heredan colección | estampado explícito |
| P8 | Restauración `PlayQueue.from_dict` / `queue_state.json` | roundtrip completo (asdict → `QueueItem(**m)`) | sin cambios; cubierto por prueba |

Pantallas widget heredadas (`album.py:499`, `playlist.py:618`) NO se tocan:
no se instancian en la arquitectura QML-only de la rama (sesgo probado por
`tests/test_qml_only_routes.py`); son productores muertos.

## 4. Cambios (6 archivos, +87/−6)

- `src/doremi/ui/controllers/playback_controller.py`
  - `_play_song(..., *, context=None)`: fallback filtra las tres claves del
    contrato y solo cubre items `context_type=="unknown"`.
  - `_persist_listen()`: `context_type = item.context_type or "queue"`,
    `context_id/context_title` coercionados a `str` (compatibles con
    `add_entry`), `position_ms = max(0, int(result.position_ms or 0))`.
    `was_played`/`skip_count`/`completed`/`record_play()` intactos; sin
    registros duplicados (la sesión se consume en `finish()`).
  - `_fetch_and_populate_auto_queue` y expansión `_advance_queue`:
    `context_type="autoplay"`.
  - `_play_local`/`_play_local_playlist`/`_play_local_wrapper`: captura en
    boundary y fallback `local` (metadata manda si trae su propio
    `playback_context`).
- `src/doremi/ui/main_window.py`: `_play_song_sync` captura
  `playback_context(self)` una vez, sincrónico, y lo pasa como kwarg.
- `src/doremi/ui/screens/playlist_qml.py`, `album_qml.py`: estampado del
  origen en la construcción de QueueItems.
- `src/doremi/ui/controllers/queue_controller.py`: `context` capturado en
  los wrappers sincrónicos; item sellado en `add_to_queue_async`.
- `.github/workflows/linux-appimage.yml`: rutas aditivas para que el PR
  ejecute la suite representativa (`test_rec041*`, productores, cola,
  persistencia). Sin cambios en jobs.

Contratos NO duplicados ni alterados: `QueueItem`, `PlayQueue`,
`ListeningSession`/`ListenResult`, `HistoryRepository.add_entry`,
`services/playback_context.py` (cero cambios), `PlayHistory`/`Collection`
(sin migraciones nuevas).

Semantic note: `PlayHistory` no guarda `context_title` (el título vive en
`Collection.title`, creado por `add_entry` solo cuando hay id+título y
nunca para `local-list:`). El historial conserva tipo/id/posición; las
pruebas verifican ambos destinos.

## 5. Pruebas (22 nuevas, primero rojas)

`tests/test_rec041_playback_context.py` — SQLite temporal + XDG aislados +
mocks mínimos; sin red (socket/urlopen denegados), sin música real, sin DB
del usuario. Estado previo al fix: 16 rojas / 6 verdes (reproduce D1);
final: 22/22 verdes. Cubre: historial playlist/álbum/smart + `Collection`
por título, fallback sin identidad inventada, captura en boundary
(cambio de pantalla posterior no reatribuye), fallback solo a items sin
sello, avance manual con contexto por elemento, shuffle/repeat intactos,
reemplazo de cola sin reatribución, roundtrip de sesión, skip con
semántica original (`record_play` no invocado), `position_ms` exacto de
`ListenResult`, un registro por canción, persistencia total en SQLite
temporal, productores reales (playlist/álbum/cola/local/autoplay) y
compatibilidad de productores existentes.

## 6. Validación local

- Suite completa: **541 passed** (519 REC-03C + 22 nuevas).
- Nativas + packaging: **33 passed**
  (`test_native_rs.py`, `test_linux_packaging.py`, `test_linux_appimage.py`).
- `git diff --check` limpio; worktree limpio tras commits.
- YAML de workflow validado.

## 7. Riesgos y notas

- Vía `_play_song_sync`, una reproducción disparada desde un panel
  mientras otra pantalla es visible hereda el contexto de la pantalla
  activa (paridad con el rescate, aceptado); nunca inventa identidad:
  contexto vacío/`unknown` queda en tipos no-agregados.
- Compatibilidad: historial antiguo (`context_type="queue"`) convive con
  el nuevo; las consultas de REC-02/03 filtran tipos de colección.
- Commits intermedios `rec041.1`–`rec041.2` quedan intencionalmente rojos
  en la batería de persistencia (pruebas-primero); el árbol final y el PR
  están en 541 verdes.
- No se abordaron D2, D3, D5 ni D8 (fuera de alcance). D4 queda en espera
  de UI (REC-04.3) para consumir reanudación.

## 8. Entregable

PR apilado sobre `recovery/rec03c-product-composition` con los 5 commits
listados en `REC041-RESULTS.md`. Sin fusionar ni etiquetar.
