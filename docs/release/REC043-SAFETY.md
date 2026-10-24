# REC-04.1.4 — Contrato D7 y deuda de infraestructura

## D7: auditoría de guardado de sesiones

`ListeningPeriods.save_as_playlist(first_id, last_id, title, cutoff=None)` es
un comando **no idempotente**. Cada invocación intencional crea otra identidad
`local-list:`. Conserva el orden y las ocurrencias duplicadas de la sesión.
Su secuencia actual es `tracks` → `ensure_songs` → `create_playlist` → `append`;
`append` es atómico, pero crear y añadir son transacciones separadas. La
compensación de fallo de append sigue siendo el borrado best-effort de la
lista vacía recién creada. REC043/REC044 no cambian ninguna de esas operaciones.

Búsqueda de consumidores en `src` y `tests`: el único punto de ejecución en
producto es la definición del servicio; los demás usos son las pruebas
REC-03C de no idempotencia, vacío y fallos. No existe todavía botón, señal,
ViewModel ni controlador activo que guarde una sesión. Por tanto, no se añade
un lock al servicio ni un componente anticipado sin consumidor.

La protección debe entrar en el **boundary del futuro comando de UI** en
REC-04.2, antes de programar la coroutine, compartido por botón/teclado/menú.
No basta con deshabilitar visualmente un botón una vez que ya hay dos tareas
programadas. Contrato propuesto, todavía no implementado:

1. Capturar de manera sincrónica `(first_id, last_id, cutoff, title)` y registrar
   una sola operación en vuelo para esa activación. Un segundo evento mientras
   está ocupada no programa otro `save_as_playlist()`.
2. Mantener la tarea y su resultado en el controlador propietario del comando;
   cambiar de vista no libera el guard mientras la escritura siga en vuelo.
   La navegación no debe cancelar ciegamente una escritura cuyo commit podría
   haberse completado. La política de cancelación/resultado incierto se decide
   al conectar ese consumidor, sin reintentos automáticos que creen otra lista.
3. Reflejar busy/error/resultado desde esa misma operación. Liberar el guard
   únicamente al terminar, restaurar controles en éxito o fallo y permitir
   otro guardado intencional posterior, que creará una identidad nueva.
4. No cambiar la idempotencia, transacciones ni formato del servicio. Un error
   con resultado de commit desconocido requiere reconciliar el resultado, no
   repetir el comando a ciegas.

Pruebas requeridas al conectar REC-04.2:

- Dos eventos en el mismo turno, o botón + teclado: una llamada y una lista.
- Un segundo evento mientras `tracks`, `create` o `append` esperan: no se
  agenda otra operación; controles busy coherentes.
- Navegación de ida/vuelta y cierre del consumidor durante el await: no se
  abre una ventana para duplicar la escritura pendiente ni se publica un
  resultado en una vista obsoleta.
- Éxito, fallo anterior a crear, fallo de append y cancelación/commit incierto:
  liberación correcta, sin reintento automático y errores recuperables.
- Un segundo guardado intencional después del primero: otra identidad, mismos
  miembros y duplicados preservados. Mantener los tests REC-03C existentes.

Estado D7: **auditado y especificado; guard de UI diferido**, porque no hay un
consumidor real donde aplicarlo. No se declara corregido por un lock decorativo.

## Deuda CI: falso positivo de Docker

Evidencia heredada: los probes Ubuntu 22.04/24.04 montan el AppImage con `:ro`
y ejecutan `chmod` sobre ese archivo. El contenedor aborta con
`Read-only file system`; el pipeline exterior hacia `tee` no propaga ese
estado de fallo y aun así puede imprimir `CLEAN_ENV_2204=PASS`.
Los runs verdes de REC042 no demuestran compatibilidad en esos contenedores.
El problema se conserva separado de D2/D6 en esta unidad; solo se añaden
filtros de paths al workflow, sin modificar silenciosamente sus probes.

Propuesta de corrección en una unidad aislada de infraestructura:

1. Conservar el montaje `:ro`, copiar el AppImage a una ruta temporal escribible
   dentro del contenedor, aplicar `chmod` sobre esa copia y ejecutarla allí.
   Alternativamente, retirar el chmod si el modo ejecutable ya está preservado;
   no resolverlo dando escritura al artefacto del host innecesariamente.
2. Activar `set -o pipefail` en el shell exterior para capturar fallos de
   `docker run` a través de `tee`; conservar `set -e` dentro del contenedor.
   Emitir PASS solo después de una salida cero y de verificar el JSON smoke.
3. Comprobar que `ok` y todos los checks obligatorios son verdaderos, que el
   VLC procede del bundle y que no se instaló VLC del sistema. Mantener la
   distinción entre Ubuntu 22.04 obligatorio y 24.04 informativo.
4. Añadir regresión negativa del harness: forzar fallo antes del smoke y
   comprobar salida no cero y ausencia de PASS; después ejecutar realmente
   ambos contenedores y conservar los logs/JSON completos.

Hasta ese trabajo aislado no se certifica compatibilidad Docker. Los tests
unitarios de packaging y los smokes AppImage/Qt/VLC que sí se ejecuten se
informan con su alcance propio, sin equivaler a verificación visual, audio
real audible ni autorización de publicación. Las licencias siguen pendientes.
