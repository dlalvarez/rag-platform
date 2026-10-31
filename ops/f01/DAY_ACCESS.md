# Sesión diaria reutilizable — contrato y plan

Objetivo autorizado: una intervención del operador habilita 24 horas completas de
pruebas repetidas en ragdev01, sin contraseña en chat y sin una nueva autorización
por batería. [Decisión propuesta](../../docs/adr/0008-daily-development-session.md).

## Criterios de aceptación

- DAY-01: un rol propio f01-dev-day emite token con los mismos permisos de datos
  f01-provisioner/default y TTL inicial/máximo explícito de 86400 segundos.
  No alterar f01-cli ni sus pruebas de expiración.
- DAY-02: iniciar el día requiere una sola autenticación de operador en su terminal.
  Consumir el SecretID inmediatamente y conservar únicamente el token diario en tmpfs
  0600 dentro de directorio 0700. No contraseña, root, unseal, argumentos o logs secretos.
- DAY-03: varias ejecuciones independientes comparten la autorización hasta el vencimiento
  original. Verificar en OpenBao políticas, ruta de origen, TTL y estado al adjuntarla.
  Fallar sin fallback ante expiración, revocación, sellado, formato o permisos incorrectos.
- DAY-04: status expone solo estado/vencimiento, nunca token. revoke revoca en OpenBao,
  verifica HTTP 403 y elimina el archivo. No extender el final por renew ni nueva sesión
  automática. Rechazar cambios de archivo/rol/sesión que no correspondan al contrato.
- DAY-05: ejecutar al menos dos baterías independientes con la misma autorización,
  comprobar aislamiento SQL/S3 y preservación de datos, sin pedir otra contraseña.
  Compatibilidad del flujo corto y regresión F00/CI.
- DAY-06: evidencia identifica commit/hash, TTL real y reloj de vencimiento. No afirmar
  que transcurrieron 24 horas a partir de tests de reloj simulado o de leer un TTL.

## Tareas previstas

D001: resolver la vía administrativa inicial. f01-operator no puede crear roles;
root inicial revocado. Usar otra identidad administrativa autorizada si existe;
en caso contrario, preparar recuperación controlada para decisión de Diego.
No tocar la configuración del servidor ni regenerar root en esta entrega.

D002: preparar el cambio idempotente de rol/política y su comprobación exacta.
Rechazar configuración ajena incompatible en lugar de sobrescribirla.
Verificar límite efectivo del auth mount y lectura posterior de todos los TTL.
Root temporal, si se autoriza usarlo, se revoca y verifica antes de entregar el día.

D003: implementar start-day/status/revoke y adjuntar sesiones desde archivos privados
sin consumir el token en cada ejecución. Adaptar el cliente SecretStore para aceptar
un token validado sin ampliar silenciosamente el límite del login corto existente.
Perfiles mínimos; actor explícito de sesión diaria en auditoría.

D004: probar expiración/revocación/sellado, ficheros inseguros, concurrencia/lock,
errores saneados, incompatibilidad de políticas y no renovación del final del día.
Mantener toda prueba existente. Sin nuevas dependencias si no son necesarias.

D005: Diego activa la primera sesión desde su terminal; Codex prueba dos ejecuciones
independientes y revocación de una sesión de ensayo. Emitir después el día operativo,
sin repetir autenticación durante ese día. Registrar hora de vencimiento comprobada.
Planificar la comprobación posterior del límite real de 24 horas sin fingir resultados.

D006: revisión delegada del PR de implementación, CI y postmerge. No instalar o
reiniciar servicios de datos para esta mejora ni anticipar F02.

## Estado de esta entrega

Implementación preparada y probada offline, pendiente de configuración real por Diego.
El operador confirmó que custodia unseal y contraseña. La vía es una ventana controlada
con dos reinicios solo de OpenBao; [procedimiento](DAILY_RECOVERY.md).
No se ha aplicado la configuración ni se declara activa una sesión diaria.
ACC de PR #17 sigue siendo el único flujo probado contra el servidor.

## Comandos preparados

Configuración inicial, solo desde la terminal SSH del operador y tras revisar la ventana:

    python3 scripts/f01_daily_host.py configure

Exige CONFIGURAR24H y pide unseal/contraseña ocultos. No ejecutarlo desde Codex.
Al finalizar informa configuración restaurada, root/ensayo revocados y vencimiento
del token operativo. Si se detiene, no pegar secretos ni repetir a ciegas: informar
solo el código F01-DAY-SETUP. Un fallo puede dejar el nodo sellado; conserva la clave.

Después, Codex puede ejecutar sin intervención por batería:

    python3 scripts/f01_host.py run --rm -T daily status
    python3 scripts/f01_host.py run --rm -T daily verify
    python3 scripts/f01_host.py run --rm -T daily-cli

Para terminar el día antes de tiempo:

    python3 scripts/f01_host.py run --rm -T daily revoke

Al siguiente día, una sola autenticación de operador, sin ceremonia administrativa:

    python3 scripts/f01_host.py run --rm daily start

No sobrescribir una sesión previa: revoke elimina una sesión confirmada revocada
o expirada. Si el host pierde tmpfs o OpenBao reinicia, el acceso puede necesitar
recuperación operativa; 24 horas de validez no garantizan disponibilidad del servidor.
Nunca ampliar fecha local ni renovar automáticamente el token.

## Comprobaciones preparadas

Cliente valida servidor/origen/políticas/TTL y no amplía el login corto.
Tests de dos clientes independientes, fecha no extensible, ficheros privados,
configuración idempotente, restauración ante fallo, no adopción de ceremonia ajena
y revocación de root incluso si falla la configuración. Evidencia real aún pendiente.
