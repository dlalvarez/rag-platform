# Ratificación F01 — aprobada el 2026-10-30

**Estado:** aprobada por Diego e integrada en develop mediante PR #8.
[Registro de aprobación](https://github.com/dlalvarez/rag-platform/pull/8#issuecomment-6528543252). Merge f2c74400d2cafb5fce065b6eb0db23243731f8cf.
T001 en curso; aprobación de planificación no equivale a aceptación técnica ni merge de nuevos PR.
Dependencia F00 satisfecha en [PR #6](https://github.com/dlalvarez/rag-platform/pull/6)
e [Issue #4](https://github.com/dlalvarez/rag-platform/issues/4).
Seguimiento: [Issue #7](https://github.com/dlalvarez/rag-platform/issues/7).

## Contenido a aprobar en el PR documental

- [Spec](spec.md) F01-R01..07 y AC-F01-01..07 sin cambios de alcance.
- [Plan](plan.md), [tareas](tasks.md), [checklist](checklist.md) y formato [evidence](evidence.md).
- [ADR-0004](../../docs/adr/0004-secrets-storage.md): secretos en gestor, refs opacas,
  bucket y credenciales propias por tenant; propuesta OpenBao de desarrollo.
- Perfil de pruebas separado de F00, bootstrap SQL de privilegio explícito,
  presupuestos de pools/recursos y rollback conservador.

| Decisión | Propuesta concreta | Estado |
|---|---|---|
| Secret manager dev | OpenBao 2.7.2 por digest, KV v2, Raft un nodo y TLS | Ratificado; arrancado sin inicializar en T001 |
| Custodia de desbloqueo | Shamir 1/1 solo dev; clave en gestor de contraseñas independiente de la VM y copia fuera de línea, ambas fuera de ragdev01 | Esquema y preparación de destinos confirmados por Diego; generación/entrega y copias efectivas pendientes de bootstrap |
| Identidad del gestor | Operador userpass de infraestructura + AppRole CLI de TTL corto | Aprobado, sin usuarios SaaS/F02 |
| SQL/objetos | PostgreSQL 17/pgvector 0.8.7 y MinIO fijados como F00, nuevas instancias/datos F01 | Aprobado; riesgo MinIO conservado |
| Provisionador | Bootstrap manual del template vector; cuenta CREATEDB/CREATEROLE separada, ningún app superuser | Aprobado; privilegios de clúster reconocidos |
| Pools | 2 conexiones por tenant/engine, 4 engines y 8 conexiones tenant por proceso; control 2; admin serial | Aprobado para probar, sin prometer límite multiproceso |
| Topología de prueba | A/B misma instancia y A2/B2 en dos endpoints reales | Aprobado; sin migrar datos entre instancias |
| Rollback/recuperación | Conservar datos, no borrar recursos ajenos ni ejecutar DROP/borrados automáticos | Aprobado; backup externo/HA/producción no acreditados |
| Ejecución | Solo ragdev01, rama feat/F01-* y PR hacia develop después de aprobación | T001 en curso, nueva rama técnica |
| Merge | Revisión y autorización humana por PR | PR #8 autorizado e integrado; futuros PR requieren revisión |

La aprobación inicial de custodia fue seguida por la ratificación completa del PR #8.
Diego confirmó preparados ambos destinos de custodia. La generación y entrega de la
clave y la creación de sus dos copias se efectuarán durante bootstrap en su terminal. La
credencial de operador se establece en terminal y queda protegida fuera del host;
el root inicial se revoca según ADR-0004. No pedir valores por chat ni guardarlos en Git.
La custodia de la clave no acredita backup externo de Raft ni restauración.

## Límites y fuentes

No modificar constitución, contratos externos, tenancy ni roadmap. No OIDC, alta
HTTP, documentos/RAG/chat, producción ni cambio de visibilidad pública. No usar
el cierre de F00 como permiso automático para ejecutar F01.
[Guía de siguiente tarea](../../ops/NEXT_CODEX_TASK.md).

Fuentes técnicas: [PostgreSQL CREATE DATABASE](https://www.postgresql.org/docs/17/sql-createdatabase.html),
[roles](https://www.postgresql.org/docs/17/role-attributes.html),
[extensiones](https://www.postgresql.org/docs/17/extend-extensions.html),
[pgvector control](https://github.com/pgvector/pgvector/blob/v0.8.7/vector.control),
[SQLAlchemy pools](https://docs.sqlalchemy.org/en/20/core/pooling.html).
CREATE DATABASE no es transaccional y no copia ACL de conexión; el template no
sustituye el hardening por base. La instalación de vector se separa del rol app.
Las fuentes del secret store figuran en ADR-0004; lo propuesto aquí no está ensayado.
