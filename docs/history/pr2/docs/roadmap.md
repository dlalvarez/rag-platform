# Roadmap incremental — RAG Platform

**Estado:** propuesta de secuencia; cada fase requiere spec/plan/tasks propios y aprobación.

| Fase | Enfoque | Puerta de salida |
|---|---|---|
| F00 | Constitución, ADR, documentación de infraestructura, proceso SDD | PR documental aprobado |
| F01 | Fundamentos de persistencia multi-tenant PostgreSQL+pgvector | Tests de aislamiento y restauración básica |
| F02 | Control plane: tenants, conexiones, usuarios y permisos | Aprovisionamiento/revocación probados |
| F03 | Repositorios documentales y almacenamiento de originales | ACL y ciclo de vida por tenant |
| F04 | Pipeline de ingesta, extracción, chunking, embeddings | Idempotencia, reintentos y borrados |
| F05 | Recuperación vectorial/híbrida y autorización | Calidad de recuperación y cero fugas |
| F06 | Asistentes RAG y abstracción LLM | Respuestas con citas/evidencia |
| F07 | API y experiencia de administración multiusuario | Autorización funcional |
| F08 | Observabilidad, cuotas y coste por tenant | Métricas operativas verificadas |
| F09 | Evaluación de RAG, seguridad y robustez | Suite reproducible y pruebas negativas |
| F10 | Preparación comercial SaaS y operación | Backup/restore, seguridad y despliegue validados |
| F11 | Escalamiento y distribución de infraestructura | Pruebas multi-instancia y migración tenant |

Los números F02–F11 son una **propuesta de organización**, no una redefinición de acuerdos previos. Ajustes por nuevas decisiones requieren documentación y autorización.
