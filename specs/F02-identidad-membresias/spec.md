# F02 — Identidad, membresías y contexto autorizado

**Estado:** ejecución autorizada por Diego al delegar la continuidad del roadmap y
resolver D-04 con Keycloak solo dev en PR #19; implementación/aceptación pendientes.
**Dependencia:** F01.  
**Meta:** Identidad y selector tenant seguros.

## Problema y resultado esperado

Esta fase transforma el estado previo en: Identidad y selector tenant seguros. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F02-R01** Integrar proveedor OIDC configurable, validar firma, emisor, audiencia y expiración de tokens.
- **F02-R02** Mapear usuario OIDC a UUID interno en control DB, con membresías de tenant personales/empresariales.
- **F02-R03** Resolver `AuthorizedTenantContext` inmutable y rechazar tenants sin membresía/estado válido.
- **F02-R04** Definir roles de plataforma y tenant, con administración de membresías controlada.
- **F02-R05** Auditoría de denegaciones sin exposición de identidad sensible o tokens.

## Criterios de aceptación observables

- **AC-F02-01** — Una identidad puede pertenecer a tenants A/B y tener rol distinto en cada uno.
- **AC-F02-02** — Cambiar `tenant_id` en URL sin autorización produce 403/404 sin consultar BD ajena.
- **AC-F02-03** — Token inválido/expirado o tenant suspendido no habilita operación.
- **AC-F02-04** — Logs nunca incluyen JWT en claro.

## No-objetivos y límites

- No autorización granular de repositorio hasta F03.
- No almacenar contraseñas locales propias como backend de producción.

## Estrategia mínima de validación

- Unit token/role; integración IdP de dev; tests request spoof y contexto.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
