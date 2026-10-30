# F01 — Plano de control y aprovisionamiento aislado

**Estado:** spec/plan/tasks ratificados por Diego en PR #8 el 2026-10-30; T001 en curso, aceptación técnica de F01 pendiente.
[Registro de aprobación](https://github.com/dlalvarez/rag-platform/pull/8#issuecomment-6528543252).
**Dependencia:** F00 aprobada y cerrada en Issue #4 (PR #6 integrado en develop).
**Meta:** Prueba técnica de aislamiento antes de datos de negocio.

Referencias: [plan](plan.md), [tareas](tasks.md), [ratificación](ratification.md), [checklist](checklist.md) y [evidencia](evidence.md). Requisitos y AC originales conservados.

## Problema y resultado esperado

Esta fase transforma el estado previo en: Prueba técnica de aislamiento antes de datos de negocio. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F01-R01** Migraciones separadas crean `rag_control` y contrato mínimo de catálogo, destinos y estados.
- **F01-R02** Servicio/CLI administrativo idempotente provisiona BD tenant A/B, extensiones, roles mínimos y migraciones tenant.
- **F01-R03** Catálogo resuelve destinos distintos y referencias opacas a credenciales; secretos fuera de BD/repositorio.
- **F01-R04** Crear almacenes privados de objetos por tenant, credenciales/políticas segregadas y verify probes.
- **F01-R05** Provisioning es saga con estados, reintentos, fallos controlados y compensación sin destruir recursos ajenos.
- **F01-R06** Pools limitados por tenant e interfaz para varias instancias PostgreSQL.
- **F01-R07** Migración por tenant con esquema versionado, locks y detección de error.

## Criterios de aceptación observables

- **AC-F01-01** — Tenants A y B poseen dos bases PostgreSQL distintas y control DB separada.
- **AC-F01-02** — Credencial A no puede CONNECT/SELECT sobre BD B y viceversa; ningún rol app es superuser.
- **AC-F01-03** — Credencial objeto A no puede obtener/poner/listar objetos de B y viceversa.
- **AC-F01-04** — Reintentar provisioning produce una sola identidad/BD/bucket por tenant, sin datos duplicados.
- **AC-F01-05** — Fallo inyectado en creación de bucket no marca tenant READY; recuperación demostrada.
- **AC-F01-06** — Resolver cambia tenant/instancia sin reutilizar conexión o credenciales.
- **AC-F01-07** — Migrar y reintentar la migración de un tenant conserva su versión, aplica locks e informa fallos sin modificar la base de otro tenant (trazabilidad de F01-R07).

## No-objetivos y límites

- No crear documentos, endpoints públicos de alta, auth de usuarios ni chat.
- No declarar PITR independiente por BD si comparte instancia.

## Estrategia mínima de validación

- Test integración tres DB, roles cross-connect, MinIO cross-bucket, timeouts/fallos, migración doble.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
