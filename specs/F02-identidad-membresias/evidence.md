# Evidencia F02

Estado: T001..T006 integradas en PR #20..#25; T007 documenta aceptación técnica delegada.
Cierre efectivo con CI/revisión/merge/postmerge de su PR. Las secciones anteriores son históricas.
Las anotaciones de planificación siguientes conservan el estado histórico.

Base inspeccionada en ragdev01: develop@f66a38c8dbfe6d9244eef3cf390ed16f37998b41,
checkout limpio. Lectura de constitución, arquitectura, tenancy, modelo de datos,
contratos API, NFR, roadmap, amenazas, gobierno y spec F02.
F01 cerrada en PR #15; autorización diaria de pruebas integrada en PR #18.
Sesión verificada ACTIVE con vencimiento original 2026-11-01T21:34:19-05:00;
esa lectura no demuestra validez al ejecutar futuras pruebas.

## Resultados pendientes

V01..V07 pendientes. No se instaló/arrancó IdP, no migraciones, usuarios/membresías
o endpoints nuevos en esta entrega. No se ejecutaron pruebas de funcionalidad F02.
La validación documental y CI de este PR se registrarán en su conversación;
no equivalen a aceptación técnica de la fase.

## Registro por entrega

Anotar tarea/requisitos/AC, commit y hashes, fecha/entorno/comando, resultado observado,
negativos, cambios de esquema/config/dependencias, recursos conservados, límites
y resultado postmerge. Salidas saneadas; no bearer, claves, passwords ni claims
personales. Un fallo mantiene abierto el criterio afectado.

## Ratificación

Diego respondió «Keycloak solo para desarrollo (recomendado)» a la decisión
concreta de D-04 presentada en PR #19. Proveedor de producción no elegido.
Ejecución de F02 dentro del roadmap autorizada; revisión/merge delegados ADR-0007.
Esta ratificación no acredita implementación ni cierre de fase.

## T001 — entorno IdP real en ragdev01

Base 9d37b0a7790e1cfb40d9986b78d8229ee4db9d74; rama feat/F02-T001-oidc-dev.
F02-R01, preparación de AC-F02-03/04; V01/V07 parciales.
Keycloak 26.8.1 según release oficial; índice OCI por digest en Dockerfile.
Imagen local ejecutada:
sha256:4907e364c09d86badd8c3cc95655822382beb9313575689638561f0f68e029d0.
PostgreSQL independiente, rol f02_idp con flags de superusuario/CREATEDB/
CREATEROLE/REPLICATION/BYPASSRLS desactivados, comprobados en pg_roles.
No usuarios, administrador inicial, clientes OAuth ni membresías creados.

Comandos en servidor: f02_host.py prepare/config/build/up/check;
pytest -q, Ruff check/format y scripts/check_docs.py.
PASS T001: TLS real, discovery/JWKS, issuer exacto y claves públicas de firma.
PASS T001: conexión sin CA privada rechazada; red interna, sin puertos publicados.
221 tests correctos, 71 archivos formateados, sin errores Ruff/SDD.
11 tests nuevos: preservación de datos/enlaces, metadata no confiable,
claves privadas/tipos/límites, CA y redirecciones.
Regresión real F00 API/SQL/vector/S3 correcta; daily verify canary correcto,
autorización diaria conservada sin pedir password o ampliar vencimiento.

Muestreo posterior al arranque: IdP 442.5 MiB/1536 MiB y 0.23% CPU;
PostgreSQL 44.54 MiB/512 MiB y 0% CPU; sin OOM ni salidas.
Durante inicialización se observó IdP 390.6 MiB y 78.10% CPU (cota 0.75 CPU).
La primera comprobación completó dentro de su espera máxima de 180 segundos;
no se midió p95 ni capacidad bajo carga. F00/F01 no se detuvieron.
Sin migración de rag_control o bases tenant. Sin backup/restore acreditado.

Pendientes: access token firmado/emisión/rotación T002, usuarios/membresías T003,
administración T004, contexto/API T005 y aceptación integral T006/T007.
La evidencia de T001 no cierra AC-F02 ni autoriza F03.
Fuentes exactas: [manifiesto](../../docs/evidence/f02-t001-source-sha256.txt).
Manual: [IdP dev](../../ops/f02/README.md).
CI, revisión y comprobación postmerge se registran en la conversación del PR.

