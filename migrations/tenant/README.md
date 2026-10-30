# Pista tenant

T002 añade la revisión f01_tenant_0001: identidad operativa mínima y versión Alembic,
sin esquemas de negocio. Vector procede de la plantilla propia preparada por bootstrap;
la migración usa migrator/owner limitados, sin instalar extensiones como superusuario.

Ver [runbook T002](../../ops/f01/T002.md). Locks, canary, fallos/reversión y coordinación
con el catálogo se completan en T006. Crear esta pista no acredita aislamiento real:
la prueba correspondiente es scripts/f01_sql_check.py con credenciales de cada tenant.
