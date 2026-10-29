# F06 — Búsqueda híbrida, ranking y evaluación de recuperación

**Estado:** BORRADOR RECTOR, pendiente de aprobación humana para ejecutar.  
**Dependencia:** F05.  
**Meta:** Motor de búsqueda recupera fuentes verificables.

## Problema y resultado esperado

Esta fase transforma el estado previo en: Motor de búsqueda recupera fuentes verificables. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F06-R01** FTS PostgreSQL y búsqueda vectorial combinadas con RRF u otra fusión registrada.
- **F06-R02** Filtros por permisos, repositorios, versión y metadatos antes de construir evidencias.
- **F06-R03** Evaluación offline reproducible con >=30 preguntas de fixtures iniciales, incluyendo negativas/ambigüedad.
- **F06-R04** Fragmentos devueltos con IDs/version/página/offset y `citation_resolver` autorizante.
- **F06-R05** Medir recall@10, latencias y fallos; baseline versionado.

## Criterios de aceptación observables

- **AC-F06-01** — recall@10 >= 0.80 en dataset aprobado; si no, fase bloqueada y se registra análisis.
- **AC-F06-02** — 100% citas de resultados resuelven a chunks existentes, publicados y autorizados.
- **AC-F06-03** — Búsqueda no ve un documento en estado RECEIVED/FAILED/TOMBSTONED.
- **AC-F06-04** — Corpus técnico con palabras exactas (comandos, parámetros) demuestra FTS junto a semántica.

## No-objetivos y límites

- No generación LLM ni conversaciones todavía.

## Estrategia mínima de validación

- RAG eval reproducible, ACL, performance baseline, estados.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