## T002 — tokens verificados y rotación real

Base develop@2acd9f6c5704cde47c73690480e7131d1b690778.
Rama feat/F02-T002-oidc-validation; F02-R01/R05, AC-03/04 parciales; V01/V06.
PyJWT[crypto] 2.15.1 y cryptography 50.0.2 por hashes; sin actualizar versiones previas.
Verificador RS256/RSA >=2048, issuer/audience/exp/iat/sub y perfil access token
validados; cache JWKS <=300 s/32 claves/64 KiB, red 5 s y refresco limitado/concurrente.
Sin redirecciones, proxy, URLs de JWT, claves vencidas o roles de producto desde claims.
Identity inmutable sin bearer/claims completos y sin issuer/sub en repr.

Batería real scripts/f02_token_check.py, imagen rag-f02-tools:t002:
sha256:271784a521da6c5ef939faabbc7177e4cec7fc3137fbc409212a9fdd1182d7cb.
Verificador instalado y scripts de imagen coinciden con fuentes del servidor.
PASS T002: token Keycloak real; firma y audiencia alteradas rechazadas.
PASS T002: rotación real de clave; tokens nuevo/anterior verificados y clave original restaurada.
PASS T002: token de 5 s realmente vencido rechazado con leeway=0.
Credenciales solo en archivos privados del servidor; tokens solo en memoria.
Realm sintético rag-dev-token-fixture separado del principal, clientes de servicio,
controlador manage-realm solo en su realm; no usuario/admin master.
La batería retira solo su componente temporal; no rota secretos existentes.

Importación inicial falló por nombre de archivo diferente del realm, requisito de
DirImportProvider. Se corrigió el destino del bind y se añadió regresión de nombre,
permisos y no sobrescritura. Sin borrar/reinicializar base o secretos; prueba completa
correcta después. Se recreó solo IdP F02; PostgreSQL y F00/F01 conservados.

249 tests correctos, Ruff/formato/SDD correctos; 28 nuevos tests desde T001.
Firma y claims inválidos, ID token, none/HS, JWKS privados/débiles/duplicados,
límites/redirecciones, ráfaga concurrente de kid, rotación, caída/cache expirada,
cierre y captura de logs sin JWT/subject probados offline.
Regresiones reales: discovery/TLS/CA del realm principal, canary diario OpenBao
y F00 API/SQL/vector/S3 correctas. Sin nueva contraseña ni extensión del día.
Un aviso previo de Starlette/httpx continúa; sin tests fallidos.

Sin migraciones de control/tenant, usuarios de producto, membresías ni endpoints nuevos.
T003..T007 y aceptación integral siguen pendientes. Este servicio de prueba no
acredita login humano ni cierre de todos los AC-F02.
[Fuentes exactas](../../docs/evidence/f02-t002-source-sha256.txt).
CI/revisión/postmerge del commit publicado se registran en la conversación de su PR.

## T003 — migración y catálogo de identidad

Base e94e9854214a67feedc3ecc9bff71cfb24d3bb00; rama feat/F02-T003-identity-catalog.
F02-R02/R04/R05, AC-01/03/04 parciales; V02/V04/V06.
f02_control_0005 aplicada y repetida en rag_control con migrador limitado.
Cinco tablas aditivas, sin columnas de contenido/secreto, tipo de tenants F01
sin inferir ni modificar. Metadatos F01 separados y helpers acotados por fase.
Registro issuer+sub estable, sin auto membresías/roles; 3 fixtures sintéticas
de catálogo retenidas, sin usuario final/API creado en esta tarea.

