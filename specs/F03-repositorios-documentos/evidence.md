# Evidencia F03

Estado: planificación activa, implementación y aceptación pendientes.
Base inspeccionada en ragdev01: develop@81e213c0682ec1766358b29328e52df968c4d8ea,
checkout limpio, F02 cerrada y postmerge comprobado en PR #26.

Diego reiteró continuidad autónoma entre tareas/fases el 2026-11-01 y pidió guardarla.
AGENTS/ADR-0010/gobierno/guía activa registran esa instrucción; no es inferencia del agente.
Leídos Constitución, arquitectura, tenancy, roadmap, contrato API y spec F03.
La carpeta solo contenía spec; se prepararon plan/tasks/checklist/evidence.

No se implementó F03, aplicó migración, desplegó servicio ni modificó política de
secretos mediante esta entrega documental. R/AC/V pendientes; no declarar éxito por
documentos. CI/revisión/postmerge del PR se registran en su conversación.
El acceso de aplicación a secretos se debe comprobar/preparar sin montar el bearer
infra diario en el runtime. Un bloqueo real de bootstrap no bloquea módulos independientes.

## T001 integrado y preparación T002 — 2026-11-01

PR #27 integrado en develop@8530739dbc2cf5a067c5f67c6cc963ea2cc12d76.
Docs/lint/tests exactos y postmerge correctos; checkout limpio verificado.
La instrucción de continuidad queda persistida; se inició T002 sin esperar otra orden.

capabilities-self real de la sesión diaria: deny para policy y role administrativos F03.
No se alteró esa limitación ni se montó el bearer de infraestructura en una API.
Preparados adaptador read-only, policy exacta de 12 refs, AppRole de 1 hora/SecretID
de un uso, bootstrap administrativo fijo y host con restauración/fuentes verificadas.
[Runbook y límites](../../ops/f03/README.md).

Cuatro fixtures F03 nuevas READY en las dos topologías, con namespace idempotente
propio; todas siguen con versión F01, todavía sin esquema documental. Snapshot de
tablas del catálogo anterior igual antes/después y reintento sin rotación.
La primera envoltura de ejecución no cargó módulos y la segunda falló al exportar
JSON después de provisionar; se corrigió la envoltura, se repitió idempotentemente y
se validó el resultado. No se ocultó ni declaró PASS de esos intentos fallidos.

Validación en ragdev01: 333 tests offline correctos, ruff check/format y check_docs.
Advertencia Starlette/httpx ya registrada en F02, sin fallo funcional.
80 pruebas focalizadas de acceso/secretos/daily correctas.
Imagen de herramientas construida con uv --frozen; hash de fuentes/scope del bridge
coincide con checkout. Sin dependencias nuevas ni ejecución de código local en Mac.

Prueba TLS contra OpenBao 2.7.2 vacío, red interna exclusiva, inmem y sin puertos:
dos recuperaciones reales/roots revocados, bootstrap repetible sin alterar roles
anteriores, 12 refs exactas/versionadas, SecretID de un uso, infra/list/write/delete/
admin/create-token denegados y token revocado sin fallback. Contenedores/red propios
retirados. Sin claves del operador ni acceso al OpenBao activo durante esta prueba.

T002 parcial: falta ejecutar bootstrap en el servicio existente, verificar emisión
con el día vigente y conectar runtime autorizado/versionado. No aplicadas migraciones
tenant F03, no desplegada API documental, no AC-F03 acreditado ni F03 cerrada.
Mientras esa acción externa esté pendiente, continuar T003 y módulos independientes.
CI/revisión/postmerge de esta preparación se registran en el PR, no se presuponen.

## Bootstrap real y esquema T003 — 2026-11-01

Diego ejecutó el procedimiento del PR #28 y comunicó ambos PASS F03 APP SETUP.
Verificación autónoma posterior: 12 refs exactas/versionadas, SQL app/readonly en
destinos propios con TLS; admin SQL/migrator/canary denegados, SecretID de un uso,
token de ensayo revocado y sesión diaria conservada. PR #29 añadió exclusión con
baterías diarias; CI/revisión/postmerge correctos en d10a8d318f4b74c5a184e4acf75289fd1c235d03.
No se necesita repetir bootstrap ni pedir otra contraseña para las pruebas.

T003 añade f03_tenant_0002 solo a las cuatro fixtures F03 propias. [Esquema y permisos](schema.md).
Fábrica DDL histórica independiente del metadata runtime; F01 fijada a su versión
explícita para no migrar fixtures anteriores al head nuevo. Resolver/authority/queries
aceptan solo perfiles conocidos y contextos separados, con defaults F01/F02 conservados.

