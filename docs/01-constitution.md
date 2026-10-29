# 01 — Constitución del proyecto (NORMATIVA)

**Versión:** 1.0 propuesta para ratificación. **Fecha:** 2026-10-28. **Estado:** rector desde arranque, sujeto solo al proceso formal de ADR.

**P01. Aislamiento fuerte desde el día 1 — NO NEGOCIABLE.** Cada tenant tiene su propia base PostgreSQL y sus propias tablas, vectores e índices. `rag_control` no contiene contenido privado de documentos/conversaciones. Ningún desarrollo presupone tablas compartidas entre tenants.

**P02. Tenancy independiente de infraestructura.** Una base por tenant puede residir en instancia compartida o dedicada. Resolver endpoint/BD/identidad desde catálogo de control. No codificar host, database o credenciales del tenant en la lógica funcional.

**P03. Identidad y autorización explícitas.** Identidad global, membresías verificadas por backend y ACL de repositorio dentro del tenant. Denegar por defecto. Un usuario puede tener varios tenants, pero cada solicitud opera en un solo contexto autorizado.

**P04. Separación de responsabilidades.** Control plane separado del data plane; backend/API desacoplado de workers; LLM, embeddings, extracción, almacenamiento y mensajería detrás de interfaces intercambiables.

**P05. Conocimiento con procedencia.** Conservar originales y metadatos, historial de versiones, fuente, hash, offsets/página y vínculo chunks-documentos. Ninguna cita apunta a fuentes inexistentes, inactivas o no autorizadas.

**P06. Consistencia documental.** Indexación idempotente y versionada, publicación atómica a nivel de versión documental, borrado sincronizado seguro y controles ante ejecuciones repetidas/fallos parciales.

**P07. RAG verificable.** La recuperación precede a la generación; el contexto es solo información del tenant/repositorios autorizados. Citas verificadas, abstención ante falta de evidencia y mitigación de prompt injection en documentos.

**P08. Seguridad por diseño.** Mínimo privilegio; secretos fuera de repo y de registros de control; cifrado en tránsito; validación de archivos y límites; auditabilidad; sin credenciales de base de datos expuestas a usuarios.

**P09. Operabilidad y reversibilidad.** Aprovisionamiento/migración por tenant, backups verificados, restauración ensayada, observabilidad por tenant y procedimientos para falla parcial. Una BD aislada no implica PITR independiente si comparte instancia.

**P10. SDD con evidencia.** Sin implementación sin spec aprobada; plan, tareas, tests y checklist vinculados a requisitos. Cada PR corresponde a alcance acotado y verificable; Codex implementa, el humano aprueba arquitectura y merges.

**P11. Compatibilidad evolutiva sin promesas ingenuas.** No se presume trivial mover datos entre topologías, reindexar modelos, dividir monolitos o migrar infraestructura. Operaciones y datos versionados; ADR obligatorio para cambios estructurales.

**P12. Simplicidad disciplinada.** Arquitectura modular, sin microservicios innecesarios ni herramientas introducidas por moda. n8n es opcional, no fuente de verdad ni runtime RAG obligatorio.

**P13. Evaluación como criterio de calidad.** Probar exactitud de recuperación, fundamentación, aislamiento, latencia y fallos; los hallazgos se miden contra corpus y versiones de modelos identificados.

**P14. No introducir características fuera de roadmap.** Toda propuesta nueva fuera de fase se registra para evaluación; no sustituir tareas pactadas por trabajo interesante no solicitado.

## Gobernanza

- Autoridad: Constitución > ADR aprobado > arquitectura/contratos > spec aprobada > plan > tareas > implementación.
- Cambio constitucional: propuesta escrita con motivación, impacto en datos/seguridad/operación, alternativas y plan de migración + aprobación humana explícita antes del código.
- *Stop conditions*: acceso cruzado, filtración de secretos, alteración no aprobada del tenancy, pérdida de datos, citas falsas, tests esenciales omitidos o ampliación silenciosa del alcance.
- Ninguna fase se considera terminada sin demostrar criterios de aceptación sobre ambiente reproducible.
