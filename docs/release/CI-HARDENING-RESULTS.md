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

**VERIFIED para los probes y la matriz ejecutada.** PR
[#16](https://github.com/Eirom16/Doremi-Rust/pull/16), apilado sobre REC043.

- HEAD comprobado: `da49e490e129c0446381465adcf976acf78cd2e8`.
- [Run 40109382295](https://github.com/Eirom16/Doremi-Rust/actions/runs/40109382295): completed/success;
  job `120917722405`.
- Suite: **685 passed**, 36.14 s; nativas **17**, packaging **16**.
- Negativo real: FORCED_SMOKE_FAILURE → CLEAN_ENV_2204=FAIL exit=42 →
  NEGATIVE_PROBE=EXPECTED_FAILURE_42; sin PASS antes de ese fallo.
- Positivos reales: SYSTEM_VLC_ABSENT en ambos contenedores; JSON frozen=true,
  ok=true y los nueve checks obligatorios true. CLEAN_ENV_2204=PASS y
  CLEAN_ENV_2404=PASS; ambos outcomes success, sin error chmod sobre :ro.
- Logs y JSON: artefacto temporal `clean-container-evidence` del run.

Este sellado es posterior a ese HEAD. Se comprobará también el CI de su propio
SHA publicado antes de entregar o crear la rama de UI; el resultado anterior
no se traslada automáticamente al nuevo HEAD. La evidencia final se registra
también en el PR. No se certifica ninguna otra distribución ni audio audible.

## Integridad

Se conserva el snapshot inicial de HEAD/porcelain completos de los nueve
árboles previos, incluidos los cambios existentes de Rescate y REC03A.
Solo se escribe en el nuevo worktree. No hay merges, tags, releases ni
publicación pública. La siguiente rama se creará solo desde el HEAD validado.
