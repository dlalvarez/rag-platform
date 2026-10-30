# Ratificación F01 — propuesta del 2026-10-30

**Estado:** pendiente de revisión y aprobación humana. Esta propuesta no inicia F01.
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
| Secret manager dev | OpenBao 2.7.2 por digest, KV v2, Raft un nodo y TLS | Preferido para la propuesta; ratificación pendiente |
| Custodia de desbloqueo | Shamir 1/1 solo dev; clave en gestor de contraseñas independiente de la VM y copia fuera de línea, ambas fuera de ragdev01 | Esquema aprobado por Diego el 2026-10-30; disponibilidad efectiva de ambos destinos pendiente antes de inicializar |
| Identidad del gestor | Operador userpass de infraestructura + AppRole CLI de TTL corto | Propuesto, sin usuarios SaaS/F02 |
| SQL/objetos | PostgreSQL 17/pgvector 0.8.7 y MinIO fijados como F00, nuevas instancias/datos F01 | Propuesto; riesgo MinIO conservado |
| Provisionador | Bootstrap manual del template vector; cuenta CREATEDB/CREATEROLE separada, ningún app superuser | Propuesto; privilegios de clúster reconocidos |
| Pools | 2 conexiones por tenant/engine, 4 engines y 8 conexiones tenant por proceso; control 2; admin serial | Propuesto para probar, sin prometer límite multiproceso |
| Topología de prueba | A/B misma instancia y A2/B2 en dos endpoints reales | Propuesto; sin migrar datos entre instancias |
| Rollback/recuperación | Conservar datos, no borrar recursos ajenos ni ejecutar DROP/borrados automáticos | Propuesto; backup externo/HA/producción no acreditados |
| Ejecución | Solo ragdev01, rama feat/F01-* y PR hacia develop después de aprobación | No iniciada |
| Merge | Revisión y autorización humana por PR | Pendiente |

La aprobación de custodia se limita al esquema descrito: no ratifica por sí sola el
PR ni el resto del diseño F01. Antes de inicializar, Diego confirma que ambos
destinos están preparados y que puede recuperar la copia fuera de línea. La
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
