# Checklist F04

- [x] F03 aceptada en PR #34, continuidad autorizada ADR-0010.
- [x] T001 integrada en PR #35 con cuatro checks de head/tres de merge y postmerge.
- [ ] T002: núcleo/carreras reales correctos; faltan activación/grants y parada con T005.
- [ ] T003 evolución aditiva con originales/datos anteriores conservados.
- [ ] T004 componente acreditado en 618 tests/contenedor; pendiente puerta del PR.
- [ ] T005 idempotencia, crash, reconciliación y fencing reales.
- [ ] T006 autorización/API/tombstone/operación verificadas.
- [ ] T007 ambas topologías, regresiones y cierre postmerge.

| Validación | Requisitos | Criterios | Evidencia requerida |
|---|---|---|---|
| V01 cola | R01/R04/R06 | AC-01/03 | dos procesos, lease, timeout, backoff y fencing |
| V02 parsing | R02/R03/R06 | AC-02/05 | cuatro formatos, páginas/offsets, NEEDS_OCR, límites |
| V03 commit | R04/R05 | AC-01/03 | reintento/crash sin duplicado ni parcial visible |
| V04 tombstone | R01/R04/R05 | AC-04 | borrar/revocar durante job bloquea commit tardío |
| V05 aislamiento | R01..06 | AC-01..05 | SQL/S3/control/API/worker A→B→A ambas topologías |
| V06 operación | R01..06 | AC-01..05 | migraciones, logs/temporales, CI/regresiones/postmerge |

Errores esenciales o ampliación de alcance bloquean cierre. READY_FOR_EMBEDDING
no equivale a PUBLISHED. [Evidencia](evidence.md).
