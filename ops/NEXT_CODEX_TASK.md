# Siguiente tarea Codex — activar y acreditar sesión diaria

Diego pidió un día completo de pruebas sin reautorización por batería. ADR-0008,
contrato DAY-01..06 y cliente están preparados en PR #18. No confundir con ACC corto.

Diego custodia unseal y contraseña del operador. Recuperación inicial preparada:
[procedimiento](f01/DAILY_RECOVERY.md), [manual](f01/DAY_ACCESS.md).
Solo Diego ejecuta en su terminal python3 scripts/f01_daily_host.py configure,
tras revisar los dos reinicios de OpenBao y confirmar CONFIGURAR24H.
No pedir claves en chat ni ejecutar ese mantenimiento por herramientas de Codex.

Tras PASS SETUP: verificar con el mismo día dos procesos independientes, daily verify
y daily-cli, status/TTL real y regresión F00. No revocar el día operativo tras la
batería; su sesión de ensayo ya se revoca en setup. Mantener el vencimiento original.
Registrar códigos/salidas saneadas y hashes de fuentes. No fingir transcurso de 24h.
Si falla configuración, pedir solo código y comprobar estado; no repetir root a ciegas.

PR de implementación permanece sin fusionar hasta evidencia real y CI correctos.
Después integrar/verificar según ADR-0007 y dejar el día operativo activo para pruebas.
Toda ejecución/desarrollo en ragdev01; conservar datos, F00, rol corto y clon T007.
F01 sigue cerrada; F02/main/tag no se inician con esta mejora.
