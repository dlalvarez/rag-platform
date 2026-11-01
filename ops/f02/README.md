# F02 — IdP de desarrollo, T001

Keycloak solo desarrollo aprobado por Diego en ADR-0009/PR #19.
No IdP de producción, usuarios reales ni UI de producto.

## Operación en ragdev01

Trabajar en /home/diego/proyectos/rag-platform. Preparación inicial:
    python3 scripts/f02_host.py prepare
    python3 scripts/f02_host.py config
    python3 scripts/f02_host.py build
    python3 scripts/f02_host.py up
    python3 scripts/f02_host.py check
    python3 scripts/f02_host.py status

prepare no sobrescribe datos ni configuración existentes. Si falla o hay estado
parcial, conservarlo y revisar; no borrar/reinicializar para ocultar el fallo.
No repetir prepare en el entorno existente.

Datos: /srv/rag-data/rag-platform/f02, ext4 montado. .env.f02 contiene solo rutas/UID.
Archivos TLS y bootstrap privados; certificados públicos 0444, secretos 0600,
directorios 0700. No mostrar config/keycloak.conf o config/init.sql:
contienen la contraseña SQL del IdP. No montarlos en API/herramienta de comprobación.
La clave de la CA no se monta en ningún servicio.

IdP: Keycloak 26.8.1, índice OCI
sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332.
Imagen local optimizada rag-f02-keycloak:26.8.1; registrar image ID real en evidencia.
PostgreSQL: imagen PG17/pgvector 0.8.7 ya fijada en F01, sin actualizar sus clústeres.
Esta base no instala esquemas RAG ni usa el rol bootstrap como runtime:
f02_idp es NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION/NOBYPASSRLS.

TLS API IdP y JDBC verify-full con CA propia; http deshabilitado.
Issuer interno fijo: https://idp:8443/realms/rag-dev. Realm no permite registro,
reset de password o login por email. Importación inicial sin usuarios ni clientes.
T001 no crea administrador inicial; la preparación de identidades/cliente sintéticos
para T002/T006 será una operación separada, con bootstrap privado y auditado.
Nunca pasar credenciales a argumentos ni copiar la sesión diaria de OpenBao al IdP.

Red Docker interna rag-f02-dev_f02; sin puertos publicados. El check solo recibe CA
y su script, sin claves privadas, contraseñas de SQL, Docker socket o credenciales Bao.
No acceso a F00/F01 desde esta red. No exponer hostname/puertos a LAN automáticamente.

## Presupuesto y aceptación

Límites: IdP 1536 MiB/0.75 CPU, PG 512 MiB/0.25 CPU y check serial 768 MiB/0.25 CPU.
API F02 aún no creada. Medir consumo/OOM/readiness real, no inferir capacidad del límite.
La comprobación espera hasta 180 segundos y valida discovery/JWKS reales;
una conexión sin la CA privada debe fallar por verificación de certificado.

T001 no prueba emisión ni validación de access tokens, login de usuario, rotación,
membresías, roles, API o autorización tenant. Esos AC siguen abiertos.
Pruebas unitarias/CI offline no requieren Keycloak ni Internet.
La integración real se ejecuta aparte solo en ragdev01.

## Conservación y reversión

No down -v, prune, eliminación de bases o buckets ni reinicio de Bao/F00/F01.
Retirar tráfico y detener únicamente servicios propios F02 si fuera necesario,
conservando /srv/rag-data/rag-platform/f02 y sus secretos. No prometer backup/restore.
El wrapper no ofrece borrado. Cambios de hostname/issuer o sustitución de IdP
requieren compatibilidad/mapeo explícitos; no vincular identidades por email.

