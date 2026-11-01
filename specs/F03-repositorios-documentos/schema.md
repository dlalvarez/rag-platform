# Esquema tenant F03-0002

T003 desarrolla R01/R03/R04 y V03/V04/V07; no acredita por sí sola AC-01..04.
Migración aditiva f01_tenant_0001 → f03_tenant_0002, sin downgrade destructivo.
Los UUID de usuario son referencias lógicas; no hay FK hacia rag_control.

## Tablas y consistencia

- knowledge.repositories: nombre, owner lógico, config, estado ACTIVE/DELETED y tiempos.
  Baja lógica; nombre activo único sin distinguir mayúsculas. Nombres sin controles,
  espacios exteriores ni vacío. Config actual: language auto o etiqueta de idioma
  acotada, sin claves arbitrarias. Chunking/retrieval se concretan en sus fases;
  F03 no les asigna algoritmos/perfiles ni ejecuta ingesta.
- security.repository_acl: PK repositorio/principal, rol owner/admin/editor/reader.
  No sustituye membresía tenant ni concede permisos implícitos al operador.
- knowledge.sources: fuente UPLOAD en su repositorio, actor y timestamp.
- knowledge.documents: fuente/repositorio concordantes, versión actual del mismo
  documento/repositorio, actor y estado RECEIVED. La FK de versión actual es diferida
  para insertar documento y versión en una única transacción.
- knowledge.document_versions: original, MIME soportado, tamaño, SHA-256, clave privada
  derivada solo de repo/versión UUID y RECEIVED. No chunks, texto ni embeddings.
- ops.document_receipts: key actor/repositorio, huella, IDs reservados, estado durable,
  intento/lease y versión confirmada. FK compuesta impide confirmar otro documento/repo.
  COMMITTED exige versión propia y lease cerrado; pendiente exige lease.
- ops.audit_events: UUID actor/repo/target/request, acción y resultado de catálogo cerrado.
  Sin cuerpo documental, claims OIDC, mensajes libres o valores de secretos.

FK compuestas y constraints protegen source/document/version/receipt dentro del tenant.
El techo estructural de bytes es 1 GiB, no una autorización de carga: T005 debe imponer
límites HTTP/cuota más bajos y configurables antes de persistir objetos.
Los metadatos RECEIVED de los probes SQL se revierten; no se deja un documento sin S3.

## Migración, permisos y perfiles

Usa migration_session F01: credencial migrator propia, identidad de base/owner/marker,
advisory xact lock en la misma conexión y NullPool; DDL/grants/versionado transaccional.
El coordinador conserva lock de saga por tenant, publica PROVISIONING/MIGRATING y
observed_version=NULL durante la operación; fallo queda FAILED/MIGRATION_FAILED sin
versión falsa, reintento verifica la versión física antes de READY.

El DDL histórico está congelado en schema_f03_0002.build_metadata(); cada invocación
produce metadata nuevo. Las fases futuras no deben editar esa definición ni mutar
el metadata que se usa para reproducir migraciones pasadas.

F01 apply_initial fija explícitamente f01_tenant_0001, en vez de avanzar al head nuevo.
Los perfiles identity/documents solo admiten sus versiones exactas conocidas. Defaults
F01/F02 conservados; constructor inválido, versión futura o estado no READY se rechazan.
Contexts HMAC separados por perfil. IdentityQueries permite únicamente perfiles
configurados conocidos, sin aceptar cualquier head o tenants con versiones divergentes.

App: USAGE de schemas; SELECT/INSERT/UPDATE de repo/documentos/recibos; SELECT/INSERT
de fuentes/versiones/auditoría; CRUD de ACL. Sin DDL, borrado físico de documentos/repos,
edición de versiones/auditoría ni lectura de identidad/versionado operativo.
Readonly: USAGE/SELECT knowledge/security; sin escritura, DDL u ops.document_receipts.
No default privileges amplios; cada migración concede explícitamente lo necesario.
La API aún debe aplicar membresía y ACL antes de contenido/S3; SQL app no es identidad humana.

## Reproducción en ragdev01

Herramientas confiables de migración, no runtime API:
scripts/f03_application_check.py y scripts/f03_schema_check.py, en aislamiento F02
con las monturas administrativas existentes y la sesión diaria, sin pedir contraseña.

La batería usa únicamente cuatro fixtures F03 de application-scope.json, verifica
topologías same-instance/two-instances, grants/constraints, repetición, fallo DDL,
estado FAILED, recuperación y lock entre procesos spawn con handshake de arranque.
El timeout de lock PostgreSQL sigue en cinco segundos; se mide después de que el hijo
anuncia que va a adquirirlo, sin confundir importación con contención.

Reproduce DDL fresco mediante schema_translate_map en tres schemas temporales propios,
dentro de transacción revertida. No DROP, bases extra ni objetos/documents retenidos.
Comprueba ausencia posterior y versión real intacta. Snapshot del catálogo ajeno al
scope F03 se toma bajo el lock diario y se compara al finalizar.
Sin backup/restore acreditado, contenido real, endpoints nuevos o cierre de F03.
