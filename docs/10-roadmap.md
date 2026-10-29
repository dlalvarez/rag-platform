# 10 — Roadmap incremental con puertas de calidad

## Reglas

Una fase = spec aprobada, plan, tareas, implementación, pruebas, PR, revisión y decisión de merge. Dividir un PR demasiado grande sin alterar la especificación de fase. Nunca avanzar a una fase que dependa de otra no aprobada. La columna de entrega indica resultados verificables, no simplemente archivos creados.

| Fase | Entrega verificable | Dependencia | Puerta obligatoria |
|---|---|---|---|
| **F00** | Estructura repo, tooling SDD, linters/tests CI, entorno base | — | Repositorio reproducible; docs validadas |
| **F01** | `rag_control`, provisionador, 2 BD tenant, secretos/roles/MinIO aislados | F00 | Pruebas cruzadas SQL/objeto; reintentos; migraciones |
| **F02** | OIDC, identidad, membresías y `AuthorizedTenantContext` | F01 | Usuarios múltiples/tenant; acceso denegado por defecto |
| **F03** | API repositorios, ACL, upload y objetos privados | F02 | Repositorio privado y aislamiento API/S3 |
| **F04** | Jobs de ingesta, parsing, chunking, versionado, publicación atómica | F03 | Reintento/duplicados/fallos parciales sin índice incompleto |
| **F05** | Embedding spaces/pgvector y búsqueda vectorial autorizada | F04 | Dimensiones correctas; sin acceso repo ajeno |
| **F06** | Búsqueda híbrida, ranking, citas recuperables y dataset eval | F05 | Gates recall/cita/aislamiento; baseline |
| **F07** | Asistentes, chat, historial, respuesta fundamentada y abstención | F06 | E2E dos tenants, citas válidas, no alucinación inducida |
| **F08** | Consola web mínima y experiencia MVP | F07 | UX E2E de carga a consulta multiusuario |
| **F09** | Sincronización fuentes externas, cambios y borrados seguros | F08 | Error externo no causa borrado masivo; idempotencia |
| **F10** | Preparación beta: cuotas, auditoría, restore, migración masiva, observabilidad | F09 | Ensayo restauración y seguridad; despliegue controlado |
| **F11** | Comercial: planes, metering/billing, autoservicio, soporte | F10 | Flujo de alta/baja/consumo y revisión legal/comercial |

## Hitos

- **H0 Fundamento probado:** F00–F02 — tenant-DB aislado, identidad y aprovisionamiento.
- **H1 Motor RAG utilizable por API:** F03–F07 — repositorios, indexación, búsqueda y conversación.
- **H2 MVP personal/empresarial de prueba:** F08 — experiencia web completa con dos tenants.
- **H3 Beta empresarial:** F09–F10 — sincronización y disciplina operativa.
- **H4 Comercial:** F11 — suscripciones y autoservicio.

## Trabajo deliberadamente posterior

OCR multilingüe avanzado, conectores adicionales, colaboración entre tenants, aprendizaje/agents con herramientas, deduplicación global de documentos, GPU propia, automatizaciones visibles al cliente, separación en microservicios y despliegue multi-región: requieren ADR y justificación basada en necesidades reales.

## Convención por fase

Cada carpeta `specs/Fxx-nombre/` contiene `spec.md` aprobado; al activarse debe disponer de `plan.md`, `tasks.md`, `checklist.md` y `evidence.md`. `evidence.md` se llena solo con resultados reales.