PASS T003 real: todas las filas de tablas F01 iguales antes/después por hashes
calculados en memoria; migración repetida y F01 helper no rebaja revisión F02.
12 intentos/8 hilos/2 conexiones producen un UUID; mismo sub en otro issuer distinto.
Constraints/FK/PK y roles distintos A/B probados en PostgreSQL con SAVEPOINT revertido.
App/admin SQL separados y mínimos, TLS verify-full; app sin CONNECT a bases rag_t_*,
sin escritura de membresías/estados/roles, DDL o alteración de auditoría.
Admin sin modificar issuer/sub o auditoría existente. Suspensión denegada y
auditada sin reactivar la identidad; estado de fixture restaurado al finalizar.
Un negativo inicial obtuvo el límite VARCHAR antes del CHECK; ensayo corregido
para probar el CHECK y batería completa repetida, sin rotación o borrado.

260 tests offline correctos; Ruff/formato/SDD correctos.
Regresión real CLI F01 diaria (tres PASS T007) después del esquema ampliado,
con su nueva fixture sintética esperada; autorización diaria conservada.
F00 API/SQL/vector/S3 real correcto. Sin reinicio de Bao/PG/MinIO.
Manual y matriz de permisos en ops/f02/README.md.
[Manifiesto de fuentes](../../docs/evidence/f02-t003-source-sha256.txt).
CI, commit exacto, revisión e integración/postmerge en conversación del PR.
T004..T007 y aceptación F02 pendientes; no F03.

## T004 — CLI de identidad real y locks

Base b568d6a5d5eb3297724fcf2cc6ebab37c2d556bf; rama feat/F02-T004-identity-cli.
F02-R02/R04/R05; AC-01/03/04 parciales; V02/V04/V06.
PASS real: CLI OIDC, bootstrap con autorización infra adicional y sin roles del JWT.
Matrices owner/admin/editor/reader/support, ausencia de autoridad global sobre
tenant ajeno, protección frente a takeover, permisos consultados en control.
Dos procesos CLI distintos retiran owner simultáneamente: exactamente uno pasa
y otro LAST_OWNER; estado final restaurado con un owner. Suspensión de Bob
denegada al iniciar sesión y restaurada; último platform_operator protegido.
Archivos JWT tmpfs 0600 eliminados; respuestas/stderr sin bearer, subject IdP
o contraseñas. Registro y denegaciones auditados sin datos sensibles.

Cuatro identidades IdP sintéticas aceptadas en realm fixture v2, con 4 tenants
físicos nuevos READY de propiedad/idempotency keys F02. Tipo explícito solo en
esas fixtures. Alice owner A/reader B, Bob editor A/owner B; Carol reader A/support,
Dave sin membresías. Fixture anterior de IdP preservada, sin roles de producto.
Catálogo F01 fuera de las cuatro operaciones conserva hashes exactos.

Hallazgos de implementación corregidos sin debilitar controles:
audiencia exigió declarar el cliente rag-api; nuevo realm conserva el anterior.
IDs de usuario deben ser únicos globalmente en Keycloak; transacción fallida
verificada revertida antes de ajustar solo IDs aún no persistidos, sin rotar passwords.
FOR UPDATE exigía privilegio UPDATE del catálogo F01; se sustituyó por advisory
xact lock por tenant, sin ampliar grants. Batería real completa correcta después.
Regresiones offline cubren audiencia, nombre de import y IDs únicos por realm.
T005 contexto/API y T006/T007 aún pendientes; F02 no cerrada.

Verificación T004: 269 tests offline correctos; Ruff check y 85 archivos formateados;
check_docs correcto. La advertencia de compatibilidad Starlette/httpx ya existente
no afecta el resultado y no se silencia. Hashes: docs/evidence/f02-t004-source-sha256.txt.

## T005 — contexto y API de identidad

Base develop@d7e3aec78f08007878ba2a564f6ed3be60f5f134, rama
feat/F02-T005-authorized-api. Fuentes/herramientas/construcción y ejecución en ragdev01.
F02-R02/R03/R04/R05; AC-01/02/03/04, V03/V05 parcialmente offline hasta T006.

