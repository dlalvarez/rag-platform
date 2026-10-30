# RAG Platform — Arquitectura fundacional y especificaciones SDD

**Estado:** documentación de arranque / propuesta rectora, versión 0.1, 2026-10-28.  
**Nombre de trabajo:** `rag-platform` (marca comercial por definir).  
**Método:** Spec-Driven Development (SDD) con GitHub, Codex, revisiones y pruebas por PR.  
**Importante:** este paquete contiene especificaciones y plantillas; **no contiene un producto funcional ni despliegues de producción**.

## Visión

Plataforma SaaS para crear repositorios de conocimiento y asistentes conversacionales fundamentados en documentos, con espacios personales y empresariales, usuarios en varias organizaciones y controles de acceso. El MVP se validará primero con conocimiento técnico personal, sin relajar los límites multi-tenant.

## Decisiones obligatorias

1. **Una base de datos PostgreSQL independiente por tenant**; además una BD `rag_control` para catálogo e identidad. Nunca tablas de conocimiento compartidas entre tenants.
2. Un tenant puede ubicarse en una instancia PostgreSQL compartida o dedicada; resolución de conexión por tenant desde un catálogo controlado.
3. Credenciales de base de datos y permisos de almacenamiento separados por tenant; secretos fuera del código y de la BD central.
4. Repositorios, documentos, chunks, embeddings, asistentes, conversaciones y ACL de repositorio en la BD del tenant.
5. La autorización se verifica **antes** de consultar repositorios, ejecutar recuperación o construir contexto para LLM.
6. Desarrollo incremental por fases, especificaciones versionadas y **ninguna modificación silenciosa de principios rectores**.
7. Sin respuestas inventadas: citas verificables, abstención ante evidencia insuficiente y evaluación repetible.

## Orden recomendado de lectura

- [`AGENTS.md`](AGENTS.md): reglas ejecutables para Codex.
- [`docs/00-vision.md`](docs/00-vision.md): producto y objetivos.
- [`docs/01-constitution.md`](docs/01-constitution.md): constitución de autoridad máxima.
- [`docs/02-architecture.md`](docs/02-architecture.md): componentes y flujos.
- [`docs/03-tenancy-security.md`](docs/03-tenancy-security.md): aislamiento y control de acceso.
- [`docs/04-data-model.md`](docs/04-data-model.md): entidades y límites transaccionales.
- [`docs/05-ingestion.md`](docs/05-ingestion.md): ciclo de vida documental.
- [`docs/06-retrieval.md`](docs/06-retrieval.md): motor RAG, citas y evaluación.
- [`docs/07-api-contracts.md`](docs/07-api-contracts.md): API y eventos.
- [`docs/08-operations.md`](docs/08-operations.md): aprovisionamiento, backups y operación.
- [`docs/09-nfr-quality.md`](docs/09-nfr-quality.md): no funcionales y pruebas.
- [`docs/10-roadmap.md`](docs/10-roadmap.md): entregas y dependencias.
- [`docs/11-sdd-codex.md`](docs/11-sdd-codex.md): trabajo con Codex CLI/Cloud.
- [`docs/12-threat-model.md`](docs/12-threat-model.md): amenazas y mitigaciones.
- [`docs/13-decisions-risks.md`](docs/13-decisions-risks.md): decisiones pendientes y riesgos.
- [`specs/`](specs): especificación trazable por fase.
- [`docs/adr/`](docs/adr): registros de decisiones.

## Primer paso de implementación

Realizar **F00**, que genera el repositorio ejecutable y el entorno de pruebas *sin construir todavía funcionalidades de negocio*. Después, aprobar **F01**, que demuestra separación real entre al menos dos bases de datos de tenants y la BD central. No iniciar ingestión ni chat antes de superar esa barrera.

## Gobierno de cambios

La jerarquía de referencia es: `docs/01-constitution.md` > ADRs aprobados > arquitectura y contratos > spec de fase aprobada > plan > tareas > código. En caso de conflicto, **detener cambios de arquitectura** y elevar propuesta por ADR para aprobación humana.

## F00 técnica en revisión

Implementación y pruebas exclusivamente en ragdev01. [Runbook F00](ops/F00_RUNBOOK.md), [plan y trazabilidad](specs/F00-fundacion-repositorio/plan.md), [evidencias](specs/F00-fundacion-repositorio/evidence.md). Solo paquete Python, API placeholder /healthz, PostgreSQL/pgvector y MinIO sintéticos; no tenants ni RAG. PR hacia develop, revisión humana antes de merge.
