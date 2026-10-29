# 08 — Aprovisionamiento, migraciones, respaldos y operación

## Aprovisionamiento de tenant (saga idempotente)

1. Registrar tenant `PROVISIONING` en `rag_control` con ID inmutable.
2. Elegir `db_location` por política y capacidad; crear BD dedicada y roles propios mediante credencial administrativa con acceso restringido.
3. Revocar permisos de conexión no deseados, habilitar extensión pgvector, aplicar migraciones `tenant` y validar versión/esquema.
4. Crear bucket privado + política/credencial aislada; guardar referencia a secretos (no valores) y comprobaciones de acceso.
5. Ejecutar *isolation probes* (DB, objeto, funcional); publicar `READY` **solo** cuando todas pasen.
6. En fallo: `FAILED`, diagnóstico saneado, reintento seguro/compensación; jamás marcar ready por completar solo parcialmente.

F01 permite aprovisionamiento vía comando administrativo local/controlado; autoservicio llega después.

## Migraciones

- Dos pistas Alembic distintas: `migrations/control` y `migrations/tenant`.
- Cada tenant conserva versión de schema, registro en control y estado `NEEDS_MIGRATION`, `MIGRATING`, `READY`, `MIGRATION_FAILED`.
- Ejecutar migraciones de tenant en lotes con límites, lock, verificación previa, rollback/restore plan, canary inicial y evidencia; no migrar todas las bases en un solo script sin control.
- Cambios incompatibles usan expand/migrate/contract, versiones API y despliegue coordinado.

## Backups y restauración

- `pg_dump`/respaldo lógico por base tenant + almacenamiento de objetos con versionado/backup correspondiente + secretos/config de recuperación; validar consistencia temporal.
- PITR físico/WAL es **a nivel de clúster/instancia PostgreSQL**, no per-tenant al compartir instancia. Para restaurar un tenant a un punto, restaurar instancia/cluster en entorno temporal y extraer su BD según procedimiento probado, o ofrecer instancia dedicada.
- Eliminar un tenant no implica borrado automático de copias sujeto a retención; definir política y controles legales para producción.
- Pruebas regulares de restauración por tenant con RPO/RTO medidos, no asumidos; antes del beta comercial completar simulacro documentado.

## Observabilidad y operación

- Logs JSON de API/worker con request/job/tenant ID y redacción; métricas latencia, tasa fallos, jobs pendientes, chunks, tokens, bytes, conexiones por instancia y ocupación.
- Catálogo de instancias PostgreSQL con límites y monitoreo de conexiones y capacidad; pool global acotado, sesiones inactivas cerradas.
- Cuotas y rate limits por tenant; circuit breakers a proveedores; reintentos con jitter; trabajos bloqueados recuperables por lease.
- Salud separada por control plane, tenant plane, MinIO/S3, proveedores LLM; no exponer secretos o texto privado en dashboards agregados.

## Ambientes

`dev` Docker Compose con dos tenants de prueba y objetos sintéticos; `test` reproducible CI; `staging` con datos no sensibles; `prod` con IdP, TLS, backup, secreto externo y observabilidad adecuados. No exponer DB ni MinIO públicamente sin controles. Nunca ejecutar borrados destructivos o `--clean` sin respaldo y aprobación explícita.
