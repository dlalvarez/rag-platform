# Siguiente tarea Codex — revisar T003; después T004

T001/T002 aceptadas e integradas mediante PR #9/#10. Base T003:
develop@ff24f439c75e93477df0a99835635d0fb00538d5.
T003 implementada en [PR #11](https://github.com/dlalvarez/rag-platform/pull/11):
calibración MinIO y batería A/B con OpenBao completadas.
[Runbook](f01/T003.md) y [evidence](../specs/F01-aislamiento-provisionamiento/evidence.md).

Puerta actual: comprobar docs/lint/tests del HEAD del PR T003, revisar evidencia
y esperar aprobación explícita de Diego para merge. No auto-merge/bypass.
Después de merge autorizado, sincronizar develop y comprobar postmerge.

Solo después de aceptar T003 y autorizar continuar: T004, saga/journal,
lock por tenant, idempotencia y fallos parciales conforme P4/V05.
No implementar aún resolver/pools, T006, usuarios finales o fases posteriores.

Mantener F00 y datos/credenciales F01. Tenants siguen PROVISIONING hasta que existan
migración coordinada y probes completos de la saga. No borrar buckets/BD, regenerar
secretos ni reinicializar OpenBao. No ejecutar prepare-storage sobre recursos existentes.
Solo desarrollo/pruebas por SSH en ragdev01, nunca en el equipo local.