Contexto inmutable firmado, vinculado a request UUID y máximo 30 s; roles y referencias
versionadas revalidadas en control antes del registro F01. Roles JWT/cabeceras ignorados
como autoridad. Reader se adapta a readonly y no admite elegir otro rol SQL.
GET /me y /tenants reales con OIDC Keycloak/TLS y PostgreSQL: Alice owner A/reader B,
Carol solo A, Dave sin membresías; cursor limitado/ligado a identidad, token inválido
e ID token rechazados, suspensión efectiva en próxima solicitud y restaurada.
No rutas públicas admin/contenido/tests. API separada con rol SQL app, sin secretos
administrativos, sesión diaria o MinIO; 512 MiB/0.25 CPU, sin puertos publicados.

Batería real api-check completa y captura local de logs correcta (sin mostrar cuerpos).
Runtime medido aproximadamente 71 MiB API, 508 MiB IdP, 39 MiB PostgreSQL propio;
F00/F01 permanecen activos. Se corrigieron antes de integrar: lista tmpfs YAML,
mapeo de error de token ausente a 401 y lookup de fixtures en herramienta migrator
sin ampliar grants del runtime. Fixtures sintéticas y datos previos conservados.
Los tests de contexto/IDOR emplean espías offline; cero acceso SQL/S3 real ante
denegación y ambas topologías siguen pendientes de T006. No se declara F02 aceptada.

Bloqueo separado detectado: desapareció el archivo privado de sesión diaria junto al
runtime de usuario, con Linger=no. Se habilitó Linger=yes para conservarlo tras logout;
no se recuperó bearer, no renovación/revocación ni reinicio Bao. daily status rechaza
por falta de autorización; el operador debe ejecutar daily start desde su terminal.
El token anterior puede seguir válido hasta su TTL original, no consta revocación.
T005 no requiere esa sesión; T006 con secretos reales permanece pendiente de reemisión.

T005 regresión: 287 tests offline correctos, Ruff check y 91 archivos formateados;
check_docs correcto. Manifiesto: docs/evidence/f02-t005-source-sha256.txt.

## Preparación T006 — integración todavía pendiente

Base develop@b23b6bedc018b36a57cea269a05ccdb2f2292c3c (T005 integrada PR #24;
docs/lint/tests del merge correctos y hashes postmerge verificados en ragdev01).
Rama feat/F02-T006-isolation: herramienta de pruebas y fixture HTTPS loopback
preparadas para contadores secretos/conexiones/queries/S3 y topologías SAME_INSTANCE/
TWO_INSTANCES. Sin modificar código de producto ni crear rutas públicas de contenido.
Construcción/configuración/lint no acreditan ejecución real.

La ejecución queda bloqueada por ausencia del archivo de sesión diaria. El ajuste
Linger=yes está comprobado; daily start sigue siendo una acción del operador con su
contraseña en su terminal. No recuperar root, almacenar contraseña, renovar el token
automáticamente ni simular las pruebas. T006/T007 y aceptación F02 siguen pendientes.

## Ejecución T006 — autorización y correcciones del comprobador

Diego emitió una nueva sesión diaria el 2026-11-01 con vencimiento
2026-11-02T06:38:16-05:00. daily verify confirmó canary real desde otro proceso SSH;
Linger=yes comprobado. No root/unseal, reinicios Bao, renovación automática ni contraseña
en conversación/herramientas. El bloqueo histórico de la preparación quedó resuelto.

Antes de acreditar el resultado se corrigieron tres problemas del comprobador:
(1) libpq omite SQLSTATE en ciertos rechazos de arranque; ahora se verifica firma exacta
y CONNECT negado previo, con 9 negativos offline que rechazan TLS/red/otro usuario/base.
(2) el probe intentaba leer ops_identity, restringida expresamente en F01; ahora ejecuta
SQL/vector permitido y comprueba que SELECT operativo sigue negado. Sin nuevos grants.
(3) el cliente HTTPS de pruebas dejaba keepalive abierto al apagar el fixture; reproducción
aislada confirmó timeout con cliente abierto y salida normal tras cerrarlo. Se separó
del cliente IdP y se cierra antes del servidor, conservando restauraciones por CLI.
No se modificó código de producto ni datos F01 para corregir esos fallos.
Las ejecuciones parciales con fallo no se presentan como batería completa aceptada.

## T006 — batería completa correcta

