# Checklist F03

- [x] F02 aceptada en PR #26 y continuidad del roadmap autorizada (ADR-0010).
- [x] T001 integrada; requisitos y roadmap originales conservados.
- [x] T002..T006 integradas/promovidas con permisos mínimos y datos previos conservados.
- [x] AC-01..04 y V01..V07 acreditados en cuatro fixtures/ambas topologías.
- [x] Regresiones F00/F01/F02 y esquema F03 con documentos presentes correctas.
- [x] 562 tests offline, lint/formato/docs/diff y logs/temporales correctos.
- [x] CI/revisión/merge/postmerge del PR de cierre T007 (#34).

| Validación | Requisitos | Criterios | Resultado |
|---|---|---|---|
| V01 ACL | R01/R02/R05 | AC-01 | HTTP/observadores reales; rol global no concede contenido |
| V02 tenant/objetos | R01/R02/R05 | AC-02 | SQL/SET ROLE/S3 cruzados denegados; A→B→A correcto |
| V03 archivo | R03/R04 | AC-03 | MIME/tamaño/hash/ZIP; inválidos sin filas/objetos |
| V04 idempotencia | R03/R04 | AC-04 | HTTP concurrente, caídas, fencing y reintento estable |
| V05 original | R05 | AC-01/02 | Proxy privado, bytes/hash/cabeceras, reader y negativas |
| V06 secretos/auditoría | R01..05 | AC-01..04 | API sin infra, no fallback, auditoría, logs/temporales |
| V07 reproducibilidad | R01..05 | AC-01..04 | Esquema real/repetido, regresiones y controles offline |

[Detalle de aceptación y límites](acceptance.md), [resultados reales](evidence.md).
Un fallo esencial bloquea cierre; los mocks o documentos solos no acreditan integración.
T002/T006 tienen CI/revisión/postmerge en PR #33; T007 conserva su puerta final.

Cierre efectivo acreditado en [postmerge PR #34](https://github.com/dlalvarez/rag-platform/pull/34#issuecomment-6565126139).
