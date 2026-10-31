# Siguiente tarea Codex — sesión diaria de pruebas

Diego solicitó una autorización reutilizable de al menos 24 horas, sin nueva
intervención por batería. El flujo corto ACC de PR #17 no satisface ese objetivo.
F01 sigue cerrada; el runtime actual no cambia en esta entrega documental.

[ADR-0008 propuesto](../docs/adr/0008-daily-development-session.md).
[Contrato DAY-01..06 y tareas D001..D006](f01/DAY_ACCESS.md).
Propuesta: f01-dev-day, mismos permisos f01-provisioner, token reutilizable de 86400s,
caducidad máxima explícita y revocación por sesión diaria. Sin guardar contraseña.
Conservar f01-cli y su máximo de una hora como flujo corto independiente.

Pendiente D001: disponer de administración inicial. Root inicial revocado;
f01-operator no puede crear roles ni editar políticas. Resolver con Diego si tiene
otra identidad administrativa o si hay que preparar recuperación controlada.
No generar root ni habilitar endpoints/reiniciar OpenBao unilateralmente.
No pedir secretos en chat. La duración solicitada está clara; no preguntar otra vez
si quiere 24 horas ni presentar una batería de un uso como solución equivalente.

Tras resolver D001, implementar y probar el contrato, PR y postmerge conforme a
la delegación ADR-0007. No afirmar que hay sesión diaria mientras no esté activada.
Todo desarrollo permanece en ragdev01. Conservar datos/fixtures/clon T007 y F00.
No iniciar F02 ni promover main/tag por esta tarea. Backup/restore/HA/PITR pendientes.
