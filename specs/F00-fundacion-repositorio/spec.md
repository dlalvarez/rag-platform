# F00 — Fundación del repositorio y calidad SDD

**Estado:** propuesta de ratificación F00; pendiente de revisión humana en PR. Esta entrega solo formaliza la planificación; no acredita implementación ni autoriza despliegue.  
**Dependencia:** ninguna.  
**Meta:** Repositorio reproducible y listo para que Codex desarrolle F01.

**Plan y pruebas:** [plan.md](plan.md). **Tareas:** [tasks.md](tasks.md). **Control de aprobación:** [ratification.md](ratification.md). Requisitos y AC originales conservados.

## Problema y resultado esperado

Esta fase transforma el estado previo en: Repositorio reproducible y listo para que Codex desarrolle F01. Debe respetar la Constitución P01–P14 y los ADRs aprobados. **Prohibido anticipar funcionalidades de fases posteriores.**

## Requisitos funcionales y técnicos

- **F00-R01** Estructura de proyecto Python y módulos iniciales sin implementar negocio; README, versionado, herramientas de lint y test, configuración tipada.
- **F00-R02** Docker Compose local preparado para PostgreSQL con pgvector, MinIO y servicio API placeholder verificable (sin datos reales).
- **F00-R03** Toolchain reproducible con versiones fijadas, `.env.example` sin secretos y `.gitignore` apropiado.
- **F00-R04** CI ejecuta validación documental, estilo y tests mínimos; ramas y PR protegidos mediante instrucciones operativas.
- **F00-R05** Documentación SDD y gobierno de PR funcional, sin constituciones paralelas.

## Criterios de aceptación observables

- **AC-F00-01** — Clon limpio instala dependencias y ejecuta pytest/lint sin llaves externas.
- **AC-F00-02** — Compose levanta y prueba salud de PostgreSQL/pgvector y MinIO con datos sintéticos.
- **AC-F00-03** — CI falla ante falta de specs/constitución/documentación crítica; no guarda secretos.
- **AC-F00-04** — `AGENTS.md`, constitución y roadmap son descubiertos desde raíz.

## No-objetivos y límites

- No implementar autenticación definitiva, RAG, alta de tenants ni API funcional de contenidos.
- No utilizar `latest` ni servicios externos en pruebas obligatorias.

## Estrategia mínima de validación

- Pruebas de arranque en máquina limpia; pipelines básicos; revisión de secretos.

## Entregables SDD de la fase

- `spec.md` aprobada (este archivo), `plan.md`, `tasks.md`, `checklist.md`, `evidence.md` con pruebas reales.
- PR(s) que referencien requisitos y criterios de aceptación.
- Migraciones/contratos/manuales actualizados cuando corresponda; tests offline y negativos.
- Describir explícitamente limitaciones y regresiones conocidas; sin declarar implementación exitosa por crear solo scaffolding.

## Puerta de salida

Aprobación humana de evidencia, revisión de seguridad y compatibilidad, pruebas reproducibles exitosas y merge controlado.
