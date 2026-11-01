# F04 — Pipeline asíncrono de ingesta y versionado

**Estado:** alcance original autorizado por Diego mediante ADR-0010; F03 aceptada
en PR #34. Planificación T001 activa, sin implementación acreditada.
**Dependencia:** F03.
**Meta:** Documentos convertidos a chunks versionados y auditables.

## Problema y resultado esperado

Esta fase transforma el estado previo en: Documentos convertidos a chunks versionados y auditables. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F04-R01** Implementar cola durable mínima y worker con lease, reintento/backoff y parada segura.
- **F04-R02** Extractores PDF texto/DOCX/MD/TXT, reportar NEEDS_OCR para escaneados.
- **F04-R03** Chunking preservando páginas/secciones/títulos y evitando carga completa en memoria cuando sea viable.
- **F04-R04** DocumentVersions/Chunks y transiciones de estado idempotentes.
- **F04-R05** Publicación transaccional de versión procesada y tombstone que impide publicación tardía.
- **F04-R06** Guardar parsers/chunker versions, hash, offsets, errores saneados.

## Criterios de aceptación observables

- **AC-F04-01** — Ejecutar dos veces mismo job no duplica versiones/chunks.
- **AC-F04-02** — PDF escaneado queda NEEDS_OCR con explicación, no datos fabricados.
- **AC-F04-03** — Falla a mitad de parseo no hace visible versión incompleta.
- **AC-F04-04** — Borrar documento durante un job impide publicación posterior.
- **AC-F04-05** — Chunks conservan relación a versión y página/offset verificable en fixture.

## No-objetivos y límites

- No llamar servicio embedding real; estado READY_FOR_EMBEDDING intermedio permitido.
- No conectores externos ni OCR pesado.

## Estrategia mínima de validación

- Fixtures 4 tipos, archivos grandes, worker crash, idempotencia, deleted while ingesting.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
