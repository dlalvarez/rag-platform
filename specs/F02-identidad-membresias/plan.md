# Plan F02 — identidad y membresías

Estado: T001..T006 implementadas, probadas e integradas en PR #20..#25.
T007 documenta aceptación técnica delegada, manual y matriz final; cierre efectivo
con integración/CI/postmerge de su PR. D-04 conserva Keycloak solo de desarrollo.
Base: develop@f66a38c8dbfe6d9244eef3cf390ed16f37998b41.
F01 aceptada en PR #15. Seguimiento operativo de acceso diario integrado en PR #18.
Diego renovó la delegación de revisión e integración de actividades dentro del plan;
no se pide aprobación rutinaria por tarea o PR. La decisión de D-04 fue tomada
expresamente por Diego; no se atribuye a una autoaprobación.

Fuentes: [spec](spec.md), [arquitectura](../../docs/02-architecture.md),
[tenancy](../../docs/03-tenancy-security.md), [API](../../docs/07-api-contracts.md),
[ADR aprobado](../../docs/adr/0009-development-oidc.md).
No se modifica el roadmap ni F02-R01..05/AC-F02-01..04.

## Resultado y límites

Identidad OIDC validada; UUID interno y membresías en rag_control; contexto autorizado
inmutable que precede a cualquier resolución SQL/S3. Los únicos endpoints públicos
previstos son GET /api/v1/me y GET /api/v1/tenants, autenticados.
No alta pública, contraseñas propias, UI, ACL de repositorios, documentos, ingesta,
jobs, RAG, chat, facturación, SSO empresarial o producción. No exponer el provisionador
F01 como API de alta. No vincular userpass de OpenBao con usuarios del producto.

## P1 — proveedor y entorno (T001)

Decisión D-04: Keycloak solo como IdP de desarrollo; adaptador configurable por
issuer/audience/JWKS. [ADR-0009](../../docs/adr/0009-development-oidc.md) compara
alternativas y reversión. No fijar IdP comercial/de producción por esta elección.
Seleccionar release soportada, verificar avisos/versiones y
fijar imagen por digest antes de descargar/ejecutar en ragdev01. No usar latest.

Proyecto/perfil F02 separado; TLS con CA validada, hostname/issuer estables, puertos
de administración internos, ninguna exposición LAN/Internet automática.
Persistencia bajo /srv/rag-data/rag-platform/f02 tras verificar montaje y ownership.
Base/rol propios del IdP, separados de rag_control y de bases tenant.
Presupuesto inicial para probar: IdP 1536 MiB, PostgreSQL propio 512 MiB,
API 512 MiB y herramienta serial 768 MiB. Medir consumo real junto a F00/F01;
no ampliar límites ni parar servicios existentes para encajar una prueba.
En 2 vCPU serializar builds/baterías y medir readiness/timeout, sin prometer capacidad.
Secretos generados en servidor y custodiados fuera de Git/logs/argumentos; bootstrap
del IdP separado del runtime. No reiniciar Bao ni repetir configure.
Reutilizar la sesión diaria vigente mediante API de sesión, no extraer bearer
a la conversación ni ampliar su vencimiento. Caducidad real bloquea pruebas que
necesiten secretos, nunca habilita fallback.

## P2 — validación de identidad (T002)

Cliente resource server: validar access token destinado a la API, no tratar cualquier
ID token como autorización. Perfil de access token explícito para el IdP elegido.
Firma con biblioteca mantenida, algoritmo asimétrico permitido configurado por servidor,
issuer exacto, audience API, exp/nbf/iat y sub presentes/tipados según perfil.
No algoritmo decidido por JWT, none/HS como sustitución de clave pública, firma
desactivada o aceptación por email. Acotar tamaño de token/claims y tolerancia de reloj.
Resolver JWKS únicamente desde configuración/discovery de issuer permitido y TLS;
ignorar jku/x5u/URLs arbitrarias del token. Sin redirecciones hacia destinos no permitidos.
Cache de claves acotada, timeout y refresco limitado por kid desconocido; rotación probada.
Ante dependencia caída, clave desconocida o token no validable: sin contexto/fallback.
Distinguir credencial inválida 401 de dependencia indisponible 503 sin filtrar detalles.

## P3 — datos de control y administración (T003/T004)

Migración Alembic control aditiva. Identidad única por par (issuer, subject) con UUID
interno estable; email no identifica ni fusiona usuarios. Estado activo/suspendido.
Sin passwords, tokens, claims completos ni perfiles personales innecesarios.
Primer login válido puede registrar identidad idempotente; nunca crea membresía o rol.
Membresías únicas por (user_id, tenant_id), estado y rol owner/admin/editor/reader.
Roles de plataforma platform_operator/platform_support separados de roles tenant.
No confiar en tenant_id, roles de producto o permisos administrativos enviados en JWT.
Claims del IdP autentican identidad; la autoridad de acceso reside en control.

