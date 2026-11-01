# F03 — Repositorios, ACL y recepción documental

**Estado:** alcance original autorizado para ejecución continuada por Diego el
2026-11-01 (ADR-0010), tras aceptación de F02 en PR #26. Planificación activa;
implementación y aceptación técnica aún pendientes.
**Dependencia:** F02.  
**Meta:** Carga de archivos privados y repositorios seguros.

## Problema y resultado esperado

Esta fase transforma el estado previo en: Carga de archivos privados y repositorios seguros. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F03-R01** CRUD de repositorios dentro de DB tenant con nombres y configuraciones validadas.
- **F03-R02** ACL owner/admin/editor/reader y capacidades aplicadas a cada operación.
- **F03-R03** Carga de archivo a objeto privado de tenant con validación MIME/tamaño/hash y metadata.
- **F03-R04** Guardar documento/fuente y estado RECEIVED sin procesar embeddings.
- **F03-R05** Descarga de original mediante autorización y URL firmada limitada o proxy.

## Criterios de aceptación observables

- **AC-F03-01** — Usuario sin permiso de repo no lista, descarga ni carga documentos aunque conozca IDs.
- **AC-F03-02** — Repositorio A no aparece en tenant B; URL de objeto entre tenants falla.
- **AC-F03-03** — Archivo inválido/supera límite se rechaza sin objeto huérfano persistente.
- **AC-F03-04** — Reenvío con misma idempotency key no crea dos documentos.

## No-objetivos y límites

- No parsear PDFs, producir embeddings ni sincronizar Drive.

## Estrategia mínima de validación

- API + DB + MinIO + ACL negativas, validación archivo y cuotas.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
