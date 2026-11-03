# T003 — contrato y esquema de asistentes

Diseño dentro del alcance F07-R01/R02, AC03/04. Aún no activa rutas ni adopta bases.

Cada asistente pertenece a un usuario lógico dentro de una base tenant. Su
configuración contiene nombre (1..120, NFC), propósito (0..2000), 1..16 repositorios
distintos, espacio de embeddings, fingerprint de un perfil generativo permitido
por servidor y top_k (1..8). El cliente no configura endpoints ni credenciales.
El propósito es dato del prompt y no sustituye la política obligatoria.

El propietario con rol tenant owner/admin/editor puede crear, actualizar o dar de
baja sus asistentes. Reader puede leer y usar uno propio; no editar configuración.
Un administrador tenant o plataforma no hereda contenido de otro propietario.
El servicio debe validar primero el contexto firmado y vigente, el estado ACTIVE
y cada ACL de repositorio. No basta con pasar owner_allows: esa función es una
condición adicional, nunca un sustituto de autenticación/autorización.

Un enlace no concede acceso. Al configurar y usar, se exige permiso actual sobre
todos los repositorios; se rechaza la operación entera ante uno inaccesible, sin
eliminarlo silenciosamente. El espacio debe coincidir con el perfil de recuperación.
El fingerprint generativo debe pertenecer al catálogo fijo del servidor.

Actualizaciones y bajas exigirán revisión positiva acotada (CAS); se incrementará
la revisión al cambiar configuración o estado. La baja es lógica. IDs, propietario
y creación no son editables. Se revalidará configuración/revisión después de inferir.

## Esquema congelado candidato

schema_f07_0007 construye metadata nueva desde la definición F05 congelada,
sin cambiar ninguna tabla previa. Añade assistant.assistants, repository_links y
audit_events. FK solo locales, RESTRICT para conservar registros; propietario y
actor son UUID lógicos sin FK a control. Las auditorías guardan identificadores,
acción y fecha, sin propósito, pregunta, respuesta o documentos.

El esquema impone estado, fingerprint, top_k, revisión, tamaños y relaciones
asistente/espacio/repositorio. El servicio impondrá normalización, límite del
conjunto de enlaces, catálogo de perfiles, CAS y todas las ACL. La metadata no
demuestra autorización por sí sola.

Esta entrega no registra revisión Alembic, perfil de autoridad, privilegios,
migrador, API ni almacenamiento de conversaciones. El head persistente sigue
f05_tenant_0006. No aceptar un head desconocido o relajar las verificaciones de
F03..F06 para acomodar este diseño. La migración y compatibilidad requerirán
pruebas reales de roles/TLS/rollback en ambas topologías antes de adopción.

## Integración pendiente

CRUD transaccional, paginación ligada a actor/tenant, permisos actuales y
auditoría atómica. Concurrencia de revisión y denegación ante cambios de ACL.
Roles de lectura deben conservar sus garantías previas: el contexto reader usa
credencial SQL readonly, por lo que persistir un turno de chat necesita un camino
de escritura limitado y probado. No convertir ese contexto en credencial app
ni concederle escritura documental como atajo. Resolver este diseño antes del
pipeline persistente y su adopción. No afecta al contrato puro de esta entrega.

Pruebas offline de metadata comprueban DDL previo idéntico, FK locales, límites
y aislamiento entre instancias. No sustituyen ejecución PostgreSQL, rollback,
privilegios ni pruebas API.
