# ADR 0001 — Aislamiento por base PostgreSQL para cada tenant

- **Estado:** decisión rectora ratificada en F00; documentada mediante PR #2.
- **Fecha:** 2026-10-28.
- **Contexto:** el proyecto debe poder comercializarse; migrar después de tablas compartidas/RLS a aislamiento fuerte sería costoso y riesgoso.

## Decisión
1. Mantener una base de control central (`rag_control`) para el registro, ubicación y ciclo de vida de tenants; sin guardar allí el corpus ni vectores de tenants.
2. Aprovisionar para cada tenant una **base PostgreSQL independiente**, roles y credenciales específicos, índices pgvector internos a esa base.
3. Diseñar un registro de ubicaciones y un resolvedor de conexiones por tenant que soporten **múltiples instancias PostgreSQL**, aunque inicialmente varias bases compartan una misma instancia.
4. Segregar documentos/objetos, claves, permisos y auditoría por tenant.
5. Mantener autorización transversal: independencia de base no reemplaza control de acceso por usuario, repositorio y asistente.

## Consecuencias
- Más complejidad en aprovisionamiento, migraciones por tenant y pooling de conexiones.
- Se reduce la exposición accidental entre tenants, pero compartir host/instancia conserva riesgos de recursos y fallas comunes.
- Cada tenant debe poder restaurarse y migrarse independientemente, con inventario de su ubicación y objetos.

## Alternativas rechazadas para aislamiento primario
Tablas PostgreSQL compartidas con `tenant_id` y RLS; un esquema por tenant en una misma base.

## Verificaciones requeridas
Dos tenants distintos deben tener bases, credenciales e índices separados. El acceso cruzado debe fallar; la migración de un tenant entre instancias no deberá requerir rediseño de consultas ni datos.
