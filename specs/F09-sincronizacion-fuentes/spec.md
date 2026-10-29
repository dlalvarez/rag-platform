# F09 — Sincronización de fuentes externas

**Estado:** BORRADOR RECTOR, pendiente de aprobación humana para ejecutar.  
**Dependencia:** F08.  
**Meta:** Sync incremental fiable y segura.

## Problema y resultado esperado

Esta fase transforma el estado previo en: Sync incremental fiable y segura. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F09-R01** Interfaz SourceConnector con listado paginado, identidad externa, cursor y delta changes.
- **F09-R02** Adaptador inicial Google Drive o almacenamiento acordado por ADR; permisos delegados por tenant.
- **F09-R03** Detectar nuevas versiones y borrados confirmados sin eliminar por fallas temporales de API.
- **F09-R04** Reporte de reconciliación y recuperación tras interrupción.

## Criterios de aceptación observables

- **AC-F09-01** — Documento en subcarpeta se descubre, versiona e indexa correctamente.
- **AC-F09-02** — Documento eliminado en origen pasa tombstone solo tras inventario confirmado.
- **AC-F09-03** — Falla de paginación/autorización no desencadena eliminación masiva.
- **AC-F09-04** — Repetir sync sin cambios no crea embeddings duplicados.

## No-objetivos y límites

- No sincronización entre tenants ni n8n como fuente de verdad.

## Estrategia mínima de validación

- Simulación API paginada/delta, subtree, delete confirmation, rate limits.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
