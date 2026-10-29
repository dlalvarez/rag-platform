# Plan F01 — propuesta para revisión

1. Dos pistas Alembic (`control`, `tenant`) y catálogo con tenant/instancia/referencia secreto/estado.
2. Provisioner service de mínimo privilegio (credencial administrativa restringida) con saga idempotente y roles de tenant no-superuser.
3. Crear por tenant DB separada y esquema base + pgvector. Endpoint de instancia resuelto de catálogo, sin credenciales embebidas.
4. Objeto privado por tenant (bucket local MinIO), políticas y referencias de credenciales separadas.
5. Tenant session factory con piscinas acotadas; CLI admin para create/show/check/retry. No exponer alta de tenant a Internet todavía.
6. Tests cruzados de credenciales SQL, lectura objetos, cambio contexto, reintento y fallo inyectado. Documentar que PITR físico es por clúster.

**Decisiones a cerrar antes de tareas:** versión PostgreSQL/pgvector; secret store dev/prod; biblioteca de conexiones; máximos de pools; bucket/policy; privilegios mínimos del provisioner.

**Aceptación:** AC-F01-01 a 07. **Rollback:** provisioning compensado e inspeccionable, no `DROP DATABASE` sin identificar que el recurso fue creado por esa operación y sin aprobación admin.
