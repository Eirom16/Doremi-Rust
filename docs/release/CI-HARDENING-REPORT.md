# CI-HARDENING — Probes Docker verificables

Base revalidada: `bbfcb98540d1c510b0ced148170f16303578958d`, REC043/PR #15.
Su run `40106418374` estaba completed/success antes de crear el worktree
`rec04-ci-hardening`, rama `recovery/rec04-ci-hardening`.

El falso positivo se reproducía ejecutando los comandos reales del workflow
con un Docker simulado que salía con 42: el pipeline exterior devolvía cero
y seguía imprimiendo PASS. Además, el chmod se aplicaba al montaje :ro y el
check de VLC usaba un `&& exit 1 || echo`, que también podía ocultar el fallo.

Ahora el workflow invoca un harness común:

- `probe-clean-env.sh`: montaje original :ro, scripts :ro y directorio de
  evidencia escribible; pipefail, salida original de Docker/tee, limpieza de
  reportes anteriores, validación estricta de JSON y marcador antes de PASS.
- `probe-container.sh`: copia temporal del AppImage antes de chmod, checksums
  original/copia en logs, sistema sin libvlc/libvlccore en ldconfig, smoke real
  del ejecutable congelado con XDG temporal y pipes protegidos.
- `validate-smoke.py`: exige ok/frozen true y los nueve checks obligatorios
  por nombre y booleano estricto. La validación no depende de assert, por lo
  que PYTHONOPTIMIZE no puede desactivarla.

Ubuntu 22.04 sigue siendo obligatorio. Ubuntu 24.04 sigue siendo informativo
(continue-on-error), pero el harness devuelve fallo y lo imprime explícitamente;
el workflow registra los outcomes reales. Un fallo informativo no se presenta
como compatibilidad validada. Evidencia JSON/log se conserva con always() en
un artefacto temporal, incluso ante fallos del probe.

El probe negativo usa Docker real y el AppImage construido: una pipeline interna
forzada debe propagarse con código exacto 42 y marcador FORCED_SMOKE_FAILURE;
se comprueba que no contiene CLEAN_ENV_2204=PASS. Un error de infraestructura
arbitrario no cumple esa prueba negativa.

Pruebas locales usan procesos Docker simulados, archivos sintéticos y shell
real; no equivalen a ejecutar Docker. Docker no está instalado localmente.
El workflow remoto es la fuente de evidencia de contenedores reales. Los
checks de bundle no certifican una interfaz funcional, audio audible o licencia
de distribución. Sin cambios en aplicación, QML, modelos, migraciones o Rust.
No se publica release ni se fusiona el PR.
