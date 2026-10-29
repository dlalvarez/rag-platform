# F07 — Asistentes, conversaciones y respuestas fundamentadas

**Estado:** BORRADOR RECTOR, pendiente de aprobación humana para ejecutar.  
**Dependencia:** F06.  
**Meta:** API de conversación especializada con evidencia.

## Problema y resultado esperado

Esta fase transforma el estado previo en: API de conversación especializada con evidencia. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F07-R01** CRUD de asistentes con lista de repositorios, política de respuesta y perfil de proveedor.
- **F07-R02** Pipeline chat que recalcule ACL del usuario al consultar asistente y seleccionar contexto.
- **F07-R03** Modelo LLM intercambiable y mock determinista para CI.
- **F07-R04** Respuestas con citas validadas contra evidence; abstención y contradicción explícitas.
- **F07-R05** Historial por tenant y permisos, límites tokens, timeouts y metering sin fuga de prompts.

## Criterios de aceptación observables

- **AC-F07-01** — Chat contesta pregunta cubierta con citas a versión/chunk auténticos.
- **AC-F07-02** — Pregunta fuera del corpus produce abstención evaluada, sin inventar fuentes.
- **AC-F07-03** — Asistente conectado a repo privado no elude ACL del usuario final.
- **AC-F07-04** — Un usuario de tenant B no recupera mensaje del tenant A aunque conozca thread_id.
- **AC-F07-05** — Documento con prompt injection de prueba no cambia políticas ni produce exfiltración.

## No-objetivos y límites

- No herramientas/agentes capaces de realizar acciones en sistemas externos.
- No facturación ni UI definitiva.

## Estrategia mínima de validación

- Chat E2E offline con mocks, online opt-in, prompt injection, no ACL bypass.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
