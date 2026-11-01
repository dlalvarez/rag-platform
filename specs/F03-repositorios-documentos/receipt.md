# Recepción documental T005

Componente de F03-R03/R04; controles ACL de R02 y secretos de R05.
Desarrolla V03/V04/V06 y parte de V01/V02/V07. Los AC de HTTP siguen abiertos hasta
T006/T007: esta entrega no despliega la API documental ni acredita su proxy.

## Entrada y límites

El adaptador debe autorizar tenant/repositorio antes de leer el cuerpo. ReceiptService
vuelve a comprobar autoridad, membresía, versión y ACL antes de SQL/S3 y entre etapas.
La identidad de datos solo lee las referencias exactas/versionadas del AppRole F03.
El bearer diario permanece en la herramienta de operación; nunca cruza a los hijos
de datos. Cada hijo recibe por IPC privado un bearer de aplicación verificado, con
TTL máximo de una hora; el padre lo revoca también si el hijo termina abruptamente.

UploadSpool usa un archivo temporal privado sin nombre del cliente en la ruta;
cierre de contexto elimina el temporal. Procesa bloques de 64 KiB y calcula SHA-256
más MD5 de transporte. Máximo por archivo 10 MiB, configurable hacia abajo; cuota
tenant inicial 100 MiB y 10 000 recibos, configurables con cotas explícitas.
T006 deberá limitar concurrencia y espacio temporal antes de exponer HTTP.

Formatos: TXT/Markdown UTF-8 estricto sin controles binarios; PDF con cabecera/EOF
estructurales; DOCX ZIP con partes mínimas, CRC, límites de expansión y rechazo de
macros, cifrado, enlaces y rutas peligrosas. Extensión y MIME deben coincidir.
El preflight ZIP limita el directorio antes de que ZipFile asigne sus entradas,
incluyendo recuento real frente a un EOCD falseado. No extrae texto ni ejecuta archivos.
Validación estructural PDF no equivale a comprobar la semántica completa del PDF.
Después de cualquier error el spool queda invalidado.

## Diario, objetos y recuperación

Idempotency-Key ASCII de 16..128 caracteres, única por actor/repositorio.
La huella incluye actor, repositorio, nombre, MIME, tamaño y SHA-256.
La misma petición devuelve documento/versión originales; una huella distinta devuelve
409. Un intento con lease vigente devuelve OPERATION_IN_PROGRESS (409).

1. Bajo advisory lock tenant y locks de fila, reservar cuota/IDs en PENDING.
2. Crear original privado con If-None-Match: *, checksum y metadatos de propiedad.
3. Verificar tamaño/MIME/hash/propiedad y registrar OBJECT_STORED.
4. Verificar otra vez el objeto; confirmar fuente, documento, versión RECEIVED,
   auditoría y recibo COMMITTED en una sola transacción SQL.

El original tiene clave generada con UUID de repositorio/versión; el nombre de
archivo no determina rutas. No hay URL pública ni presignada. El adaptador usa la
extensión privada _url_open del SDK MinIO 7.2.20 fijado: firma condicional real,
Content-Length y cuerpo acotado. Requiere sus tests de transporte y prueba real al
actualizar esa dependencia. No hace retry automático de PUT.

Tras un rechazo temprano de PUT se cierra/libera su respuesta y se descarta el pool
de esa operación antes de reutilizar conexión para HEAD. No se aceptan transport
errors como si fueran el 412 esperado. Una colisión solo es reutilizable si todos
los marcadores de propiedad, tamaño, MIME y ETag/checksum coinciden.

Una interrupción conserva reserva y posible objeto; después de caducar el lease,
otro intento retoma los mismos IDs con un attempt_id nuevo. El intento antiguo queda
fenced y no puede confirmar SQL. Una respuesta perdida tras COMMIT se resuelve con
replay. Un fallo SQL revierte fuente/documento/versión/auditoría conjuntamente;
el diario y original permiten recuperación hacia delante.

La cuota cuenta todos los estados, incluso recepciones pendientes/fallidas y repos
dados de baja. No liberar cuota por un HEAD ausente: un PUT de resultado incierto
podría terminar después. Esta compensación conserva el intento durable y revierte
los cambios SQL incompletos; no borra originales ni aparenta transacción distribuida.
Una colisión ajena queda conservada y bloqueada para revisión, sin adopción.
La pérdida de un original ya COMMITTED falla de forma cerrada, sin reparación silenciosa.
No hay purge, restauración, borrado físico ni transición a PUBLISHED/READY documental.

## Reproducir en ragdev01

Herramienta de confianza, sesión diaria vigente y fixtures F03 de T003/T004:
reconstruir isolation-check con ops/f02/compose.yaml y .env.f02 de operación.
Ejecutar dentro de esa herramienta scripts/f03_conditional_check.py y
scripts/f03_receipt_check.py. No copiar archivos privados ni salidas de secretos.

La primera prueba reutiliza cuatro documentos estables (conditional-fixture.json),
verifica 412 real, original intacto y replay idéntico. La segunda conserva un conjunto
nuevo de fixtures diminutas por ejecución; receipt-fixture.json identifica la última
batería completa. Los intentos fallidos anteriores se conservan también.
Los hijos usan spawn, handshake antes de medir operaciones y leases realmente
caducados, sin modificar relojes ni expirar filas manualmente.

La batería comprueba formatos/hash por GET privado, inválidos/ACL/cuota sin altas,
S3 cruzado/anónimo, caída real con os._exit después de PUT y COMMIT, concurrencia,
fencing, error SQL real dentro del commit y recuperación, cuota entre repositorios
y colisión con marcadores ajenos conservada. Compara el catálogo previo ajeno a F03.
Los tests offline cubren además ZIP bombs, metadata falseada y ausencia de efectos
después de perder autoridad o faltar el original. Ver evidence.md para resultados.

Pendientes de T006/T007: handoff privado del runtime, límites HTTP/temporales,
rutas y errores v1, proxy y cabeceras seguras, aislamiento API y regresiones finales.
Sin nuevas migraciones, roles administrativos, puertos, dependencias ni servicios.
