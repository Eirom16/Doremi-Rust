# REC-04.1.1 — Resultados

Fecha: 2026-10-17 · Worktree:
`/home/eirom/Proyectos/Doremi/worktrees/rec041-playback-context`.

## Commits (apilados sobre `51e8541` REC-03C exacto)

1. `33fee1b` — `test(rec041.1)`: batería roja que reproduce D1
   (22 casos: origen, boundary, ciclo de cola, persistencia).
2. `082c9a3` — `fix(rec041.2)`: productores estampan el origen en el
   boundary (playlist/smart, álbum, cola, locales, autoplay, fallback).
3. `553853e` — `fix(rec041.3)`: persistencia contextual vía `QueueItem` +
   `ListenResult.position_ms` (sin `"queue"` fijo, sin lectura tardía).
4. `dcebfe4` — `ci(rec041.4)`: rutas aditivas en el workflow
   representativo (`test_rec041*`, productores, cola, persistencia).
5. `b5d55a3` — `docs(rec041.5)`: REPORT/RESULTS.
6. (sellado post-CI) `docs(rec041.6)`: VERIFIED con run `39084863494`.

HEAD final tras docs: ver `git log --oneline -6` en el worktree.

## Archivos modificados

- `src/doremi/ui/controllers/playback_controller.py`
- `src/doremi/ui/controllers/queue_controller.py`
- `src/doremi/ui/main_window.py`
- `src/doremi/ui/screens/playlist_qml.py`
- `src/doremi/ui/screens/album_qml.py`
- `.github/workflows/linux-appimage.yml` (solo `paths`, aditivo)
- `tests/test_rec041_playback_context.py` (nuevo, 22 casos)
- `docs/release/REC041-REPORT.md`, `docs/release/REC041-RESULTS.md` (nuevos)

## Pruebas

| Bloque | Comando | Resultado |
|---|---|---|
| Batería REC-04.1 (antes del fix) | `pytest tests/test_rec041_playback_context.py` | 16 failed / 6 passed — reproduce D1 |
| Batería REC-04.1 (final) | ídem | **22 passed** |
| Suite completa | `pytest tests/ -q` | **541 passed** (519 + 22) |
| Nativas + packaging | `pytest tests/test_native_rs.py tests/test_linux_packaging.py tests/test_linux_appimage.py -q` | **33 passed** |
| `git diff --check` | — | limpio |
| Workflow YAML | `yaml.safe_load` | OK |

Entorno local: interprete del worktree REC-03C `.venv`
(pytest 9.1.1, pytest-asyncio 1.4 strict con marcadores explícitos),
`QT_QPA_PLATFORM=offscreen`, `PYTHONDONTWRITEBYTECODE=1`,
`-p no:cacheprovider`. Sin DB/música/config reales ni red en las pruebas.

## CI

Workflow `linux-appimage.yml` (`Linux AppImage (F0B-3B)`): suite completa +
nativas + packaging + PyInstaller/AppImage. Filtros `paths` ampliados para
que el PR ejecute la suite representativa con los archivos de esta unidad.

| Evidencia (PR #13) | Valor |
|---|---|
| Run | `39084863494` — https://github.com/Eirom16/Doremi-Rust/actions/runs/39084863494 |
| Evento / conclusión | `pull_request` / `completed` + `success` |
| SHA verificado | `b5d55a3599269986f1aba2b9715236023106cf11` (`docs(rec041.5)`) |
| Suite completa | **541 passed in 16.32s** (519 REC-03C + 22 nuevas) |
| Nativas | **17 passed in 0.18s** |
| Packaging (portable+appimage) | **16 passed in 0.15s** |
| `git diff --check` | limpio (paso de CI) |

Estado: **VERIFIED (para el alcance validado)**.

## Integridad de worktrees

- `rec041-playback-context`: activo, limpio tras commits.
- `rec02-data-foundation`, `rec03a-metadata-services`,
  `rec03b-data-repositories`, `rec03c-product-composition`: sin cambios.
- `Doremi-Rust-Rescate`: solo lectura; sin escrituras.
- Principal `Doremi-Rust` (worktree build/f0b3b): sin cambios.

## Estado

- [x] Matriz de productores verificada contra contratos reales.
- [x] Pruebas rojas que reproducen D1 antes del fix.
- [x] Productores e historial contextual implementados.
- [x] Suite local verde (541) + nativas/packaging (33).
- [x] PR #13 creado + CI verde (run `39084863494` success, 541/17/16)
      → **VERIFIED para el alcance validado**.
