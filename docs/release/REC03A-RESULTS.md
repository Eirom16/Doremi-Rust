# REC-03A — Servicios de metadatos y artwork: resultados

Rama: `recovery/rec03a-metadata-services` → destino `recovery/rec02-data-foundation`.
Base: `38c1a1d1da2ab1f5cc5afc676971cdddbc06487e`. Rescate (lectura): `c00d772` (+ 3 `??`).
PR: `https://github.com/Eirom16/Doremi-Rust/pull/10` apilado sobre
`recovery/rec02-data-foundation` (no sobre `main`), abierto, sin fusionar.
Código evaluado: `48ec6214458c1aa91e92ca69209b71e6c1deaaf2`.
Estado: VERIFIED (cierre documental post-CI). Fecha: 2026-10-14 (UTC). Solo `tmp_path`/`XDG_*` temporales.

## 1. Pruebas nuevas (43 passed)

Comando (venv aislado del worktree, Python 3.12.14):

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/test_rec03a_metadata_services.py -q
```

Resultado: **43 passed in 0.81s**.

Cobertura por control:

- Distribución: `test_pyproject_declares_mutagen`,
  `test_specs_collect_mutagen_submodules[doremi.spec/doremi-linux.spec]`,
  `test_mutagen_format_readers_importable`, `test_services_import_without_network`.
- `artist_credits` (10): comas estructuradas intactas; **mismo nombre distinto
  id preservado** (`UC_A`+`UC_B` → ambos); mismo id deduplicado; `feat/ft`
  legacy; `&` no partido; 5 variantes `unknown` filtradas; `dict` único +
  `browseId/channelId`; inválidos omitidos + sin escrituras.
- `artwork` (10): dedup + límite 4; `explicit` domina; `file://` existe/missing;
  ruta plana existe/missing; hit md5 bajo `artwork_cache` + `is_relative_to`;
  hit offline bajo `cache/offline/artwork`; 6 `video_id` inválidos rechazados;
  miss remoto = passthrough sin red (urlopen mockeado a fallo); todo lo
  resuelto desde caché contenido bajo `XDG_CACHE_HOME`.
- `local_metadata` (15): WAV etiquetado (título/artista/álbum/1000ms,
  JPEG ≤1024px); no-modifica-audio + reuse sin re-codificar (mtime igual);
  dañado/missing → defaults; sin tags → stem; **>16 MiB no llama a
  `Image.open`**; **8 hilos concurrentes → 1 URL, JPEG `verify()` OK, sin
  `*.tmp`**; solo `artwork/` escrito (data/config intactos, música intacta);
  contrato síncrono (`not iscoroutinefunction`, sin `async def`); `_first`
  trunca a 500.

## 2. Suite completa + nativas + packaging

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/ -q
```

Resultado: **448 passed in 17.82s** (405 baseline REC-02 + 43 nuevas).
Sin skips forzados, sin fallos. CI AppImage confirma 448 sobre el mismo código.

Nativas (wheel `maturin build --release --locked`, instalado en venv):

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/test_native_rs.py -q
```

Resultado: **17 passed in 0.36s**. Wheel:
`dist/doremi_native_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl`.

Packaging Python:

```
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m pytest tests/test_linux_packaging.py tests/test_linux_appimage.py -q
```

Resultado: **16 passed in 1.02s** (validan rutas empaquetadas, no el binario).

Controles extra:

- `git diff --check`: OK.
- `python -m py_compile doremi.spec doremi-linux.spec`: OK.
- `mutagen` readers (`mp3/flac/mp4/ogg/wave` + `File`): OK.
- `collect_submodules("mutagen")` cubre 36 módulos
  (`aac/ac3/aiff/apev2/asf/dsdiff/dsf/easyid3/easymp4/flac/id3/m4a/.../wave/wavpack`).

Entorno: venv `/home/eirom/Proyectos/Doremi/worktrees/rec03a-metadata-services/.venv`
(Python 3.12.14, `pip install ".[dev]"` + `maturin`, wheel nativo instalado).
Rescate no usado como entorno (prohibido); `.venv` del worktree no se commitea
(`dist/` ignorado, `.venv/` sin añadir al índice).

## 3. Empaquetado / nativo

- Sin cambios en `datas/binaries/excludes`, QML, launchers, instaladores,
  `native_rs/`, `config/paths.py`, `db/*`. Impacto: +`mutagen` en deps y frozen.
- PyInstaller procesó los imports ocultos de `mutagen` en los tres bundles:
  `mutagen-1.48.1` instalado desde `pyproject` y logs con
  `Analyzing hidden import 'mutagen...'` más
  `Adding imports: [..., 'mutagen', ...]` (AppImage, Linux portable y Windows
  portable verificados en §5).
