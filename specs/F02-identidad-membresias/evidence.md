# Evidencia F02

Estado: T001..T004 integradas en PR #20..#23; T005 implementada y comprobada; F02 no aceptada.
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
