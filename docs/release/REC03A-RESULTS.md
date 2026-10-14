# REC-03A — Servicios de metadatos y artwork: resultados

Rama: `recovery/rec03a-metadata-services` → destino `recovery/rec02-data-foundation`.
Base: `38c1a1d1da2ab1f5cc5afc676971cdddbc06487e`. Rescate (lectura): `c00d772` (+ 3 `??`).
PR: apilado sobre `recovery/rec02-data-foundation` (no sobre `main`), abierto, sin fusionar.
Estado: NO VERIFIED (pendiente CI verde). Fecha: 2026-10-14 (UTC). Solo `tmp_path`/`XDG_*` temporales.

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
Sin skips forzados, sin fallos.

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
- `AppDirs` frozen-aware intacto: caché a XDG, nunca a `_MEIPASS` (verificado
  por tests de contención + `is_relative_to`).
- Nativo Rust sin modificar; solo compilado para pruebas (mismo flujo que CI).
- Smoke frozen (`DOREMI_SMOKE_OK` 9/9) no se usa como sustituto funcional;
  queda para CI (AppImage A/B/C + portable) sobre este HEAD.

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

- Workflow pertinente: `linux-appimage.yml` (suite completa + build + AppImage
  + smoke). Cambio mínimo de `paths:` justificado en REPORT §2.
- PR: apilado `recovery/rec03a-metadata-services` → `recovery/rec02-data-foundation`.
  (URL del PR y run se anotan al crear el PR; sin fusionar, sin tags/releases.)
- Estado: **pendiente de verde**. No se declara VERIFIED. Referencia inicial
  405 tests; final esperado 448 (405 + 43) en el run de CI.

## 6. Riesgos (resumen; detalle en REPORT §6)

Packaging real pendiente de bundles CI; rendimiento exige `to_thread` fuera del
hilo Qt; disco solo escribe carátula atómica (verificado); licencias mantienen
**bloqueada** la publicación pública (`mutagen` GPLv2 incluida).

## 7. Árboles intactos

- Principal `Doremi-Rust @ 80aaf1e` (`build/f0b3b-linux-appimage`): limpio.
- REC-02 worktree `@ 38c1a1d`: limpio.
- Rescate `@ c00d772`: solo lectura, `M`/`??` preexistentes intactos, sin venv
  ni builds en él.
- Solo `recovery/rec03a-metadata-services` desde `38c1a1d` contiene cambios.
