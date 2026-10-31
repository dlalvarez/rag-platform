# Siguiente tarea Codex — conservar el flujo delegado aprobado

F01 cerrada, Issue #7 completed. ADR-0007 permite revisar e integrar PR hacia develop
dentro de specs/tareas autorizadas, con diff revisado, pruebas/checks/evidencias y postmerge.
No pedir confirmación repetida para operaciones rutinarias autorizadas.

La mejora operativa ACC-01..05 está implementada y probada contra OpenBao:
[manual](f01/ACCESS.md), [log](../docs/evidence/f01-access-2026-10-31.txt).
180 tests y batería CLI real delegada correctos; token revocado y grant consumido.
No es acceso permanente. Otra batería requiere emitir otro SecretID desde la terminal
del operador; no pedir contraseña en chat ni reutilizar grants/tokens. No cambiar roles,
TTL o custodia para eliminar esa intervención sin decidir antes el cambio de contrato.

Todo trabajo permanece en ragdev01. Conservar datos, canaries, conflictos y clon fijo
T007 /home/diego/proyectos/rag-platform-t007-clean-b60b912b.
F02 y main/tag todavía no autorizados; no asumir que autonomía amplía el alcance.
Si se autoriza F02, leer su spec/contratos originales y formalizar el plan antes de código.
No reinicializar OpenBao ni borrar bases/buckets ni declarar backup/restore/HA/PITR.
