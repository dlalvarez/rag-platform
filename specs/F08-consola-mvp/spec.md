# F08 — Consola administrativa web y MVP integral

**Estado:** BORRADOR RECTOR, pendiente de aprobación humana para ejecutar.  
**Dependencia:** F07.  
**Meta:** MVP personal y empresarial de prueba utilizable.

## Problema y resultado esperado

Esta fase transforma el estado previo en: MVP personal y empresarial de prueba utilizable. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F08-R01** UI para autenticación, selección tenant, repositorios, upload, estados de ingesta y asistentes.
- **F08-R02** UI chat que muestre enlaces a citas y fuente, estados de insuficiencia y error.
- **F08-R03** Experiencia de usuario con roles visibles; no mostrar acciones no autorizadas sin confiar solo en UI.
- **F08-R04** Documentación de despliegue local, manual de uso y demo de corpus técnico.

## Criterios de aceptación observables

- **AC-F08-01** — Usuario crea repo, carga documento, espera estado published y recibe respuesta con citas en UI.
- **AC-F08-02** — Misma persona alterna espacio personal/empresa sin visualizar recursos del otro.
- **AC-F08-03** — Usuario reader no puede cargar/editar desde UI ni llamando directamente a API.
- **AC-F08-04** — Error de proveedor aparece con mensaje controlado y trazabilidad, no stack trace/secreto.

## No-objetivos y límites

- No marketplace, pagos, automatizaciones n8n, panel comercial ni soporte completo móvil.

## Estrategia mínima de validación

- E2E UI/API, accesibilidad básica, tenant switch, error handling.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
