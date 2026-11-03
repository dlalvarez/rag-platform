# Evidencia F06

## Planificación

Dependencia F05 aceptada en PR74, merge 7f7f180d400d28203d2b20f1947d792661237251.
Cuatro checks HEAD y tres postmerge correctos, revisión propia delegada ADR0007.
El2026-11-03 Diego aprobó aclarar AC-F06-03: solo versiones publicadas completas,
conservando estado de recepción del original. Sin migración por esta aclaración.

Plan y tareas preparados antes de implementar. RRF con k=60/50candidatos por modalidad,
FTS simple y contratos internos registrados. No se ha implementado ni probado
todavía la recuperación híbrida, citas o evaluación F06. No hay métricas F06.
El Recall@3=1.0 del corpus F05 no es evidencia de aceptación F06.

## T002 — contratos y fusión offline

Contratos internos inmutables para filtros, referencias tenant/space/repo/doc/
versión/chunk, extracto y offsets normalizados, con repr privado. RRF versionada
k=60, hasta50 candidatos por modalidad y top_k1..50. Rechaza duplicados dentro
de modalidad, evidencia contradictoria del mismo chunk, mezcla tenant/space
y puntuaciones no consistentes con rangos. Un chunk compartido aporta una vez
por modalidad; desempate por UUID y sin modificación de entradas.

61 pruebas offline correctas en0.30s: promoción de evidencia compartida,
simetría, límites, desempates, deduplicación segura, provenance/offsets inválidos,
filtros acotados y privacidad. No SQL/inferencia/HTTP/DDL ni métricas semánticas.
Ruff focalizado correcto; validación completa e integración pendientes.

Validación completa T002:1188passed,1warning heredado,87.61s; runnerexit0/93.78s.
Journal d9ffc7edf033475e93fa03ccc7ebc586. HEADbase55bf9e3 con cambios T002
sin commit durante la corrida; no se modificó código durante la batería.
Ruff completo/formato275archivos/docs/diff correctos. Revisión propia: referencias
incluyen tenant/space, mismochunk exige procedencia/texto idénticos, un aporte
por modalidad y score consistente con rangos. Sin revisión independiente.
