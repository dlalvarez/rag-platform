# F04 T005 — intención, reconciliación y worker

R01..06; AC01..05. Dependencias: núcleos T002/T003 integrados y extractor T004
aceptado. Toda ejecución en ragdev01; conservar originales, fixtures y recursos.

## Entregas verificables

Primero implementar el journal y el despacho idempotente, con pruebas PostgreSQL
revertidas sobre las cuatro fixtures. Después conectar el worker y su runtime
limitado; activar migraciones y API compatibles de manera coordinada. Un PR de
componentes no acredita el worker ni cierra T002/T003/T005.

## Intención local

Crear versión PROCESSED e intención en la misma transacción tenant, bajo lock del
repositorio y documento, con membresía/ACL de escritura actuales. Identidad estable
por original y config_hash; repetir devuelve la misma versión/intención. Conservar
el actor inicial; otro actor no adopta el trabajo. No duplicar ni actualizar original.

Despachar desde intención a control mediante IDs solamente. El UUID de intención
es la clave idempotente de cola. Confirmar el despacho local después del enqueue;
una caída entre ambos pasos reenvía la misma identidad y recupera el mismo job.
La cola no concede acceso. Reconciliar solo tenants autorizados del catálogo;
ningún barrido transversal SQL, cada conexión resuelta por tenant.

## Claim, autorización y commit

Un trabajo simultáneo. Lease inicial acotado a 180 segundos, parser de 45 segundos
como máximo; heartbeat antes de etapas y durante espera si fuera necesario.
El token/intento de control y journal local deben coincidir. No revivir lease
caducado ni permitir que un proceso anterior sobrescriba un intento nuevo.

Revalidar usuario, membresía, tenant READY y referencias de secretos al entrar y
antes de confirmar. Extraer fuera de locks SQL. Mantener contexto nuevo después del
parseo, pues la prueba de autorización expira a los 30 segundos. No guardar tokens
de usuario en la cola. Runtime sin día/admin/migrator/root.

La finalización corta toma el lock del claim en control, vuelve a comprobar el reloj
de base, serializa las filas de autorización relevantes y toma repositorio/documento
en tenant. Revalida ACL y tombstone bajo esos locks. Insertar todos los bloques/chunks,
metadata, READY_FOR_EMBEDDING y auditoría en una transacción tenant. Comprobar fencing
y parada inmediatamente antes del commit. Ningún texto en control, logs o excepciones.

El commit tenant puede preceder al ack control: no hay ACID entre bases. Si el ack
falla o el proceso cae en esa frontera, otro claim observa el resultado canónico
completo y solo confirma el job. No vuelve a insertar bloques/chunks ni publicar.

## Fallos y parada

Código cerrado, retry/backoff solo ante dependencia recuperable. Parser inválido,
límites, cifrado, NEEDS_OCR o autorización revocada no generan datos inventados.
Original e historial permanecen. Un fallo de parseo no persiste bloques/chunks.
Una baja gana el lock antes del commit o espera al commit ya autorizado; si gana,
impide el resultado tardío. Lo mismo para ACL y estado del repositorio.

SIGTERM/SIGINT dejan de tomar trabajo. Terminar o abandonar sin commit de resultado
parcial; release/retry con fencing cuando sea posible, recuperación por lease si
muere el proceso. No matar infraestructura ni purgar fixtures.

## Puertas pendientes de aceptación

Pruebas offline y reales en ambas topologías: enqueue/ack perdido, repetición,
crash antes y después del commit tenant, dos procesos/lease/fencing, error a mitad
de parseo, baja/ACL/membresía durante trabajo, A→B→A, parada/reinicio, cuatro formatos
y NEEDS_OCR. Logins reales de roles limitados y canary SQL, capacidad/pools/temporales.
Activación persistente repetible y fallo DDL controlado con recuperación honesta del
catálogo. CI, revisión delegada del mismo agente y postmerge antes de aceptar.

No embeddings, PUBLISHED, cambio de current_version_id, F05, nuevos servicios de datos,
nuevos secretos administrativos ni ampliación de AppRole sin propuesta concreta.