Batería real final SAME_A/SAME_B/TWO_A/TWO_B correcta: versión física/repetición,
constraints de nombre/config/MIME/tamaño/hash, pertenencia source/doc/versión/recibo,
unicidad actor/repo/key, grants mínimos, readonly sin escritura/DDL, migración DDL
fallida revertida, FAILED sin versión falsa y recuperación, lock real entre procesos.
DDL histórico reproducido fresco en schemas temporales propios y revertido sin DROP;
schemas ausentes y versión intacta comprobados. Todos los documentos/recibos de probes
SQL revertidos; sin archivos u objetos ficticios persistentes. Catálogo ajeno intacto.

Primer intento de la batería falló sin PASS; se aislaron fases. El probe de lock
confundía importación del hijo (spawn bajo límite CPU) con el tiempo de contención.
Se añadió handshake antes de medir la respuesta; lock_timeout SQL permanece 5 s.
Los cuatro casos finales demuestran MIGRATION_BUSY real, no un timeout genérico aceptado.

351 tests offline, ruff check/format, check_docs y diff check correctos en ragdev01.
Regresión real F02 T006 en ambas topologías correcta: OIDC A/B/A, SQL/S3 y cruces,
IDOR/estados con cero accesos antes de autoridad. LOG_FLAGS forbidden_value=false,
jwt_pattern=false, traceback=false; fixtures F01/F02/F03 conservadas.
La congelación posterior del factory solo cambia construcción de metadata/replay;
se volvió a ejecutar la batería F03 completa y los tests sobre las fuentes finales.

No API documental desplegada, ACL CRUD o carga/proxy acreditados todavía.
T002 sigue pendiente de handoff/runtime; T003 pendiente de CI/revisión/integración
de este PR; T004 continúa sin nueva confirmación. F03 permanece abierta.

## T003 integrado y componente T004 — 2026-11-01

PR #30 integrado en develop@abae0e6d91b8c02e34816be00393ad1d437b2855,
con CI/revisión/postmerge correctos. Se inició T004 sin nueva confirmación.

[Perfil ACL](acl.md): CRUD tenant-local, control por capacidad y techo de membresía,
denegación por defecto, owner/admin/editor/reader, cambios de ACL serializados,
último owner activo/owner_id consistente y baja lógica con historial.
Listados/cursor HMAC actor/tenant/colección, nombres/config acotados, errores cerrados
y auditoría transaccional tenant para cambios. No endpoint HTTP nuevo en esta entrega.

T004 real correcto, repetido sobre ambas topologías/cuatro fixtures. OIDC real para
Alice/Bob/Carol/Dave, altas de perfil ORG/membresías explícitas solo en fixtures F03,
identidad AppRole limitada para datos. Sin acceso de operador/owner tenant a repo sin
ACL. Editor/reader sin administración, escalado y modificación de owner por admin
denegados, target limitado por membresía, último owner protegido, transferencia y
pérdida inmediata de acceso, owner_id reconciliado.
Cursores ajenos entre actor/tenant rechazados antes de secretos; UUID repo cruzado
denegado en destino propio. Suspensión de membresía existente rechazada exactamente
como MEMBERSHIP_REQUIRED, sin lecturas de secretos tenant.
Baja lógica conserva fila/ACL/auditoría; no se creó documento por CRUD.

Segunda ejecución reutilizó los mismos tres repos semilla por fixture. IDs en
ops/f03/repositories-fixture.json; solo referencias lógicas sintéticas.
Repos temporales de probes quedan DELETED, con historial. Hashes de catálogo,
usuarios/roles y membresías/perfiles ajenos a los cuatro tenants iguales antes/después.
No rotación de credenciales, IAM admin de S3 ni bearer infra en componente de datos.

Regresión T003 completa con datos CRUD presentes correcta en las cuatro fixtures:
DDL fresco revertido, constraints, roles, FAILED/reintento y locks. Probes ahora
parten de conteo previo y nombres únicos para no asumir ausencia de documentos futuros.
415 tests offline correctos (64 nuevos de política/metadatos/cursor), lint/format/docs/
diff correctos en ragdev01. Advertencia Starlette/httpx previa sin fallo funcional.

T004 componente pendiente de CI/revisión/integración de este PR. AC de API/carga/proxy
siguen pendientes; no F03 cerrada. Continuar T005 sin pausa de trámite, mantener
handoff/runtime de T002 como puerta antes del despliegue T006.

## T004 integrado y recepción T005 — 2026-11-01

