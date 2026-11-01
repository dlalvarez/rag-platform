# API documental y entrega privada — T002/T006

Perfil F03 del servicio API existente. Desarrolla R01..R05 y AC-01..04;
requiere validación real y CI antes de aceptar F03. Sin parsing, jobs o embeddings.
La API conserva /me y /tenants de F02 y admite solo versiones identity/documents conocidas.

## Credencial de aplicación

scripts/f03_runtime_host.py prepare crea únicamente un directorio tmpfs 0700 del UID
operador con locks 0600, sin credenciales. ensure usa la sesión diaria existente en
una herramienta efímera para emitir el AppRole f03-application ya aprobado.
El emisor solo monta día, entrega privada y CA; no recibe SQL/IdP/IAM admin.

application.json 0600 se publica por rename atómico; contiene exclusivamente bearer
de aplicación y tiempos. API monta el directorio read-only, mantiene un único consumidor
con flock y valida perfil/TTL/policies en OpenBao. Tokens de root/día/operador se rechazan
y no se revocan como si fueran propios. Lectura exacta/versionada, sin KV writes,
renovación ni fallback. Cada préstamo de pool vuelve a pasar por SecretStore.

ensure reutiliza una entrega válida; renueva la entrega cerca de su vencimiento
emitiendo otra identidad limitada. No renueva el bearer anterior ni la sesión diaria.
replace es una sustitución explícita del operador diario, útil tras revocación o
reinicio de API. La API verifica la nueva entrega, revoca la identidad anterior y cierra
su cliente. Si desaparece el archivo, cambia a uno inválido, caduca o se revoca el token,
falla de forma cerrada incluso con pools calientes. No recupera acceso por sí sola.

La autorización del agente dura hasta el vencimiento del día de 24 h. El bearer del
runtime tiene la cota independiente de una hora ya fijada para F03. El agente puede
emitir reemplazos con el día vigente sin pedir contraseña; el runtime no recibe ese día.
Al cerrar el consumidor revoca su identidad. Antes de reiniciar con esa misma entrega,
usar replace; no intentar reutilizar un bearer ya revocado.

En el checkout operativo usar .env.f02 de ese checkout. En un worktree indicar
--f02-env /home/diego/proyectos/rag-platform/.env.f02 al lanzador, sin copiar secretos.
.env.f03 contiene solo UID/GID, se mantiene fuera de Git. La entrega se pierde tras
reboot; desbloqueo de OpenBao y emisión de un día nuevo siguen bajo el procedimiento
existente, sin automatizar custodia ni recuperación administrativa.

## Perfil HTTP

Rutas bajo /api/v1/tenants/{tenant_id}/repositories:

| Método/sufijo | Entrada | Salida |
|---|---|---|
| GET raíz | limit/cursor | items/next_cursor |
| POST raíz | JSON name, config opcional | 201 repository |
| GET /{repo_id} | ninguna | repository |
| PUT /{repo_id} | JSON name, config opcional | repository |
| DELETE /{repo_id} | ninguna | repository DELETED, conservando datos |
| GET /{repo_id}/acl | limit/cursor | items/next_cursor |
| PUT /{repo_id}/acl/{principal_id} | JSON role | acl |
| DELETE /{repo_id}/acl/{principal_id} | ninguna | acl retirada |
| GET /{repo_id}/documents | limit/cursor | items/next_cursor |
| POST /{repo_id}/documents?filename=... | cuerpo binario, Content-Type e Idempotency-Key | 201 document, 200 replay |
| GET /{repo_id}/documents/{document_id} | ninguna | metadata actual document |
| GET /{repo_id}/documents/{document_id}/original | ninguna | original privado como attachment |

Todas las respuestas JSON incluyen request_id generado por servidor. UUID lógicos,
sin credenciales, refs, host, bucket o claves físicas. Sin endpoint de versiones
históricas (F04), borrado físico de documentos, administración tenant ni onboarding.

Carga binaria directa: cuatro MIME de receipt.md, filename UTF-8 en query URL-encoded.
Sin multipart ni dependencia adicional. Rechazar parámetros/cabeceras duplicados,
codificación comprimida y framing ambiguo. Contar los bytes reales aunque falte
Content-Length; nunca confiar solo en la longitud declarada.
Idempotency-Key ASCII 16..128 validada antes de leer el cuerpo.
JSON de CRUD/ACL máximo 4096 bytes, claves duplicadas o campos extra rechazados.
La validación de archivo y el diario mantienen los límites de T005.

Autenticación y tenant antes de ejecutar la operación; ACL de carga antes de leer
cuerpo/crear spool/abrir S3. Capacidad global de dos cargas y dos descargas por worker,
429 si está ocupada; no cola ilimitada. Cuerpo/lectura remota con presupuesto de 20 s;
S3 tiene además timeouts de conexión/lectura. SQL conserva statement/lock timeouts.
API un worker, 512 MiB/0.25 CPU, root read-only y /tmp privado noexec 64 MiB.
Cuatro temporales máximos de 10 MiB dejan margen en esa cota; se cierran en errores
y desconexiones. No almacenar originales completos en un buffer de aplicación.

## Proxy y readonly

El lector usa su rol SQL readonly, sin permiso de consultar ops.document_receipts.
La consulta une source/document/current_version dentro del repo autorizado y comprueba
su pertenencia/estado. La clave física debe corresponder a repo/version UUID.
S3 debe coincidir con esos IDs, MIME, tamaño, SHA y marcadores estructurales del original.
GET usa If-Match sobre el ETag verificado. Los bytes se escriben en spool privado y se
verifica su SHA-256 contra la versión SQL antes de enviar un HTTP 200.
Esto no adopta ni repara objetos: una inconsistencia falla como dependencia.
La recepción conserva su comprobación más estricta del recibo/fingerprint para escribir.

Se revalida membresía/ACL después de leer S3. Cabeceras: attachment con filename*
UTF-8 percent-encoded, Content-Length verificado, MIME validado, no-store, nosniff,
CSP sandbox y Referrer-Policy no-referrer. Sin URL pública ni presignada.
Range/If-Range no están implementados y se rechazan; no se devuelve un original parcial
como si se hubiera comprobado entero. Errores v1 cerrados de F02/DocumentError,
sin input rechazado, mensajes de proveedor, JWT o trazas en logs/respuestas.

## Comprobación y promoción

Pruebas offline de archivo/locks/rotación/caducidad y adaptador HTTP, límites/concurrencia,
temporales cerrados, contenido corrupto/truncado, pérdida de permiso y desconexión.
Prueba real de handoff y pool caliente contra OpenBao, sin datos nuevos.
Ensayo HTTPS con un contenedor efímero de la misma API, sin puertos ni alias api,
mientras la instancia anterior sigue activa. El cliente verifica CA y hostname TLS api
explícitos, aunque el destino de red del candidato tenga un nombre temporal.

scripts/f03_http_check.py conserva 16 documentos HTTP estables, prueba ambas topologías
y las negativas; http-fixture.json registra sus IDs. Repetición reutiliza documentos.
Promover el mismo código/imagen al servicio api existente solo con evidencia/CI/revisión;
no convertir el candidato en un microservicio permanente. Mantener F03 abierta hasta T007.