- `AppDirs` frozen-aware intacto: caché a XDG, nunca a `_MEIPASS` (verificado
  por tests de contención + `is_relative_to`).
- Nativo Rust sin modificar; solo compilado para pruebas (mismo flujo que CI).
- Smoke frozen (`DOREMI_SMOKE_OK` 9/9) no equivale a prueba funcional
  interactiva; valida arranque y contenido del bundle (ver límites en §6).

## 4. Archivos y diff

`git diff --stat HEAD` (más 4 nuevos sin índice aún):

```
 .github/workflows/linux-appimage.yml | 8 ++++++++
 doremi-linux.spec                    | 5 +++++
 doremi.spec                          | 5 +++++
 pyproject.toml                       | 1 +
 src/doremi/services/artist_credits.py (nuevo, idéntico a rescate)
 src/doremi/services/artwork.py (nuevo, idéntico a rescate)
 src/doremi/services/local_metadata.py (nuevo, +docstrings contrato)
 tests/test_rec03a_metadata_services.py (nuevo, 43 tests)
 docs/release/REC03A-REPORT.md + REC03A-RESULTS.md
```

`artist_credits.py` / `artwork.py`: `diff -u` vs rescate vacío.
`local_metadata.py`: solo docstrings añadidos (síncrono/atomicidad/límite).

## 5. CI

- Cambio mínimo de `paths:` en `linux-appimage.yml` justificado en REPORT §2;
  los tres workflows dispararon por `pull_request` (no `skipped`).
- PR `https://github.com/Eirom16/Doremi-Rust/pull/10` (abierto, sin fusionar,
  código evaluado `48ec6214458c1aa91e92ca69209b71e6c1deaaf2`).

**AppImage — SUCCESS**
`https://github.com/Eirom16/Doremi-Rust/actions/runs/38572766738`
(`pull_request`, job `Linux x86_64 AppImage (type 2)` success):
**448 passed in 14.92s**, nativas **17 passed in 0.16s**, packaging
**16 passed in 0.18s**, generación de AppImage y smoke tests completados
(`DOREMI_SMOKE_OK`, 9/9: directo, launcher, A/B/C).

**Linux portable — SUCCESS**
`https://github.com/Eirom16/Doremi-Rust/actions/runs/38572766826`
(job `Linux x86_64 portable tar.gz` success):
**447 passed, 1 skipped in 9.43s**, nativas **17 passed in 0.13s**,
construcción portable y smoke tests completados (`DOREMI_SMOKE_OK`, 9/9).
Omisión documentada sin ocultarla ni convertirla en fallo: es un skip
condicional preexistente de packaging Linux (`desktop-file-validate` no
instalado / `Linux-only env semantics`; `pytest -q` no expone el motivo),
ajeno a REC-03A; el run AppImage sobre el mismo HEAD registra 448 sin
omisiones.

**Windows portable — SUCCESS**
`https://github.com/Eirom16/Doremi-Rust/actions/runs/38572766754`
(job `Windows x64 portable ZIP` success):
nativas **17 passed in 0.50s**, construcción del portable (`doremi.spec`) y
smoke test completados (`DOREMI_SMOKE_OK`, `ok: True`, 9/9 checks,
`f0b2a.windows.0c80db4d31eb`). Este workflow no ejecuta la suite completa por
diseño (solo nativas + build + smoke). `windows-installer.yml` no dispara por
diseño (`branches: [build/f0b2a-windows-portable]`).

**Pruebas locales:** **448 passed**, incluyendo 43 nuevas
(`tests/test_rec03a_metadata_services.py` 43 passed; suite completa 448;
nativas 17; packaging 16).

Estado: **VERIFIED** con los límites de §6. Referencia inicial 405 tests;
final verificado 448 en AppImage (447 + 1 skipped documentado en portable).

## 6. Límites explícitos de VERIFIED (resumen; detalle en REPORT §6)

- Smoke test no equivale a prueba funcional interactiva (solo arranque/contenido).
- Persisten advertencias QML preexistentes de propiedades nulas.
- `read_metadata()` debe ejecutarse fuera del hilo principal de Qt cuando se integre.
- No están recuperados los repositorios, controladores ni consumidores QML aplazados.
- Publicación pública bloqueada por licencias (`mutagen` GPLv2 incluida).
- Packaging verificado en los tres bundles CI (§5); disco solo escribe carátula
  atómica sin modificar la biblioteca.

## 7. Árboles intactos

- Principal `Doremi-Rust @ 80aaf1e` (`build/f0b3b-linux-appimage`): limpio.
- REC-02 worktree `@ 38c1a1d`: limpio.
- Rescate `@ c00d772`: solo lectura, `M`/`??` preexistentes intactos, sin venv
  ni builds en él.
- Solo `recovery/rec03a-metadata-services` desde `38c1a1d` contiene cambios.
