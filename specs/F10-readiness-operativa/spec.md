# F10 — Preparación operativa para beta SaaS

**Estado:** BORRADOR RECTOR, pendiente de aprobación humana para ejecutar.  
**Dependencia:** F09.  
**Meta:** Candidato a beta privada con operación comprobable.

## Problema y resultado esperado

Esta fase transforma el estado previo en: Candidato a beta privada con operación comprobable. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F10-R01** Cuotas por tenant (storage, docs, jobs, tokens) aplicadas y medidas.
- **F10-R02** Flujos de migración por lotes y tenant a instancia distinta ensayados.
- **F10-R03** Backup y restore de BD + objetos con reporte de integridad y objetivos RPO/RTO medidos.
- **F10-R04** Métricas, alertas, auditoría, rate limits y runbooks de soporte sin exposición de contenido.
- **F10-R05** Escaneo dependencias, revisión amenazas y pruebas de estrés/load shedding.

## Criterios de aceptación observables

- **AC-F10-01** — Restore tenant A recupera documentos/citas sin afectar tenant B.
- **AC-F10-02** — Migrar tenant A a otra instancia no modifica lógica RAG y pasa tests.
- **AC-F10-03** — Sobrecuota produce rechazo controlado y metering correcto.
- **AC-F10-04** — Fallo de worker o DB notificado y recuperable según runbook.

## No-objetivos y límites

- No SLA contractual sin datos, ni facturación automatizada.

## Estrategia mínima de validación

- Chaos controlado, restore, capacity, auth negative, métricas.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
