# CI-HARDENING — Resultados

Base: `bbfcb98540d1c510b0ced148170f16303578958d`, comprobada en remoto/local;
[CI REC043](https://github.com/Eirom16/Doremi-Rust/actions/runs/40106418374) success.
Rama `recovery/rec04-ci-hardening`, worktree `rec04-ci-hardening`.

## Commits

- `a8eced7`: regresión de pipelines y validación.
- `52ea2cd`: harness y workflow sin falso PASS.
- `bd7cd89`: validación no desactivable con Python optimizado.
- Dependencia PyYAML explícita de dev y paths de metadata: ver git log.

## Evidencia local

- Rojo: 4 failed / 7 passed; incluye los dos comandos originales del workflow
  devolviendo cero después de Docker=42, y contratos nuevos todavía ausentes.
- Optimización Python: 1 failed antes del cierre (ok=false podía imprimir PASS).
- Batería harness final: **12 passed**.
- Harness + packaging inicial: **27 passed** (antes del caso de optimización).
- Suite completa final: **685 passed**, 46.12 s (673 + 12).
- Nativas y packaging: **33 passed**, 0.62 s (17 + 16).
- Bash syntax y git diff --check: limpios.

Entorno: Python de REC03C solo leído, PYTHONDONTWRITEBYTECODE=1,
QT_QPA_PLATFORM=offscreen y pytest -p no:cacheprovider. Archivos temporales,
sin música ni DB reales. PyYAML se declara como dependencia de tests.

## CI real

Pendiente al redactar este commit. No se declara VERIFIED con mocks ni con el
run de REC043. Deben comprobarse el fallo forzado 42 y JSON completos de Docker
22.04 y 24.04. Los smokes obligatorios no se debilitarán si revelan una
incompatibilidad real. El HEAD final publicado se comprobará por separado,
incluidos cambios documentales posteriores, antes de usarlo como base de UI.

## Integridad

Se conserva el snapshot inicial de HEAD/porcelain completos de los nueve
árboles previos, incluidos los cambios existentes de Rescate y REC03A.
Solo se escribe en el nuevo worktree. No hay merges, tags, releases ni
publicación pública. La siguiente rama se creará solo desde el HEAD validado.
