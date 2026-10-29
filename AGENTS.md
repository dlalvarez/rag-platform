# Instrucciones obligatorias para Codex — RAG Platform

Antes de tocar código o documentación, leer `docs/01-constitution.md`, `docs/02-architecture.md`, `docs/03-tenancy-security.md`, `docs/10-roadmap.md` y la spec de la fase asignada.

## Reglas de ejecución

- Solo trabajar en la **fase y tareas expresamente autorizadas**; no anticipar fases.
- GitHub es la fuente de verdad; cada entrega en rama y PR, nunca desplegar en producción por iniciativa propia.
- No modificar ADR aprobado, constitución, contratos externos ni estructura de tenancy sin propuesta de cambio y aprobación explícita. `docs/01-constitution.md` es fuente canónica; `.specify/memory/constitution.md`, si existe, es una copia derivada que debe sincronizarse.
- Una BD por tenant. `rag_control` no almacena documentos, chunks, embeddings, prompts privados ni mensajes de conversación.
- No hacer joins entre bases de datos de distintos tenants ni agregarlos en consultas SQL compartidas.
- Nunca usar `tenant_id` enviado por un cliente sin autenticar/autorizar en el contexto servidor.
- Los servicios de datos usan conexión por tenant, credenciales propias y pools con límites; ningún usuario final recibe credenciales SQL.
- Probar *negative paths*: accesos cruzados, URLs de objetos, idempotencia, fallos parciales, límites, recuperación de errores y abstenciones RAG.
- Tests offline reproducibles, sin requerir servicios pagados ni API keys reales. Pruebas de integración online marcadas aparte.
- No incluir secretos, documentos reales sensibles ni credenciales en repositorio, logs, fixtures ni respuestas de LLM.
- Preferir diseño legible, tipado, modular y migraciones Alembic separadas para `control` y `tenant`.
- Toda funcionalidad debe tener evidencia de aceptación y manual mínimo; no afirmar que está completa sin pruebas.

## Al comenzar cada tarea

1. Resumir alcance, supuestos y archivos previstos.
2. Identificar los criterios de aceptación afectados (`AC-*`).
3. Detectar conflictos con la constitución/ADRs; si existen, no resolverlos unilateralmente.
4. Proponer cambios mínimos y pruebas necesarias.

## Al cerrar cada tarea

Entregar: resumen de cambios, archivos, migraciones, pruebas ejecutadas con resultados, pruebas no ejecutadas y motivo, riesgos remanentes, cambios de API/configuración, evidencia de no regresión y referencia a requisitos/AC. No marcar *done* si el flujo real falla.

## Alcance tecnológico

Python, FastAPI, PostgreSQL/pgvector, MinIO/S3, workers Python y frontend web; proveedor LLM sustituible. n8n es adaptador opcional y no parte obligatoria del core. Evitar microservicios prematuros, integración directa de secretos en configuración, SQL dinámico de identificadores no validado y dependencias no justificadas.
