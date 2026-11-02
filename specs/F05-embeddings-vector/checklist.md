# Checklist F05

- [x] F04 aceptada PR44/postmerge; continuidad original ADR0010.
- [x] Plan/tareas y propuesta concreta ADR0011 preparados antes de implementación.
- [x] D-06 decidido expresamente por Diego: E5-small local dev, ADR0011.
- [ ] Benchmark ES/EN/capacidad y fuentes/pins/pesos/licencia verificados.
- [ ] T002 provider/fake offline y rechazo mismatch/NaN/Inf/longitud correctos.
- [ ] T003 migraciones/espacios/roles/TLS/rollback/recovery en ambas topologías.
- [ ] T004/T005 batch/retry/crash/publicación/reindexación/bajas reales.
- [ ] T006 búsqueda exacta/ANN y aislamiento repo/tenant/version/space correctos.
- [ ] T007 ejemplo real/operación/manual/errores saneados.
- [ ] T008 cuatro AC, regresiones F00..F04, CI/revisión/postmerge y aceptación.

| Gate | Requisitos | AC | Evidencia |
|---|---|---|---|
| perfil/validación | R01/R03/R05 | AC01/04 | ADR, dimensión/NaN/model mismatch y benchmark |
| aislamiento | R02/R04 | AC02 | repo/tenant/version/space y A→B→A ambas topologías |
| consistencia | R02/R03 | AC01/03/04 | fallo parcial/crash/reindexación y publicación por space |
| operación | R01..05 | AC01..04 | límites/uso/logs/temporales/regresión/CI/postmerge |

No equivaler fake a calidad semántica, ni índice parcial a PUBLISHED.