Fuentes verificadas:
[release 26.8.1](https://github.com/keycloak/keycloak/releases/tag/26.8.1),
[contenedores](https://www.keycloak.org/server/containers),
[TLS/configuración](https://www.keycloak.org/server/configuration-production).
La release incorpora correcciones de seguridad; no equivale a un escaneo completo
de la imagen ni garantiza ausencia de vulnerabilidades. Sin federation, broker,
token exchange o extensiones custom de IdP en este perfil.

## T002 — validador y fixture de tokens

T002 añade PyJWT[crypto] 2.15.1 y cryptography 50.0.2, fijados en uv.lock.
No cambia versiones existentes. OIDCSettings configura issuer, audience, JWKS y CA.
Solo firma RS256/RSA >=2048; perfil Keycloak exige access token Bearer, no ID token.
El perfil RFC9068 requiere header at+jwt. No roles/membresías desde claims.
Identity es inmutable, conserva solo issuer/sub/exp y no imprime identidad en repr.

JWT máximo 16384 caracteres, JWKS máximo 64 KiB/32 claves, TTL cache <=300 s,
refresco mínimo configurado (30 s por defecto), red TLS/5 s y sin proxy/redirecciones.
kid desconocido dispara refresco limitado, también tras errores; no URLs del JWT.
Cache válida permite comprobar una firma conocida sin red; expirada o clave
desconocida sin refresco correcto falla cerrada. No fallback a claves vencidas.
Tolerancia de reloj 0..30 s; no se desactiva firma/issuer/audience/exp/iat.

Sobre el entorno T001 existente, solo una vez:
    python3 scripts/f02_host.py prepare-tokens
    python3 scripts/f02_host.py build-tools
    python3 scripts/f02_host.py up
    python3 scripts/f02_host.py tokens

Estos pasos ya están ejecutados en ragdev01; no repetir prepare-tokens.
En una preparación nueva, prepare también crea la fixture T002.
up aplica únicamente los servicios propios F02; importar una nueva fixture puede
recrear el IdP. No reinicia Bao ni PostgreSQL F00/F01.

Fixture: realm rag-dev-token-fixture, distinto del realm principal rag-dev.
Tres clientes de prueba: f02-probe, f02-short y controlador de fixture.
Solo el controlador tiene manage-realm en ese realm para generar una clave
temporal; no administrador master ni permiso sobre memberships del producto.
Sin contraseñas de usuarios: grant client_credentials para identidades de servicio
sintéticas. No usar esta prueba como evidencia de login humano o membresías F02.

Importación exige el nombre <realm>-realm.json. Archivo y credenciales de fixture
fuera de Git, 0600; controller/probe/short solo montados en token-check, nunca API.
La herramienta genera una clave temporal, verifica token nuevo y anterior, retira
únicamente su componente y comprueba que la clave original vuelve a emitir tokens.
Tokens quedan en memoria; no se imprimen ni almacenan en archivos.
La prueba de caducidad usa f02-short (5 s), sin cambiar lifespan del realm ni
contraseñas/secretos existentes. El validador de esa prueba usa leeway=0.
Si falla, informa únicamente F02-T002 y etapa; no pegar salidas de Keycloak.

La importación inicial T002 falló por nombre de archivo distinto del realm.
Se corrigió el destino del bind mount según el código oficial DirImportProvider
y se añadió test de esa convención. Se conservaron base/secretos y realm principal;
la batería completa pasó después. No se borró/reinicializó nada para recuperarlo.
No ejecutar el manifiesto histórico T001 sobre fuentes modificadas por T002:
usar el manifiesto T002 y conservar el anterior como evidencia del commit T001.

[Convención de importación verificada en código oficial](https://github.com/keycloak/keycloak/blob/26.8.1/model/storage-services/src/main/java/org/keycloak/exportimport/dir/DirImportProvider.java).

## T003 — catálogo de identidad y permisos SQL

Migración f02_control_0005, aditiva sobre f01_control_0004: users (issuer+sub únicos),
memberships, platform_roles, tenant_profiles e identity_audit. Base declarativa
separada; sin añadir contenido privado o clasificar/modificar tenants F01 existentes.
Ausencia de tenant_profiles significa tipo aún no clasificado; nunca PERSONAL implícito.
El alta idempotente registra UUID interno y auditoría, no membresía o rol automático.
Identidad suspendida no se reactiva al repetir login; su denegación se confirma antes
de devolver error. Auditoría solo UUID/códigos/timestamp, sin subject/issuer/JWT.

Credenciales de runtime/admin de control separadas, generadas en servidor:
    python3 scripts/f02_host.py prepare-identity
    python3 scripts/f02_host.py build-control
    python3 scripts/f02_host.py control

Ya preparadas/aplicadas en ragdev01; no repetir prepare-identity.
prepare de un host nuevo incluye la preparación. Nunca mostrar identity_*_password.
El perfil control-check monta bootstrap/migrator explícitos y nuevos secretos; solo
se usa para migración/ensayo, no como API. No tiene secretos IdP, MinIO o Bao.
Se conecta por la red interna F01; ninguna base nueva ni puerto publicado.

f02_identity_app: SELECT de identidad/membresías/roles/perfiles y catálogo de destinos,
INSERT solo id/issuer/oidc_subject en users, INSERT de auditoría sin sobrescribir
timestamp. Sin modificar estados/membresías/roles, DDL ni auditoría existente.
f02_identity_admin: además administra estado/roles/membresías/perfil con columnas
limitadas; no altera issuer/sub ni modifica/elimina auditoría.
Ambos NOINHERIT, sin superuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS ni membresías
SQL heredadas. Contraseñas existentes no se rotan en un reintento; ownership ajeno
bloquea bootstrap. Statement/error echo se deshabilita solo en esa sesión privada
de bootstrap para no registrar material de CREATE ROLE.

El helper F01 conserva revisión f01_control_0004 como límite al iniciar una base.
Si ya existe una revisión descendiente conocida, no la rebaja. F02 invoca
upgrade_identity explícitamente. El probe F01 de fuentes actuales admite el catálogo
extendido; imágenes históricas siguen siendo evidencia de sus commits, no migradores
de F02. La CLI F01 diaria original fue probada después de ampliar el catálogo.

Prueba real: migración repetida, hashes de todas las filas F01 antes/después,
12 intentos/8 hilos/2 conexiones para una identidad, mismo sub en distinto issuer,
constraints/FK/duplicados y perfiles en SAVEPOINT revertido. App no conecta a
ninguna BD rag_t_*; no auto roles; suspensión denegada/auditada y restaurada.
Tres identidades sintéticas de catálogo se conservan. No son usuarios IdP reales.
El probe negativo usa rol inválido de longitud válida para medir CHECK:
PostgreSQL rechazaba primero VARCHAR(8) con el valor anterior, y se corrigió el ensayo.
No se borró/reinicializó nada para recuperarse; auditoría y credenciales conservadas.
Reversión de esquema con datos es una operación aparte, no downgrade automático.

## T004 — CLI autenticada de identidad

Comandos internos: me, bootstrap-operator, bootstrap-owner, membership,
platform-role y principal-state. --token-file recibe una ruta privada 0600,
propietario actual, archivo regular sin symlink/hardlink; nunca un JWT en argumentos.
Errores de parser son códigos constantes y no repiten entradas. El JWT se valida
contra issuer/audience/JWKS configurados por servidor; actor UUID se obtiene de
issuer+sub y estado activo, nunca de --actor, cabeceras tenant o roles del token.

identity-cli monta solo app/admin SQL, CAs y tmpfs de tokens. identity-bootstrap
añade la autorización diaria para el bootstrap inicial de platform_operator:
sesión OpenBao verificada y canary leído, sin renovación/revocación. No se autoasigna
un segundo operador por tener un token válido o acceso a la fixture.
cli-check añade credenciales sintéticas/infra para crear exclusivamente sus cuatro
tenants de prueba; no es el perfil de API ni el flujo de un usuario final.
    python3 scripts/f02_host.py prepare-humans
    python3 scripts/f02_host.py build-cli
    python3 scripts/f02_host.py up
    python3 scripts/f02_host.py cli
Ya preparado en ragdev01: no repetir prepare-humans ni reemplazar credenciales.

Realm activo de fixture: rag-dev-identity-fixture-v2, sin administrador master.
Cuatro usuarios sintéticos y cliente de pruebas con direct grant, solo integración
privada de desarrollo; no acredita login web/PKCE ni elige el flujo de producción.
API sigue aceptando access tokens; no recibe las contraseñas del IdP.
El cliente de audiencia rag-api debe existir. UUID de fixture incluye nombre de
realm: Keycloak usa IDs de usuario únicos también entre sus realms.
El primer realm sin audiencia quedó conservado sin roles de producto. El intento
v2 con IDs duplicados revirtió completamente (0 realms v2) antes de corregirlos,
conservando passwords; no borrar/reimportar datos para ocultar fallos.

owner administra membresías de su tenant; admin solo editor/reader y no modifica
owner/admin; editor/reader no administran. platform_support sin acceso implícito.
platform_operator administra identidad/infra y bootstrap inicial, no toma un tenant
que ya tiene owner ni recibe membresía por su rol. Tipo PERSONAL/ORG explícito,
sin cambiar tipo existente por un reintento. Último operador también protegido.
Suspensión global no reactiva al iniciar sesión; no permite takeover de un tenant
con membresía owner activa aunque ese usuario esté suspendido.

Los cambios de membresía usan pg_advisory_xact_lock por UUID/namespace dentro de
la transacción y revalidan autoridad tras el lock. No FOR UPDATE sobre tenants:
esa operación exigiría ampliar UPDATE del catálogo F01, que se conserva denegado.
Las comprobaciones reales de dos procesos prueban serialización del último owner.
Auditoría de éxito y denegación con UUID/códigos, rollback de acción rechazada y
registro de denegación en transacción separada; sin identidad OIDC ni JWT en salida.

Batería conserva Alice owner A/reader B, Bob owner B/editor A, Carol reader A y
support de plataforma, Dave sin membresías. Cuatro tenants de fixture READY,
misma instancia y dos instancias, claves idempotentes en f02_testing.py.
No cambian roles/secretos/datos ajenos; hashes del catálogo excluyendo esas cuatro
operaciones prueban preservación de registros legacy. Tokens temporales eliminados.
Para ejecutar la CLI manualmente usar el perfil autorizado y un archivo temporal,
no copiar tokens por chat ni incorporarlos al historial. No es una API pública.

## T005 — API de identidad y contexto

Preparación única en ragdev01: `python3 scripts/f02_host.py prepare-api`.
Genera solo un certificado API dev (SAN api/localhost) y una clave privada de
autoridad/cursor, sin rotar contraseñas existentes. No volver a ejecutar si existen.
Construir con `build-api` y `build-api-tools`; arrancar únicamente API con
`api-up`; comprobar con `api-check` y `python3 scripts/f02_api_log_check.py`.
Los argumentos son acciones de scripts/f02_host.py, salvo el comprobador de logs.

API TLS interna https://api:9443, sin puertos publicados, un worker, 512 MiB/0.25 CPU,
máximo 16 solicitudes concurrentes y keepalive 5 s. Root filesystem de solo lectura.
Solo recibe contraseña SQL identity_app, CAs públicas, certificado/clave TLS de API
y clave de autoridad. Sin admin/migrator, sesión diaria, IdP passwords o MinIO.
La herramienta de integración sí recibe credenciales administrativas de identidad
para suspender/restaurar fixtures y la conexión migrator para localizar sus IDs;
esos montajes no pertenecen a la API.

GET /api/v1/me devuelve principal UUID, roles de plataforma activos y primera página
de membresías autorizadas (máximo 50). GET /api/v1/tenants devuelve items y next_cursor;
limit 1..100, cursor opaco autenticado ligado al principal. Continuar /me mediante
/tenants usando next_cursor. No issuer, subject, email, nombre físico ni referencias
de secretos. Estados y versión compatible se comprueban en cada solicitud.
JWT solo por Authorization Bearer; no tokens en URL/argumentos, ni roles de JWT como autoridad.
Errores JSON v1 con request_id generado por servidor; 401 credencial, 403 autorización,
422 entrada, 503 dependencia. Sin eco de input/tracebacks; Cache-Control no-store.
Access logs de Uvicorn desactivados para impedir registrar URLs/query strings sensibles.
Los logs de negocio solo contienen UUID de solicitud, status y código cerrado.

TenantAuthorizer emite AuthorizedTenantContext frozen/slots, UUID de principal/tenant,
rol, SecretRefs opacos, trace UUID y vencimiento máximo 30 s. MAC privado cubre todos
los campos y el contexto se revalida antes de adaptar internamente al registro F01.
Reader usa SQL readonly; owner/admin/editor usan app. No se acepta AdministrativeTenant
desde rutas de usuario ni se habilitan endpoints de contenido para probarlo.
Los espías offline prueban rechazo antes del registro; la prueba real con contadores
y ambas topologías queda en T006, no se presume por obtener HTTP 403.

### Continuidad del runtime de pruebas

Se observó la desaparición de /run/user/1000/rag-f01-access y rag-f02-auth tras
cerrar sesiones SSH; loginctl mostraba Linger=no. Se activó Linger=yes para diego
(conservación del runtime del usuario tras logout), sin tocar tokens, Bao o permisos.
La sesión diaria perdida no se recupera ni se renueva automáticamente. Para emitir otra
sesión el operador ejecuta desde su terminal SSH
`python3 scripts/f01_host.py run --rm daily start` e introduce allí su contraseña.
No repetir configure ni usar root/unseal. Verificar status/canary antes de T006.
El bearer anterior podría seguir válido en Bao hasta su caducidad original aunque
el archivo local ya no exista; no se afirma que haya sido revocado.
tmpfs se borra al reiniciar el host: no hay persistencia de credenciales en disco.
Reversión del ajuste de runtime: loginctl disable-linger diego (invalidaría continuidad
tras logout; ejecutar solo al retirar el uso diario). El token mantiene su TTL.
El lanzador F02 prepara y verifica el directorio vacío de JWT temporales cuando hace falta.
