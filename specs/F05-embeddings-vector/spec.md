# F05 — Embedding spaces, índices y búsqueda vectorial

**Estado:** alcance original autorizado mediante ADR-0010; F04 aceptada en PR #44.
Implementación activa; D-06/ADR0011 Qwen aprobado, primera medición y fundación adoptada.
Los AC completos y aceptación F05 siguen pendientes.
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
- **F05-R06** Exponer la búsqueda HTTP de fragmentos aprobada por Diego el 2026-11-02:
  POST search con repository_ids, space_id, query y top_k; hits con procedencia,
  similitud coseno y uso de embeddings, conforme a docs/07-api-contracts.md.
  Sin asistentes ni generación. Validar ACL antes y después de inferir; no truncar
  consultas que excedan el límite del perfil.

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
