# Plan F03 — repositorios, ACL y recepción documental

Estado: alcance original autorizado por continuidad expresa de Diego (ADR-0010).
Base develop@81e213c0682ec1766358b29328e52df968c4d8ea, F02 cerrada en PR #26.
Este plan desarrolla F03-R01..05 y AC-01..04 sin cambiar el roadmap ni iniciar F04.

Fuentes: [spec](spec.md), [arquitectura](../../docs/02-architecture.md),
[tenancy](../../docs/03-tenancy-security.md), [datos](../../docs/04-data-model.md),
[API](../../docs/07-api-contracts.md), [amenazas](../../docs/12-threat-model.md).
Ejecución/dependencias/servicios únicamente en ragdev01; CI conserva sus checks.

## Resultado y límites

Repositorios y ACL explícitas dentro de cada base tenant, carga privada validada,
fuente/documento/versión RECEIVED y descarga autorizada por proxy (opción ya prevista
en R05). Sin parsing, chunks, embeddings, jobs de ingesta, Drive, UI o chat.
rag_control sigue sin contenido privado ni claves. No endpoint de onboarding público.
Conservar F00/F01/F02 y sus fixtures; crear fixtures F03 propias para migración/integración.

## T001 — continuidad y trazabilidad

Registrar instrucción persistente en AGENTS/ADR-0010 y guía activa. Ratificar estado de
la spec original mediante esa autorización, plan/tareas/checklist/evidence en PR.
No tratar creación de documentos como funcionalidad terminada.

## T002 — acceso de aplicación y conexión autorizada

Reutilizar contexto OIDC/membresía de F02 y pools limitados F01. El runtime data plane
recibe solo credenciales SQL app/readonly y S3 de tenants habilitados; nunca migrator,
SQL provisioner, MinIO admin, root ni sesión diaria de infraestructura.
Mantener referencias opacas y lectura exacta/versionada en OpenBao, sin escribir secretos
desde la API, sin fallback a archivos de contraseñas de tenant o al token de operación.

Inventariar permisos reales de las identidades existentes antes de elegir bootstrap.
Preparar policy/rol AppRole de lectura limitada a refs de aplicación autorizadas y su
entrega privada/revocable. No inventar permiso administrativo para el token diario.
Si configurar esa policy necesita identidad administrativa no disponible, preparar
procedimiento fijo, revisado/probado y pedir solo esa acción imprescindible del operador.
Seguir mientras tanto con módulos/migraciones/pruebas independientes; sin desplegar
runtime con credenciales más amplias para sortear el bloqueo.

Adaptar compatibilidad de versiones tenant por perfiles explícitos conocidos, sin
aceptar cualquier head ni romper fixtures/helpers F01/F02. F03 requiere su versión
esperada y estado READY antes de pools/S3. Revalidar identidad/membresía por solicitud.

## T003 — esquema tenant y migraciones

Migración Alembic aditiva propia de F03: knowledge.repositories/sources/documents/
document_versions; security.repository_acl; registros locales de recepción/idempotencia
y auditoría sin contenido en logs/control. UUID lógicos de usuario sin FK entre bases.
Nombres/config y estados validados con constraints; referencias de objeto privadas.
Conservar original, MIME, tamaño, SHA-256, fuente y estado RECEIVED; no publicar/indexar.
No cambios destructivos de esquema/datos; baja de repositorio conserva datos/historial.
Probar repetición, rollback DDL, locks/versión real y compatibilidad en fixtures nuevas.

## T004 — repositorios y ACL

CRUD en tenant autorizado, listados paginados sin enumerar repositorios ajenos.
Roles de tenant no sustituyen ACL explícita por repositorio. Operador/support no reciben
contenido implícito. Matriz owner/admin/editor/reader con capacidades por operación,
denegar por defecto y limitar privilegios por membresía tenant activa.
Creator permitido recibe ACL owner del repo explícita/auditada. Owner administra ACL;
admin no puede promoverse a owner ni conceder privilegios superiores; editor carga/lee,
reader solo lee. No administrar membresías de tenant desde ACL de repositorio.
Sin ACL no listar, cargar ni descargar aunque se conozcan IDs. Verificar repo y documento
dentro del tenant actual y comprobar correspondencia entre source/doc/version/repo.

## T005 — recepción privada e idempotencia

Autorización tenant/repo antes de acceder a datos/objetos. Carga acotada, MIME/tamaño
reales y SHA-256 durante streaming; límites explícitos configurables y formatos
contrastados con docs/05/09. No confiar solo en extensión, Content-Type o Content-Length.
No ejecutar, extraer texto ni procesar embeddings. Contenido temporal solo privado,
con cota y limpieza; nombres del cliente nunca determinan rutas/identificadores físicos.

Idempotency-Key ligada a actor/repo y huella del pedido: repetición devuelve mismo
documento/versión; contenido distinto con la misma clave devuelve conflicto.
Estado durable de recepción ante efectos SQL/S3 parciales, propiedad del objeto y
compensación/reintento. Invalidación/límite no deja objeto huérfano persistente.
No borrar objeto ajeno ni aparentar transacción distribuida; impedir READY/PUBLISHED
falsos. Probar caída/reintento/concurrencia y limpieza de temporales propios.

## T006 — descarga y API integrada

Rutas lógicas por UUID bajo /api/v1/tenants/{tenant}/repositories y documents.
Añadir perfiles concretos de CRUD/ACL/descarga a los contratos previstos sin cambiar
su semántica. Proxy de original autorizado, streaming acotado, cabeceras/nombre/MIME
validados, no almacenar buffer completo ni exponer claves/refs/destinos.
Revalidar tenant/repo/documento antes de cada operación. No URL durable pública o acceso
directo anónimo. Errores v1 y request_id sin inputs sensibles/excepciones; no JWT en logs.

## T007 — integración y aceptación

Cuatro fixtures propias en ambas topologías PostgreSQL; usuarios A/B con permisos
distintos y usuario del mismo tenant sin ACL. Pruebas API+SQL+MinIO reales de lectura,
carga/descarga, cruces UUID/objeto, inválidos/límite, idempotencia y fallos parciales.
Counters/espías para denegación antes de secretos/pools/S3 cuando corresponde; una
respuesta HTTP por sí sola no prueba ausencia de acceso. Captura local sin secretos.
Tests offline, CI y regresión F00/F01/F02. Matriz R/AC/V, límites y postmerge por PR.
Cerrar F03 solo con evidencia; continuar F04 conforme ADR-0010 sin otra orden rutinaria.

## Presupuesto y reversión

Conservar límites de servicios existentes; API un worker 512 MiB/0.25 CPU, herramienta
serial 768 MiB, pools globales acotados. Medir antes de ampliar y serializar baterías.
No exponer nuevos puertos ni montar secretos infra en el runtime.
Retirar tráfico/perfil F03 o volver a código compatible sin borrar bases/buckets/objetos.
Sin downgrade destructivo, restore/HA de producción, cambio de visibilidad o main/tag.
