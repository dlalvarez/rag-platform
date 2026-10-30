# Plan F01 — ratificado en PR #8

**Estado:** ratificado por Diego el 2026-10-30; T001 en curso. [Aprobación](https://github.com/dlalvarez/rag-platform/pull/8#issuecomment-6528543252).
Las propuestas de diseño de este plan quedaron aprobadas; cada PR técnico requiere revisión posterior.
Dependencia satisfecha: [F00 aceptada, Issue #4](https://github.com/dlalvarez/rag-platform/issues/4),
PR #6 integrado en develop@85cd39f401b48e312c1e4fd61906543a4ff588fe.
Seguimiento: [Issue #7](https://github.com/dlalvarez/rag-platform/issues/7).
Fuentes: [spec](spec.md), [ADR-0001](../../docs/adr/0001-tenancy-db-per-tenant.md),
[ADR-0004 aprobado](../../docs/adr/0004-secrets-storage.md).
OpenBao de desarrollo y ADR-0004 ratificados en PR #8. Diego confirmó preparados
los destinos de custodia el 2026-10-30; el bootstrap se ejecutará exclusivamente
en su terminal. Ver [runbook T001](../../ops/f01/README.md).

## Resultado y límites

Demostrar rag_control y dos bases tenant separadas, roles y objetos privados,
aprovisionamiento idempotente, resolución por ubicación y migraciones controladas.
Solo CLI administrativa en ragdev01; no OIDC, usuarios finales, alta pública,
documentos, chunks, embeddings de negocio, ingesta ni chat. La extensión vector se
habilita como infraestructura, sin adelantar F05. No abrir el endpoint de alta
interno propuesto en docs/07: F01 permite CLI y no obliga a implementar HTTP.

Conservar F00 y sus datos. Proponer un proyecto Compose separado rag-f01-dev bajo
/srv/rag-data/rag-platform/f01, con las imágenes de F00 reutilizadas. Los archivos
Compose/TLS/bootstrap se crearán en la implementación, no en este PR.

## Decisiones propuestas y archivos previstos

**P1 — Catálogo, secretos y migraciones (T001).** SQLAlchemy 2.x síncrono + psycopg 3
y Alembic, sin segundo pool del driver. Mantener Python/uv y las versiones verificadas
de F00; seleccionar versiones exactas compatibles de las nuevas bibliotecas, fijarlas
con hashes y comprobarlas antes de ejecutar cambios. No actualizar dependencias
ajenas a F01 por conveniencia.

Dos pistas Alembic, migrations/control y migrations/tenant. Control mínimo:
tenants, instances/db_locations, storage_locations, provisioning_operations/steps y
audit_control. Identificadores UUID, constraints de unicidad, referencias de secreto,
versión deseada/observada y error_code cerrado. Campos permitidos explícitos; no JSON
libre que permita almacenar contenido o credenciales. No crear users/memberships/jobs
de fases posteriores. Tenant: Alembic version + metadatos operativos mínimos y vector;
tablas de prueba sintéticas solo en fixtures, sin schemas de negocio vacíos.

SecretStore recibe referencias opacas, nunca URLs/rutas suministradas por un cliente.
Implementación propuesta OpenBao según ADR-0004: KV v2 versionado, Raft de un nodo,
TLS, AppRole para la CLI y políticas restringidas. No modo server -dev, root token
de runtime, secretos en rag_control, Git, argumentos de procesos, logs ni fixtures.
Versiones/refs forman parte de los contratos; el valor solo existe en memoria del
adaptador al conectar. Proveedor caído, sellado o permiso denegado: error saneado y
sin fallback a archivos ni credenciales de otro tenant.

**P2 — PostgreSQL y privilegios (T002).** Mantener PostgreSQL 17/pgvector 0.8.7 y el
digest ensayado en F00; no upgrade de clúster ni modificación de F00.
Cada instancia de F01 tiene bootstrap explícito y revisable: base rag_control donde
corresponda, roles de operación y una plantilla propia sin datos, con vector instalado
por un administrador. No modificar template0/template1 ni convertir migraciones
de aplicación en tareas de superusuario.

Provisionador SQL: cuenta dedicada NO SUPERUSER, con CREATEDB/CREATEROLE y acceso
administrativo solo a recursos de F01. Estos privilegios son amplios a nivel de
clúster: no constituyen un sandbox por tenant. Su secreto se separa del runtime y
solo lo usa la CLI autorizada. La separación del proyecto F01 reduce exposición a F00.

Por tenant: owner NOLOGIN; migrator, app y readonly propios, NO SUPERUSER,
NOCREATEDB, NOCREATEROLE, NOREPLICATION y NOBYPASSRLS. Migrator puede asumir solo su
owner para DDL; app/readonly no asumen owner, migrator ni roles de otro tenant.
Owner y membresías del provisionador se conceden de forma explícita y se inspeccionan.

Nombres derivados por servidor de UUID validado (rag_t_<uuidhex> y sufijos de rol),
no de slug o texto SQL del operador. Usar composición de identificadores del driver;
valores parametrizados. CREATE DATABASE fuera de transacción como paso de saga.
Crear con ALLOW_CONNECTIONS=false; revocar CONNECT de PUBLIC, conceder solo los
roles autorizados y habilitar conexión después. Las ACL de BD no se heredan de la
plantilla: reaplicar siempre. Dentro de la BD, revocar CREATE de PUBLIC, fijar
search_path y grants explícitos. El template instala vector para no conceder
superusuario a la aplicación; comprobar extensión/versiones y propiedad real.
Fallo de bootstrap o template incompatible bloquea la operación.

**P3 — Objetos y credenciales (T003).** Un bucket privado rag-t-<uuidhex> por tenant,
principal y secreto propios; permitir solo get/put/delete sobre sus objetos y list
sobre su bucket. No s3:* global, bucket público, privilegios admin ni acceso a otros
buckets. Permisos administrativos MinIO separados, utilizados solo por la CLI.
Mantener la receta MinIO fijada de F00 y su riesgo de mantenimiento documentado.

Propuesta de administración: MinioAdmin incluido en minio==7.2.20 ya fijado en F00.
Se inspeccionaron sus firmas user_add/policy_add/attach_policy, sin llamar al servidor.
Comprobar compatibilidad real con la release upstream antes de crear recursos de prueba;
la presencia de esos métodos no acredita integración ni permite asumirla. Nunca
pasar secretos como argumentos de mc ni imprimir respuestas administrativas.
Los probes usan credenciales tenant y verifican accesos propios y denegaciones
cruzadas; no usar root para simular aislamiento.

**P4 — Saga e idempotencia (T004).** Un único tenant UUID y operación persistida
por clave idempotente. Estados lifecycle PROVISIONING/READY/FAILED/SUSPENDED;
migration_state separado NEEDS_MIGRATION/MIGRATING/READY/MIGRATION_FAILED.
READY exige migración compatible, probes SQL/S3 y referencias válidas, no solo DDL.

Lock por tenant en control, mantenido por conexión dedicada durante la operación;
transacciones cortas para registrar pasos, sin transacción SQL abierta esperando HTTP.
Secuencia persistida: reservar referencias/identidad → escribir secreto con CAS →
roles/BD restringidos → migración → bucket/principal/policy → probes → READY.
Reintentos conservan referencias, recursos y credenciales ya creados; no regenerar
contraseñas ni crear un segundo bucket. Probar caída entre efecto externo y registro
del paso, reintento concurrente y conflicto de recurso preexistente.

Registrar ownership por tenant/operación y comprobarlo antes de reutilizar un recurso.
Un nombre coincidente no demuestra ownership. Conflicto no atribuible: FAILED y
revisión del operador. Compensación conservadora: retirar acceso de credenciales
creadas por la operación y registrar recursos pendientes. No DROP DATABASE, borrado
de bucket con objetos ni limpieza ajena automática, incluso por un reintento fallido.

**P5 — Resolver y pools (T005).** Contexto administrativo interno obtenido por la
frontera de operación SSH/CLI y el acceso al catálogo/secret store. No llamarlo
AuthorizedTenantContext de usuario, no aceptar headers/JWT ficticios ni implementar F02.
Resolver valida tenant existente, READY y schema compatible; devuelve destino del
catálogo y refs, sin password en serialización.

Engine por (tenant_uuid, instance_ref, db_name, rol, secret_version), sin cambiar
de BD/rol mediante SET dentro de un pool compartido. QueuePool: pool_size=2,
max_overflow=0, pool_timeout=5 s y pre_ping; hasta 4 engines en caché, máximo
8 conexiones tenant por proceso. Pool control de 2; administración/migraciones
NullPool y concurrencia 1. Operación normal F01 de un proceso; ensayos concurrentes
presupuestados aparte. No presentar el límite de un proceso como límite global
de múltiples workers. Evicción solo sin préstamos activos; si no hay capacidad,
rechazo acotado. Al cambiar destino/ref, impedir nuevas adquisiciones del engine
anterior y retirarlo al devolver sesiones. Rollback al devolver y cierre por contexto.
Un checked-out activo no se revoca por llamar dispose; probar drenado y timeout.
Rotación operativa completa de credenciales/terminación de sesiones no se promete en F01.

**P6 — Migraciones y aislamiento (T006).** Lock por tenant sobre la misma conexión
usada para Alembic; versión real en la BD, control solo refleja el resultado comprobado.
Un error deja MIGRATION_FAILED y no READY, sin marcar head en falso.
Canary sintético, timeout de lock y reintento; migración ya aplicada es no-op.
Fixtures de fallo y revisión reversible para probar upgrade/rollback antes de incluir
datos relevantes. Backup/restore de producción no queda acreditado por ese ensayo.

Primera batería: A y B en bases distintas de la misma instancia, además de rag_control.
Segunda batería independiente: nuevos UUID de ensayo A2/B2 en dos servicios PostgreSQL
distintos, con almacenes privados por tenant. No es mover datos existentes entre
instancias ni anticipo de migración masiva F10. Cambiar A2 → B2 → A2 verifica
current_database/current_user, ubicación y credenciales; el destino erróneo falla
sin reconectar silenciosamente al anterior. Probar SQL en ambos sentidos, incluyendo
SET ROLE prohibido y ausencia de privilegios globales. SELECT cruzado no puede
ejecutarse cuando CONNECT ya está denegado; registrar el rechazo real, no un mock.

**P7 — CLI, runbook y evidencia (T007).** Comandos administrativos propuestos
create/show/check/retry y migrate; solo por SSH/entorno de operador. No delete público,
export de secretos ni alta HTTP. Runbook de inicialización/desbloqueo del secret store,
backup previo a cambios, diagnóstico sin secretos, rollback y recuperación.
Desarrollo, dependencias y pruebas en ragdev01. PR acotados hacia develop; sin merge
ni despliegue por iniciativa de Codex.

Archivos previstos: src/rag_platform/{control,tenancy,provisioning,providers}/ según
necesidad; migrations/{control,tenant}; tests/unit/f01 y tests/integration/f01;
ops/f01/ para TLS/policies/Compose y scripts administrativos. Mantener F00 sin regresión.
Estos nombres son artefactos previstos, no archivos ya implementados.

## Matriz spec → plan → tareas → pruebas previstas

| Requisito | AC | Plan / tareas | Prueba observable prevista |
|---|---|---|---|
| F01-R01 | AC-F01-01 | P1/P6; T001/T006 | V01: catálogo sin secretos, constraints y tres bases distintas; migraciones separadas |
| F01-R02 | AC-F01-01, AC-F01-02 | P2/P6; T002/T006 | V02: roles/grants reales, A↔B sin CONNECT/SELECT, no superuser/DDL ni SET ROLE cruzado |
| F01-R03 | AC-F01-01, AC-F01-06 | P1/P5; T001/T005/T007 | V03: refs opacas, secret store sellado/denegado, sin valores en catálogo/logs; resolver no filtra ni hace fallback |
| F01-R04 | AC-F01-03 | P3/P6; T003/T006 | V04: get/put/list propios; get/put/list cruzados y anónimo denegados A↔B |
| F01-R05 | AC-F01-04, AC-F01-05 | P4/P6; T004/T006 | V05: reintento y concurrencia sin duplicados; fallo bucket no READY y recuperación; recurso ajeno intacto |
| F01-R06 | AC-F01-06 | P5/P6; T005/T006 | V06: dos endpoints PostgreSQL reales, A2→B2→A2, saturación/evicción/timeout sin mezclar conexiones |
| F01-R07 | AC-F01-07 | P6; T006/T007 | V07: lock/concurrencia, upgrade/reintento, fallo y revisión reversible; versión/objetos del otro tenant intactos |

Los IDs V01–V07 aún no son tests ejecutados. Cada implementación deberá enlazar ruta
real, comando, commit, ambiente, resultado esperado/observado y log saneado en evidence.
SEC-02/03/04/10 de la matriz global aplican aquí; API/ACL de repositorios, LLM, ingesta,
cuotas y restore de tenants con documentos permanecen en sus fases, sin marcarse passed.

## Operación y puertas previas

Aprobar spec/plan/tasks y ADR-0004 antes de código. El esquema de custodia de unseal
fue aprobado por Diego el 2026-10-30: Shamir 1/1, clave en gestor de contraseñas
independiente de la VM y copia fuera de línea, ambas fuera de ragdev01.
Antes de inicializar OpenBao, confirmar que ambos destinos están preparados y que
Diego puede recuperar la copia; asegurar también la entrega del material de bootstrap.
No guardar esos valores en chat. Custodia no equivale a backup/restore de Raft.
Propuesta de recursos F01: runtime hasta 5 GiB en conjunto, pruebas seriales salvo
concurrencia deliberada; verificar al menos 7 GiB disponibles y 20 GiB de disco antes
de arrancar. F00 se conserva activo; medir CPU real en 2 vCPU. Los límites de contenedor
no son reserva ni garantía de rendimiento. Si no cabe, informar y acordar ajuste;
no ampliar VM ni detener F00 unilateralmente.

TLS con CA de desarrollo verificada para SQL/S3/secret store en el perfil F01; claves
de bootstrap en archivos protegidos fuera de Git, certificados públicos separados.
Sin puertos de datos/secret store expuestos a LAN/Internet. Ningún cambio de visibilidad.

Antes de alterar datos relevantes, disponer de backup y aprobación; aquí solo fixtures
sintéticas. Recursos con datos se conservan ante fallo; rollback de código por PR.
No afirmar backup externo, HA, PITR por tenant, SLA o recuperación de pérdida total.
La elección de secret manager de producción/HA y su custodia requiere decisión posterior;
el contrato evita depender del host/proveedor dentro de la lógica de tenancy.
