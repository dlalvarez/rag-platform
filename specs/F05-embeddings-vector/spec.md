# F05 — Embedding spaces, índices y búsqueda vectorial

**Estado:** BORRADOR RECTOR, pendiente de aprobación humana para ejecutar.  
**Dependencia:** F04.  
**Meta:** Motor vectorial autorizable con perfiles versionados.

## Problema y resultado esperado

Esta fase transforma el estado previo en: Motor vectorial autorizable con perfiles versionados. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F05-R01** Seleccionar perfil embedding de MVP por ADR (modelo, dimensión, métrica, límites de tokens).
- **F05-R02** Crear embedding_spaces versionados y esquema tipado de almacenamiento/vector index dentro de DB tenant.
- **F05-R03** Worker genera embeddings por lotes con retries/cuotas, valida dimensiones y guarda usage.
- **F05-R04** Búsqueda vectorial parametrizada sobre repositorios autorizados y versiones publicadas.
- **F05-R05** Tests con provider embedding determinista offline y ejemplo online opt-in.

## Criterios de aceptación observables

- **AC-F05-01** — Embedding de dimensión errónea falla sin contaminar índice.
- **AC-F05-02** — Usuario A/tenant A no puede recuperar vector de tenant B o repo sin ACL.
- **AC-F05-03** — Reindexar mismo documento/espacio no crea duplicados.
- **AC-F05-04** — Reindexación a modelo nuevo no sobreescribe vectores incompatibles.

## No-objetivos y límites

- No híbrida/FTS avanzada ni interfaz conversacional.
- No elegir modelos comerciales sin benchmark documentado.

## Estrategia mínima de validación

- Exact/ANN fixture, model mismatch, cross-repo/tenant, failures embedding.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