PR #31 integrado en develop@ea4554fb70425b3df61d9198aeb907e1216fec82,
con CI/revisión del mismo agente y postmerge correctos. Se continuó T005.

[Recepción y límites](receipt.md): F03-R03/R04, ACL de R02 y secreto mínimo;
V03/V04/V06 y parte de V01/V02/V07. No nuevas migraciones ni despliegue HTTP.
Validación privada/acotada, firma condicional real, diario, cuota tenant, lease/fencing
y recuperación hacia delante sin borrar objetos.

Prueba condicional completa y repetida correcta en SAME_A/SAME_B/TWO_A/TWO_B:
HTTP 412 exacto, ETag/LastModified intactos, replay con mismos documento/versión y
conflicto ante contenido diferente con igual clave. Los cuatro UUID lógicos estables
se conservan en ops/f03/conditional-fixture.json.

Se observaron fallos intermitentes DEPENDENCY_UNAVAILABLE/REFUSED en el HEAD posterior
al PUT rechazado. Aislamiento por etapa: el rechazo esperado sí era 412. Una primera
sonda de 12 secuencias no reprodujo el fallo; no se atribuye una causa única.
Se corrigió el ciclo de vida: cerrar/liberar respuesta y descartar el pool de esa
operación tras S3Error, sin retry de PUT. Test de transporte fija ese comportamiento.
La prueba completa posterior y su repetición pasaron. No se aceptó un error de
transporte como denegación de seguridad ni se reescribió/borró un original.

Batería real final T005 completa correcta en las cuatro fixtures/ambas topologías:
- TXT/MD/PDF/DOCX estructurales; GET privado con bytes/SHA-256 correctos y replay estable.
- Inválidos/límite, reader/sin ACL/UUID de otro tenant y cuota: denegados sin altas.
- Credencial S3 propia contra bucket ajeno y acceso anónimo: AccessDenied exacto.
- Caída real de proceso con os._exit después de PUT y después de COMMIT; mismo par
  de IDs, sin RECEIVED prematuro y exactamente una fuente/documento/versión al recuperar.
- Dos procesos: lease vigente rechaza segundo intento; lease realmente caducado
  permite takeover y el attempt_id antiguo no confirma. Sin expirar filas manualmente.
- Error SQL real (división por cero dentro del commit): rollback de fuente/documento/
  versión; OBJECT_STORED conservado y recuperación con los mismos IDs.
- Reserva de cuota en un repositorio impide otra en el segundo; suma final exacta.
- Objeto canario con propiedad ajena a la recepción: conflicto inicial y al reintentar;
  ETag, LastModified, metadatos de propiedad y SHA-256 intactos. Reserva y objeto retenidos.
- Catálogo ajeno a las fixtures F03 idéntico antes/después. Bearers hijos solo de
  aplicación, verificados en OpenBao y revocados por el padre también tras caída.

Los intentos iniciales no se presentan como PASS completo: se corrigieron una fixture
DOCX sin parte rels, el tipo Decimal de SUM(bigint) en el driver de cuota y una comparación
de metadatos que incluía Date/request-id variables. Diagnóstico independiente del canario:
body_hash_intact=true, etag_intact=true y foreign_marker_retained=true; no pérdida de datos.
Se conservan todos los recursos válidos y reservas de esas ejecuciones.
ops/f03/receipt-fixture.json registra run y los 16 documentos de formatos de la última
batería completa; el diario durable conserva los restantes casos asociados a ese run.

512 tests offline correctos en ragdev01, incluidos 21 de límites fail-closed de recepción.
Ruff check/format, check_docs y diff check correctos. Advertencia previa Starlette/httpx
sin fallo. Sin nuevas dependencias, privilegios administrativos de aplicación, puertos
o servicios. Herramienta observada cerca de 112 MiB/768 MiB; servicios previos activos.
No se solicitó contraseña ni se renovó/revocó la sesión diaria.

Componente T005 preparado; CI/revisión/integración/postmerge del PR pendientes.
T002 handoff/runtime y T006/T007 siguen abiertos; ningún AC HTTP ni cierre F03 acreditado.

Cierre de comprobaciones del componente: otras 12 secuencias 412→HEAD correctas tras
la corrección, en las cuatro fixtures. Regresión real T004 completa también correcta
con los documentos recibidos: mismos repos semilla, ACL, membresías e historial intactos.


## T005 postmerge y T002/T006 candidata — 2026-11-01