Tipo PERSONAL/ORG del tenant según modelo rector: migración explícita, sin inferir
tipo de tenants F01 existentes ni cambiar su estado. Diseñar expansión compatible;
clasificar únicamente fixtures nuevas de F02 en la prueba. Documentar cómo tratar
registros existentes no clasificados antes de usar esa característica.
Sin esquema/contenido adicional dentro de bases tenant ni FK entre bases.

Administración inicial por CLI interna autenticada/auditada y privilegio explícito.
Ningún usuario se autoasigna platform_operator; bootstrap de fixture sintética
separado del runtime. platform_support no recibe acceso a contenido.
owner administra membresías/roles del tenant; admin gestiona editor/reader sin
otorgar owner/admin ni promoverse. editor/reader no administran membresías.
No dejar tenant sin owner activo por cambio de membresía; transacción/lock ante carreras.
Bootstrap del primer owner mediante operación privilegiada explícita auditada.
No endpoints nuevos de administración o autoservicio en F02.

## P4 — contexto y API (T005)

AuthorizedTenantContext inmutable: principal UUID, tenant UUID, roles verificados,
db_ref/storage_ref y trace_id opacos; sin credenciales ni destinos físicos serializados.
Verificar identidad activa, membresía activa, tenant READY y esquema compatible
antes de resolver secretos, abrir pool o consultar datos tenant.
No aceptar AdministrativeTenant desde una ruta de usuario ni convertir UUID sin autorizar.
Conservar la CLI administrativa F01 y sus límites; adaptar entrada de aplicación
sin confundir autorización humana con autoridad del provisionador.

Revalidar membresía/estado por request; no cachear decisiones de acceso indefinidamente.
Cambio A→B→A con rol de cada tenant, sin mezcla de conexiones/credenciales.
Una identidad suspendida, membresía revocada o tenant suspendido deja de autorizar
en la siguiente solicitud. El contexto no se reutiliza entre solicitudes/jobs.
GET /me devuelve UUID interno y membresías permitidas; GET /tenants solo tenants
autorizados, con paginación opaca acotada. Sin issuer/sub/email, nombres físicos,
refs de secretos o claims privados en respuesta. Errores versionados y request_id.
Probar parámetro/ruta/cabecera tenant falsificados con dependencia/contexto y ruta
de fixture solo de tests; no crear una API de repositorios F03 para ensayar F02.

## P5 — auditoría y aceptación (T006/T007)

Auditoría de identidad/denegación con códigos cerrados, UUID interno cuando exista,
tenant/request UUID válidos y timestamp; sin JWT, Authorization, issuer/sub/email,
contraseñas, query strings o excepción de proveedor en logs/respuestas.
El audit_control F01 requiere operación de provisión: no inventar operaciones
para auditar login. Tabla/evento de identidad separado con constraints y grants mínimos.
Probar captura de logs de API, adaptador y dependencias en negativos.

Tests offline reproducibles con claves generadas en memoria. Integración aparte
con IdP real TLS, PostgreSQL real y dos tenants sintéticos en ambas topologías F01.
Demostrar permisos distintos de un usuario en A/B, otro usuario solo en A,
usuario válido sin membresía y rechazo por token/estado/clave/servicio incorrectos.
Espías/contadores demuestran cero resolución de secretos y cero conexión tenant
cuando la autorización se deniega; una respuesta 403 sola no lo demuestra.
Probar migración repetible, restricciones, concurrencia de membresías y rollback
en fixture aislada, preservando datos F01. F00/F01 y CI no pueden regresionar.

Revisión del mismo agente según ADR-0007, PR a develop, checks y conversaciones
correctos antes de merge, evidencia postmerge. No aprobación fingida de Diego.
No marcar F02 cerrada por crear documentos, mocks o endpoints sin integración real.

## Archivos previstos y reversión

src/rag_platform/providers/identity.py; módulos control/identity y tenancy/authorization;
adaptación API sin romper /healthz; migrations/control; scripts/f02_*; ops/f02;
tests/unit/f02 y tests/integration/f02; pyproject/uv.lock solo dependencias justificadas.
Conservar pistas de migración separadas y versiones tenant F01.

Retirar tráfico/perfil F02 y volver al código compatible sin borrar bases/buckets.
No downgrade destructivo de tablas con usuarios/membresías ni borrar Raft/IdP.
Reversión de datos solo ensayada en fixture aislada. Sin backup/restore de producción
acreditado; mantener ese límite explícito.
