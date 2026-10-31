# Siguiente tarea Codex — acceso temporal de pruebas en desarrollo

F01 aceptada y cerrada: PR #15 integrado en
develop@585c342fe4a87d0d2b5a071b8114c4cb075ce5be; Issue #7 cerrada.
152 tests, calidad/docs, CI y regresión real F00 postmerge correctos.
[Evidence](../specs/F01-aislamiento-provisionamiento/evidence.md).
Conservar el clon fijo b60b912 y los datos/fixtures/canaries/conflictos existentes.

Diego autorizó revisión e integración delegadas de PR dentro del alcance aprobado.
Ver [ADR-0007](../docs/adr/0007-delegated-development-review.md).
No pedir confirmación de nuevo para cada PR elegible; conservar pruebas y evidencias.

Siguiente mejora autorizada por la solicitud de agilizar pruebas: preparar un flujo
temporal y revocable en ragdev01 con el AppRole F01 ya aprobado. Documentar primero
plan y pruebas: entrega desde terminal de Diego a archivo privado/tmpfs, TTL y consumo
limitados, autenticación no interactiva explícita, sin fallback ni acceso root/unseal,
revocación/limpieza y errores saneados. Revisar diferencias entre sesión de operador
y token AppRole antes de elegir el contrato; no prometer permisos que el token no tiene.
No pedir contraseña en chat ni almacenarla de forma permanente. Esa integración
todavía no está implementada; no afirmar que las herramientas actuales la soportan.

Todo desarrollo/prueba permanece en ragdev01. Sin nueva fase, cambios de permisos,
políticas generales o servicios por iniciativa propia. Si la solución exige cambiar
ADR-0004, proponer el cambio y obtener autorización de esa decisión antes del runtime.
F02 y promoción a main/tag conservan decisión expresa. Backup/restore/HA/PITR pendientes.