PR #32 integrado en develop@752036e2533f96e54deedbd6d782818a583e3460.
Cuatro checks del head y tres del merge correctos, revisión delegada y dos checkouts
limpios por fast-forward; postmerge real 44 recibos: 40 COMMITTED/40 documentos y
cuatro PENDING de colisiones sintéticas, conservados.
[Registro posterior](https://github.com/dlalvarez/rag-platform/pull/32#issuecomment-6562724783).
Diego reiteró no detenerse al cerrar PR; AGENTS/NEXT refuerzan esa instrucción y se
continuó con T002/T006 sin pedir otra autorización ni contraseña.

[Perfil y límites T002/T006](api.md). No cambios de esquema, grants, roles admin,
dependencias o puertos. Misma API F02 extendida; candidato efímero de prueba separado
solo durante ensayo, sin alias api ni exposición LAN; instancia anterior conservada.
Composición comprobada: siete bind mounts read-only de CA/TLS/control app/authority/
handoff, sin día, migrator, SQL/MinIO admin ni secretos IdP. API 512 MiB/0.25 CPU,
un worker, root read-only y tmpfs privado noexec 64 MiB.

Handoff real correcto: entrega 0600 en tmpfs 0700, consumidor único, 12 refs exactas/
versionadas; ensure reutiliza sin rotación. Reemplazo atómico instala bearer de
aplicación verificado y revoca el anterior; archivo ausente/token revocado bloquean
acceso incluso con pool caliente. Día validado/conservado. Emisor efímero monta solo
día/handoff/CA, sin SQL/IAM/IdP admin. Material del probe revocado y retirado de tmpfs.
No se renovó la sesión diaria ni se automatizó desbloqueo/recuperación administrativa.

API candidata: dos baterías HTTPS completas correctas, cuatro fixtures y ambas
topologías. CRUD/baja lógica/ACL, editor sin promoción a owner, retirada de ACL con
pérdida de acceso; cuatro formatos y replay iguales; distinto cuerpo con key igual
409; original para reader con bytes/hash/cabeceras correctos y rol readonly sin ops.
Sin ACL y anónimo denegados; repo de otro tenant denegado; inválidos y cuerpo chunked
de más de 10 MiB rechazados sin altas de recibo/fuente/documento/versión.
Paginación sin duplicados y cursor de Alice rechazado por Bob.

Las 16 referencias lógicas en ops/f03/http-fixture.json son estables entre ambas
ejecuciones; se conservan documentos/repositorios/historial de los probes anteriores.
Segunda batería comparó hashes de catálogo y usuarios/roles/membresías/perfiles ajenos
a los cuatro tenants: iguales antes/después. Entrega ausente y bearer revocado
devolvieron 503 con pools calientes; reemplazo diario limitado recuperó acceso,
sin fallback ni cambios en el día.

562 tests offline correctos, incluidos límites HTTP/concurrencia, spool/hash,
corrupción/truncado del original, pérdida de permiso y desconexión. Ruff check/format,
check_docs y diff check correctos. Advertencia Starlette/httpx previa sin fallo.
Postensayo: 0 descriptores temporales en /tmp del proceso API; permisos privados y
tamaño tmpfs 67 108 864 bytes. Inspección interna de logs: token de aplicación=false,
patrón JWT=false, cuerpo documental=false, traceback=false. No logs brutos publicados.

Primer lanzador desde worktree falló por buscar .env.f02 allí; se añadió --f02-env
explícito, usando la configuración operativa sin copiar secretos, y ensure repetido
correcto. Ajustes de drivers previos a HTTP: perfil Compose explícito para validar
configuración, tipo normalizado de mem_limit y PYTHONPATH de herramientas al montar
el script de prueba. No se presentan como fallos del flujo funcional ni como PASS.
La API candidata mantiene exactamente las fuentes de runtime probadas.

Pendientes: CI/revisión/integración del PR T002/T006, promoción controlada de esa
imagen al servicio API existente y validación posterior. Seguir T007 con observadores,
negativas adicionales y regresiones. F03 permanece abierta; sin iniciar F04.


## T002/T006 integrado y cierre T007 — 2026-11-01

PR #33 integrado en develop@be7643847f6e472ae9b1b5d3011d83d3f75b3260.
Cuatro checks del head y tres del merge correctos, revisión delegada sobre head exacto.
[Postmerge y promoción](https://github.com/dlalvarez/rag-platform/pull/33#issuecomment-6564409178).
Candidato efímero cerrado; bearer reemplazado con día vigente y solo servicio api
recreado con la misma Image ID. Sin reinicios de PostgreSQL/MinIO/OpenBao, puertos
nuevos, contraseña del operador ni cambio de visibilidad. La API normal F03 está activa.

T007 HTTPS sobre api correcto, cuatro fixtures/ambas topologías: mismo conjunto de
16 documentos y versiones, CRUD/ACL, último owner 409, listado sin enumerar repo
sin ACL, documento ajeno 404 antes de S3, negativos de archivo/tamaño con conteos
SQL y objetos S3 iguales antes/después. A→B→A verifica documento/versión/original
propios tanto en instancia compartida como en dos instancias.
Bearer ausente/revocado devuelve 503 con pool caliente y reemplazo recupera acceso.

Observadores reales correctos: cuatro fixtures, positivos instrumentados comprueban
lecturas reales de secretos/S3/spool. JWT ausente, tenant sin membresía, reader en
carga y cursor de otro actor dejan los tres contadores en cero. La comprobación
de ACL/doc ajeno usa SQL tenant pero no S3 ni spool, aun con pool caliente.
No endpoint de debug ni cambios a la identidad de la API activa.
El primer probe se detuvo antes de los casos; al incorporar el manifiesto HTTP
generado a la imagen de herramientas y reconstruir, batería completa correcta.
Material privado del probe revocado y retirado de tmpfs; recursos de datos conservados.

Aislamiento directo F03 correcto: app/readonly con base/usuario/TLS propios y
rolsuper/rolcreatedb/rolcreaterole/rolbypassrls false. Readonly UPDATE denegado 42501;
SET ROLE cruzado denegado 42501 en instancia compartida. CONNECT entre bases/instancias
rechazado por la causa precisa de permisos/autenticación; no se aceptó un fallo TLS
genérico como aislamiento. Ambas direcciones en ambas topologías.
GET propio correcto; GET/HEAD cruzados y anónimos AccessDenied HTTP 403 en las cuatro
fixtures. No lectura de contenido cruzado, cambios de permisos o borrados.

Baja lógica con contenido real de prueba correcta en las cuatro fixtures:
repo DELETED y API deniega metadata/original; documento, versión, fuente, recibo
COMMITTED, objeto con ETag/LastModified/metadatos intactos, ACL y auditoría conservados.
ops/f03/lifecycle-fixture.json registra esos cuatro repos/documentos retenidos.

Concurrencia HTTPS real correcta: dos solicitudes con misma clave, una recepción
final/replay estable; SQL suma exactamente una fuente/documento/versión/recibo y un
DOCUMENT_RECEIVED. Cuatro originales adicionales retenidos, IDs en
ops/f03/http-race-fixture.json. La clave distinta por ejecución permite reproducir
el caso sin borrar historial. DOCX expansivo construido desde un DOCX válido con sus
partes completas rechazado 422 en cada fixture: filas y objetos idénticos antes/después.
No atribuir este resultado solo a partes ausentes de un ZIP inválido.

Regresiones reales correctas:
- F00: constitución ausente, assertion fallida e import sin uso rechazados con exit 1,
  únicamente en copias temporales; gates activos.
- F01: imagen de herramientas reconstruida desde fuentes actuales; CLI diaria sin
  password, create/fallo/retry/check/migrate en ambas instancias, sin rotación o
  duplicados. Perfil identity/f01_tenant_0001 conservado. Nuevas fixtures sintéticas
  propias de la regresión retenidas; no se confunden con mutaciones ajenas de F03.
- F02 T006: OIDC A/B/A, SQL/S3 y cruces, IDOR/estados antes de secretos/conexiones/
  queries/S3, ambas topologías. LOG_FLAGS forbidden_value=false, jwt_pattern=false,
  traceback=false; datos F01 conservados.
- F03 T003 con documentos presentes: cuatro fixtures, versión física/repetición,
  DDL histórico fresco revertido, constraints/grants, fallo DDL revertido, FAILED sin
  versión falsa/recuperación y locks entre procesos correctos. Sin probes persistentes
  ni pérdida de contenido. Todas las baterías se ejecutaron en serie.

Inspección de la API normal después de los ensayos: sin JWT, credenciales/subjects IdP,
token de aplicación ni su familia, referencias/nombres físicos, contenido o trazas.
No se publicaron logs brutos. Cero descriptores temporales; /tmp 0700 y 64 MiB.
Se amplió el inspector F02 mediante parámetros opcionales para reutilizar el mismo
control con el material F03, manteniendo la llamada F02 sin argumentos compatible.

[Tabla R/AC/V, reproducción y límites](acceptance.md). Runtime idéntico a #33;
esta entrega T007 solo añade validación y documentación. 562 tests offline y
ruff/check_docs/diff correctos; falta CI/revisión/merge/postmerge del PR de cierre.
Después continuar F04 según ADR-0010, presentando únicamente las decisiones técnicas
reales pendientes antes del código que dependa de ellas.