Base PR #25 preparado en 4d7f4e828e92eac06fe5f3116f8ce0709c199198, derivado de
develop@b23b6bedc018b36a57cea269a05ccdb2f2292c3c. Correcciones y ejecución posteriores
en ragdev01; F02-R01..05, AC-01..04, V01..V07.

PASS SAME_INSTANCE y TWO_INSTANCES: identidad OIDC real, Alice owner A/reader B/A,
Carol reader A sin acceso B, Dave sin membresía. Conexiones propias verifican
base/rol/TLS y SQL/vector permitido; S3 lista bucket propio. Credenciales SQL/S3
cruzadas rechazadas en ambos sentidos, con positivos previos del mismo destino.
Contadores de lecturas de secretos, intentos de conexión, consultas tenant y llamadas
S3 permanecen iguales ante UUID/headers/payload JWT/contexto falsificados y usuario,
membresía SUSPENDED/REVOKED, tenant suspendido o versión incompatible, con pools
fríos/calientes según caso. Contexto de otra solicitud rechazado. No fallback.

Cierre correcto del proceso HTTPS temporal tras cerrar su cliente. Captura privada
local: forbidden_value=false, jwt_pattern=false, traceback=false; no se mostró el
log crudo. Recursos, datos y cuatro fixtures T004 conservados; estados restaurados
y membresías auxiliares previas restauradas (las nuevas se conservan revocadas).
Hashes del catálogo F01 fuera de esas fixtures iguales antes/después.

297 pruebas offline correctas (9 nuevos rechazos de arranque estrictos y un caso
API 503 por dependencia de identidad sin registro de usuario ni bearer en logs).
Ruff check, formato de 94 archivos y check_docs correctos. Aviso Starlette/httpx
ya existente, sin silenciar ni atribuirlo a fallo funcional.
Rotación real de claves y caducidad real del token corto repetidas correctamente
con la herramienta histórica T002: clave original restaurada, sin valores de tokens.
No nuevas dependencias, migraciones, grants, datos de contenido o servicios persistentes.
T007 y cierre técnico de fase permanecen pendientes de evidencia final/revisión/merge.

Regresión final T006: API T005 real y captura de logs correctas; F00 API/SQL/vector/S3
correcta; CLI F01 diaria con tres PASS T007 en ambas instancias, reintento, check y
migración sin rotación. La regresión CLI conserva su fixture nueva esperada; esa alta
pertenece a la herramienta F01, no a la batería T006 que reutiliza sus cuatro fixtures.
daily verify posterior confirma canary y sesión vigente sin revocarla ni renovarla.
Tres módulos de API en ejecución y ambos scripts T006 de imagen coinciden por SHA256
con las fuentes revisadas. Imagen T006:
sha256:fb407bff4e1abc8b9313f22c9d7c3f23ebb9e713cf21368cc6a0d798cccb4355.
Los mensajes de cierre parcial de las herramientas históricas T002/T005/T007-F01
se refieren a su alcance; no sustituyen el estado actual de esta evidencia.
Manifiesto final T006: docs/evidence/f02-t006-source-sha256.txt.

## T007 — aceptación técnica y cierre documental

Base develop@29a3a84f79925001ff57dafa3debfa5997a325e7, rama feat/F02-T007-acceptance.
T006 postmerge en ragdev01: checkout limpio, 18 hashes correctos y check_docs correcto.
CI del merge docs/lint/tests success; [registro](https://github.com/dlalvarez/rag-platform/pull/25#issuecomment-6557775077).
No repetir baterías sensibles que ya pasaron para producir evidencia documental.

[Acceptance](acceptance.md) consolida R01..05 / AC-01..04 / V01..V07, revisión de
seguridad/compatibilidad, comandos, pruebas offline/reales y límites. Manual y README
actualizados al estado implementado, conservando los pendientes históricos en sus entregas.
Codex actúa bajo la delegación de Diego y ADR-0007, sin nueva aprobación humana atribuida
ni revisión independiente. Cierre efectivo al integrar este PR con checks/postmerge
registrados en su conversación. No habilita otra fase ni promoción main/tag/producción.
La sesión diaria se conserva hasta su vencimiento; no nuevas contraseñas o reinicios.
