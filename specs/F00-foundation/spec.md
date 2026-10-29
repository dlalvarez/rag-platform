# F00 — Fundación documental y especificación de infraestructura

**Estado:** aprobada por el responsable; formalización mediante PR #2. **Issue:** #1. **Tipo:** documental (no despliegue).

## Objetivo
Establecer una jerarquía de decisiones técnicas y un proceso SDD para desarrollar RAG Platform sobre infraestructura ya preparada, sin cambios funcionales ni contenedores de aplicación.

## Alcance
Constitución, instrucciones Codex, arquitectura conceptual, ADR de aislamiento y desarrollo, inventario verificable de VM, riesgos, estrategia de backups pendiente, roadmap incremental y borrador F01.

## Fuera de alcance
Despliegue PostgreSQL/pgvector, credenciales reales, automatización de aprovisionamiento, autenticación final, UI, ingesta RAG, modificaciones en Synology o en `ragdev01`.

## Requisitos
- R01: registrar database-per-tenant y control plane con conectividad multi-instancia.
- R02: separar decisiones rectoras de tecnologías pendientes.
- R03: describir entorno real y evidencias, sin afirmar producción ni backups verificados.
- R04: documentar secretos fuera del repositorio y prohibir datos reales en entorno de desarrollo.
- R05: exigir backup externo, restauración de tenant y control central, y ensayos.
- R06: mantener trazabilidad issue → ADR/spec → plan → tasks → PR.
- R07: explicitar límites de CPU y fallo de SSD único.
- R08: declarar como propuestas, no decisiones, los componentes que aún requieren aprobación.

## Aceptación
- [x] Archivos de F00 creados y consistentes.
- [x] Ninguna tecnología pendiente presentada como aprobada.
- [x] No se incluyen secretos ni direcciones públicas sensibles.
- [x] Ningún servicio funcional desplegado ni commit directo a `main`.
- [x] PR de revisión hacia `main` que referencia Issue #1.
