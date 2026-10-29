# F11 — Autogestión comercial, planes y billing

**Estado:** BORRADOR RECTOR, pendiente de aprobación humana para ejecutar.  
**Dependencia:** F10.  
**Meta:** SaaS comercializable bajo validación legal/operativa.

## Problema y resultado esperado

Esta fase transforma el estado previo en: SaaS comercializable bajo validación legal/operativa. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F11-R01** Catálogo de planes y consumos por tenant con políticas de límite/upgrade.
- **F11-R02** Alta/baja autoservicio con confirmaciones y saga de provisioning segura.
- **F11-R03** Integración de pagos mediante proveedor definido por ADR, conciliación e idempotencia de webhooks.
- **F11-R04** Panel de cuentas, facturación y soporte con permisos segregados.
- **F11-R05** Políticas/consentimientos/retención y documentos legales revisados para mercado objetivo.

## Criterios de aceptación observables

- **AC-F11-01** — Alta comercial crea nuevo tenant DB+objeto aislados sin acciones manuales inseguras.
- **AC-F11-02** — Evento de pago duplicado no factura/aprovisiona dos veces.
- **AC-F11-03** — Suspensión/renovación aplica límites sin borrar datos por error.
- **AC-F11-04** — Cliente accede solo a su uso/facturas, soporte sin contenido privado por defecto.

## No-objetivos y límites

- No marketplace ni cross-tenant sharing sin ADR posterior.

## Estrategia mínima de validación

- Webhook replay, pagos simulados, billing metering, cumplimiento local.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
