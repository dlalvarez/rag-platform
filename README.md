# RAG Platform — Arquitectura fundacional y especificaciones SDD

**Estado:** F00–F03 implementadas y probadas en ragdev01 (2026-11-01).
F03 aceptada con CI/revisión/merge/postmerge en PR #34. La API documental está en develop.
**Nombre de trabajo:** rag-platform (marca comercial por definir).
**Método:** Spec-Driven Development con fases, pruebas y PR.
El repositorio contiene especificaciones, código y pruebas de aprovisionamiento, identidad y documentos privados.
Todavía no es un producto RAG completo ni un despliegue de producción.

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

## Secuencia de implementación

F00 estableció el repositorio y entorno; F01 probó aislamiento de bases/objetos y el
provisionador; F02 añadió OIDC, membresías, roles, contexto autorizado y API de identidad.
F03 añadió repositorios/ACL, recepción privada idempotente y proxy de originales.
F04 inicia planificación dentro del [roadmap original](docs/10-roadmap.md),
con planificación y decisiones técnicas pendientes según el registro original.

## Gobierno de cambios

La jerarquía de referencia es: `docs/01-constitution.md` > ADRs aprobados > arquitectura y contratos > spec de fase aprobada > plan > tareas > código. En caso de conflicto, **detener cambios de arquitectura** y elevar propuesta por ADR para aprobación humana.

## Estado de fases

- F00 aceptada en PR #6/Issue #4: tooling, CI, entorno base y smoke API/SQL/vector/S3.
- F01 aceptada en PR #15: catálogo/provisionador, secretos y SQL/S3 aislados, dos
  topologías, reintentos, pools, migraciones y CLI. [Evidencia F01](specs/F01-aislamiento-provisionamiento/evidence.md).
- F02 aceptada en PR #26, tras implementación y validación en PR #20..#25:
  OIDC configurable, UUID internos/membresías, administración CLI auditada, contexto
  por solicitud y GET /api/v1/me, /api/v1/tenants. 297 pruebas offline y baterías reales
  en ambas topologías. [Aceptación/límites F02](specs/F02-identidad-membresias/acceptance.md)
  y [manual](ops/f02/README.md).
- F03 aceptada en PR #34, implementada en PR #27..#33: API repositorios/ACL,
  originales privados, validación y diario de recepción, idempotencia y proxy.
  562 tests offline, cuatro fixtures/ambas topologías y regresiones reales.
  [Aceptación/límites F03](specs/F03-repositorios-documentos/acceptance.md) y
  [manual HTTP/handoff](specs/F03-repositorios-documentos/api.md).
- F04 en ejecución parcial (cola/extracción): [plan y tareas](specs/F04-ingesta-versionada/plan.md), con
  aceptación E2E aún pendiente. F05..F11 conservan alcance/dependencias, no implementadas.

Toda ejecución se realiza en ragdev01. PR a develop con revisión delegada según
ADR-0007, checks obligatorios y postmerge; no promoción a main/tag por iniciativa
del agente. [Siguiente tarea](ops/NEXT_CODEX_TASK.md). No producción, HA o restore acreditados.
