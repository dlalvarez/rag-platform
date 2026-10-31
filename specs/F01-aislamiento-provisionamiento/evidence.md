# Evidencia F01 — T001–T005 aceptadas; T006 en validación

**Estado:** T001 aceptada, con checks del HEAD y postmerge correctos, integrada
mediante PR #9 en develop@a1568375164627f4be2b10d0cb9285fab92ce685.
T002/T003 aceptadas e integradas mediante PR #10/#11; T004 en validación.
F01 e Issue #7 permanecen abiertos. Ningún AC-F01-01..07 completo.

Plan ratificado: [PR #8](https://github.com/dlalvarez/rag-platform/pull/8),
develop@f2c74400d2cafb5fce065b6eb0db23243731f8cf.
Implementación: [PR #9](https://github.com/dlalvarez/rag-platform/pull/9),
rama feat/F01-T001-control-secrets. Código ejecutado en las últimas pruebas:
4c6458d25d16b6fc38a22def28df6e7073251a0f.
[Log](../../docs/evidence/f01-t001-2026-10-30.txt),
[runbook](../../ops/f01/README.md).

## Trazabilidad y resultados

F01-R01/R03 → AC-F01-01/06 parciales → P1 → T001 → V01/V03.
Los resultados limitados a T001 no acreditan provisionador ni resolver futuros.

| Prueba | Resultado | Fuente |
|---|---|---|
| V01 catálogo/control | Alembic fijo aplicado/repetido en PostgreSQL real, migrador no-superuser, constraints y rechazo de password/CA erróneas y TCP sin TLS | scripts/f01_control_check.py; log |
| Contrato tenant | UUID/ref/versión y nombres derivados validados; app/migrator separados en contrato | tests/unit/f01/test_catalog.py |
| V03 bootstrap | Diego reportó PASS de operador limitado, AppRole sin root, SecretID de un uso, KV versionado/CAS y root inicial revocado | salida saneada del operador; scripts/f01_operator.py |
| V03 sellado | Restart solo OpenBao: antes initialized=true/sealed=false; después initialized=true/sealed=true. Token ficticio: HTTP 503 | comprobación TLS independiente; log |
| V03 persistencia | Diego desbloqueó y ejecutó check: PASS. Check exige canary existente versión 1; no puede recrearlo | salida del operador; test negativo de canary ausente |
| V03 caducidad real | Lectura previa correcta, TTL de sesión concedido 2s, espera 4s, token caducado rechazado HTTP 403 con nodo desbloqueado | check-expiry ejecutado por Diego; log |
| V03 token inválido | Nodo initialized=true/sealed=false; token ficticio rechazado HTTP 403, sin imprimir cuerpo | comprobación TLS independiente |
| Errores/sin fallback | UUID/versiones, CAS, sesión expirada, denegación, redirección/timeout, errores sin valores; check no pide password sellado | tests/unit/f01 |
| Regresión | 53 pruebas offline, Ruff/formato/documentos correctos; F00 API/SQL/vector/S3 correcto y tres servicios saludables | log; suite sin red externa |

La expiración se demuestra ante el servicio real, no adelantando un reloj local.
Check-expiry revoca únicamente la sesión del operador, nunca el token AppRole que
debe caducar. Solicita renew-self con incremento 2s y usa el TTL realmente devuelto;
no modifica roles, políticas o credenciales persistidas.
Check posterior al reinicio no puede crear un canary perdido ni ocultar esa pérdida.
Las pruebas sensibles las ejecutó Diego en su terminal. Codex verificó estado/salud
y rechazos con token ficticio; no recibió valores.

## Aceptación de la fase pendiente

| AC | Cobertura hasta T002 | Pendiente para F01 |
|---|---|---|
| AC-F01-01 | Control y A/B distintos, contrato/migración inicial | Batería ampliada T006 y aceptación |
| AC-F01-02 | SQL A↔B y roles reales, PASS en T002 | Batería ampliada T006 y aceptación |
| AC-F01-03 | MinIO F01 A/B privados y cruces/anónimo, PASS T003 | Batería ampliada T006 y aceptación |
| AC-F01-04 | Constraints y repetición SQL/S3 sin rotación | Saga/reintento/concurrencia completos |
| AC-F01-05 | Sin saga de objetos | Fallo bucket, no READY y recuperación |
| AC-F01-06 | SecretStore/refs probados | Resolver, pools y dos endpoints reales |
| AC-F01-07 | Control y contrato tenant inicial repetibles | Locks, fallos y coordinación de migraciones T006 |

T001–T003 aceptadas; T004 en validación; T005–T007 no implementadas. No users/memberships/jobs, OIDC/F02, alta HTTP,
documentos, chunks, embeddings de negocio, RAG o chat.

## CI, revisión y límites

T001: 53 pruebas ejecutadas en ragdev01. Docs/lint/tests del HEAD aprobado y
postmerge correctos; [registro de cierre](https://github.com/dlalvarez/rag-platform/pull/9#issuecomment-6530152704).
Para cada PR posterior se comprueba su propio HEAD, sin extrapolar este resultado.

Advertencia preexistente Starlette/httpx conservada. Constitución, roadmap, ADR-0001,
requisitos/AC y fuentes runtime F00 preservados. Dependencias fijadas con hashes, sin
upgrades ajenos. Main y visibilidad pública sin cambios.

Raft de un nodo no aporta HA; backup externo/restore no acreditados. CA de desarrollo
de 90 días requiere renovación. SQL bootstrap separado del runtime.
Riesgo MinIO upstream archivado conservado; MinIO F01 incorporado en T003.
Rollback conserva PostgreSQL/Raft; sin downgrade destructivo automático.

La puerta de T001 ya se satisfizo. Siguiente puerta: integración real, CI y
revisión del PR T002; no merge automático.


## T002 — F01-R02 / AC-F01-01/02 parciales / P2 / V01-V02

Código: provisioning/postgres, credentials y migrations; control 0002/0003,
tenant 0001, scripts/f01_sql_check.py. [Manual](../../ops/f01/T002.md).

Resultados ejecutados en ragdev01:
- 84 pruebas offline correctas; Ruff y formato correctos.
- Documentos SDD y pruebas negativas F00 correctos.
- Imagen tools T002 construida con lock e imágenes fijadas, sin dependencias nuevas.
- Control-check real: PostgreSQL/TLS, constraints y migración 0003 aplicada/repetida, PASS.
- Regresión RESERVE real: ubicación válida con verify-full insertada/revertida, PASS.
- HBA F01: cero errores de sintaxis, recarga aceptada, sin reinicio de servicios.
- Regresión F00 real: API, PostgreSQL/vector y roundtrip S3 sintético, PASS.

Estado actualizado: sql-check real completado por Diego tras las correcciones
documentadas abajo. Ver cierre técnico T002 al final. Las entradas pendientes de
las subsecciones de diagnóstico son históricas, anteriores al ensayo completo.
CI se comprueba por HEAD en PR #10; revisión humana pendiente. AC de fase y casilla
T002 siguen abiertos hasta las puertas de aceptación correspondientes.


### Corrección de RESERVE

Diego reportó dos fallos RESERVE en la primera integración. Diagnóstico aislado con
rollback, sin autenticación OpenBao ni lectura de secretos del proveedor:
SQLAlchemy DataError, SQLSTATE 22001. La columna ssl_mode de la revisión inicial
era VARCHAR(10), insuficiente para verify-full (11 caracteres). SQLite no limita
VARCHAR(n), por eso las pruebas offline anteriores no detectaron el problema.

La revisión control 0003 amplía esa columna sin modificar revisiones históricas,
requisitos TLS ni valores existentes. El probe real ahora inserta una ubicación válida
y la revierte en SAVEPOINT; este caso pasó después de migrar y repetir el upgrade.
El comando administrativo informa SQLSTATE también para errores encapsulados por
SQLAlchemy, sin mostrar SQL, parámetros o mensajes del servidor.

72 pruebas offline correctas y control-check real PASS. Imagen tools reconstruida.
La integración completa SQL A/B sigue pendiente de repetir por el operador;
esta corrección no acredita su éxito ni cierra T002.


### Diagnóstico previo a SQL

Tras corregir RESERVE, Diego reportó una detención START. No se atribuye una causa
sin evidencia. Consulta independiente de status: initialized=true, sealed=false.
El comando ahora conserva códigos cerrados de OperatorFailure y distingue BAO_STATUS,
OPERATOR_LOGIN, OPERATOR_POLICY, APPROLE_ISSUE y APPROLE_LOGIN. No muestra cuerpos
HTTP ni contraseñas. Dos pruebas offline verifican diagnóstico de sellado y autenticación.
74 pruebas offline correctas; imagen reconstruida. Pendiente repetir integración.


### Corrección de concesión ADMIN

El siguiente intento del operador alcanzó TENANT_SQL y recibió SQLSTATE 0LP01.
Reproducción SQL independiente en transacción revertida: auto-concesión ADMIN TRUE
del owner al provisionador rechazada por ciclo de grantor. ADMIN FALSE en esa
auto-concesión pasó; el ADMIN original concedido por bootstrap se conserva.

El helper grant_owner_memberships concede SET TRUE e INHERIT FALSE, sin repetir
ADMIN TRUE en la auto-concesión. Inspección real: SET permitido, USAGE/herencia
deshabilitada. También concede al migrator solo su owner, sin ADMIN ni herencia.
control-check reproduce esa concesión como provisionador NOSUPERUSER con fixtures
NOLOGIN y rollback, sin pedir credenciales OpenBao ni persistir roles de prueba.

Resultado: PASS de reserva válida y concesiones owner, control 0003 repetible,
74 pruebas offline, Ruff/formato y reconstrucción correctos. No se regeneraron
secretos ni eliminaron recursos. Integración completa todavía pendiente de repetir.


### Comprobación de rechazos de conexión inicial

El operador alcanzó SQL_PROBES y obtuvo WRONG_DENIAL. Clasificación independiente
de registros del servidor: hubo un FATAL de permiso CONNECT denegado; no se publicaron
mensajes ni valores de esos registros. La comprobación anterior exigía SQLSTATE
exacto incluso en errores de conexión inicial, donde libpq puede no conservarlo.

La nueva prueba primero conecta con la misma credencial a su propia base.
Para el cruce A/B exige además has_database_privilege(CONNECT)=false. El intento
cruzado debe fallar con la firma FATAL específica de la base; para HBA exige usuario,
base y cifrado SSL esperados. Un código incompatible, base/usuario diferentes,
fallo de red, CA o password no cuenta como aislamiento. Nunca se imprime el mensaje
original. La firma depende del mensaje inglés del perfil fijado; un mensaje desconocido
detiene la prueba en vez de aceptarse.

81 pruebas offline, incluidas siete variantes de rechazo/casos falsos; Ruff/formato
y reconstrucción correctos. Integración completa pendiente de repetir por el operador.


### Contexto de rol del probe vector

El siguiente intento alcanzó SQL_PROBES y recibió 42501. La clasificación saneada
de la última consulta indicó VECTOR_CAST / permiso de schema public. El migrator
no hereda acceso de su owner: el probe estaba consultando vector antes de SET ROLE.

Se corrigió el probe para asumir únicamente el owner propio y ejecutar RESET ROLE
en finally. No se ampliaron grants. Prueba independiente contra PostgreSQL con los
roles reales A/B, estableciendo SESSION AUTHORIZATION para cada rol:
vector correcto en migrator/app/readonly y rol original restaurado, PASS.
Esta comprobación administrativa no sustituye los accesos con credenciales reales
de la batería completa del operador.

84 pruebas offline, incluidas restauración de rol ante error; Ruff/formato correctos.
Imagen reconstruida y ensayo completo solicitado al operador.


## Cierre técnico T002 — revisión humana pendiente

Diego ejecutó en su propia terminal scripts/f01_host.py run --rm sql-check.
Código probado: 0b297240d15a1c1b5acd2cfc30581d3938de1aea.
[PR #10](https://github.com/dlalvarez/rag-platform/pull/10),
[log saneado](../../docs/evidence/f01-t002-2026-10-30.txt) y
[manifiesto de fuentes](../../docs/evidence/f01-t002-source-sha256.txt).
No recibió Codex contraseña, token, SecretID ni credencial SQL.

| Trazabilidad | Resultado real | Fuente |
|---|---|---|
| R02 → AC01 parcial → P2/T002/V01 | rag_control y dos bases UUID distintas; TLS/vector, contrato tenant 0001 y upgrade repetido, PASS | sql-check del operador |
| R02 → AC02 parcial → P2/T002/V02 | CRUD propio, readonly sin escritura, app/migrator/readonly A↔B CONNECT denegado, SET ROLE cruzado prohibido, PASS | sql-check con credenciales reales |
| R02/R03 → P2/T002 | Secretos versionados OpenBao, referencias opacas, repetición sin rotación, PASS | sql-check del operador |
| R02 → P2/T002/V02 | Recurso coincidente sin ownership rechazado; rol NOLOGIN conservado y BD/roles restantes ausentes, PASS | fixture real de colisión |
| R01 → P1/T001-T002/V01 | Control 0003, reserva verify-full válida y rollback, concesiones owner sin ciclo ADMIN y rollback, PASS | control-check real |
| Regresión | 84 pruebas offline; Ruff/formato/documentación correctos | ejecución en servidor |

Corroboración independiente de metadatos: control en f01_control_0003; dos tenants
PROVISIONING con observed_version ausente; dos ubicaciones/distintos db_name,
verify-full y referencias readonly versionadas; dos bases tenant. Nueve roles
con prefijo tenant (ocho propios y fixture NOLOGIN ajena), ninguno con SUPERUSER,
CREATEDB, CREATEROLE, REPLICATION o BYPASSRLS. No se consultaron valores de secretos.

CONNECT rechazado impide ejecutar SELECT en la base ajena: no se presenta como
una consulta SELECT cruzada ejecutada. SET ROLE y denegaciones DDL/escritura se
probaron dentro de conexiones propias. Se conserva el límite administrativo del
provisionador CREATEDB/CREATEROLE; no se declara sandbox de clúster.

T002 entrega el paso SQL y contrato inicial. No publica READY ni observed_version,
no acredita saga/concurrencia/compensación T004, buckets T003, resolver/pools T005
o batería de dos instancias y migraciones coordinadas T006. T002 pendiente de
aceptación humana; F01 e Issue #7 permanecen abiertos. Sin merge automático.

Regresión posterior a la batería T002: F00 API, PostgreSQL/vector y roundtrip S3 sintético, PASS.


## Aceptación de T002 y entrega técnica T003

T002 aceptada por Diego e integrada en develop@ff24f439c75e93477df0a99835635d0fb00538d5;
[cierre PR #10](https://github.com/dlalvarez/rag-platform/pull/10#issuecomment-6535497540).
Las anotaciones de revisión pendiente en las entradas T002 anteriores son históricas.

F01-R04/R03 → AC-F01-03 / P3 / T003 / V03-V04.
[Runbook T003](../../ops/f01/T003.md),
[log saneado](../../docs/evidence/f01-t003-2026-10-30.txt) y
[manifiesto de fuentes](../../docs/evidence/f01-t003-source-sha256.txt).

| Prueba | Resultado observado | Fuente |
|---|---|---|
| Compatibilidad MinioAdmin | user_add, policy_add, attach_policy e inspección funcionan por HTTPS en la release fijada; sin mc | calibración real |
| Política/propiedad | bucket/ref/tenant en tags, política exacta y principal sin grupos; bucket ajeno intacto | storage.py y fixture real |
| V04 acceso propio | get/put/list/delete de A/B, PASS | s3-check del operador |
| V04 acceso cruzado | get/put/list/delete A→B y B→A rechazados AccessDenied; canaries conservados | credenciales reales A/B |
| V04 anónimo/admin | get/put/list anónimos denegados; user_list administrativo denegado | s3-check |
| ListBuckets | Respuesta filtrada contiene exactamente el bucket propio; no ListAllMyBuckets concedido | fuente de release y prueba real |
| V03 secretos | Credenciales versionadas en OpenBao, referencias en control, repetición sin rotación | s3-check del operador |
| TLS | CA propia correcta y CA ajena rechazada sin fallback | probe independiente sin credenciales |
| Regresión | 107 pruebas offline; Ruff/formato/documentos; control-check y F00 real correctos | ejecución en servidor |

Diego ejecutó s3-check en su propia terminal y comunicó tres PASS T003.
No se solicitaron ni mostraron valores de credenciales/tokens. Bootstrap MinIO está
separado del root OpenBao, que sigue revocado; el administrador no simula aislamiento.

Corroboración independiente: dos storage_locations, dos buckets tenant distintos,
versiones positivas y endpoint HTTPS. Dos tenants PROVISIONING con observed_version
ausente. IAM: ocho usuarios, dos habilitados (tenants) y seis de calibración deshabilitados.
Diez buckets: dos tenant, seis de calibración y dos fixtures ajenas; todos sintéticos,
conservados sin limpieza automática. No procesos de prueba persistentes tras --rm.

Minio 7.2.20 se promueve de dev a runtime; uv.lock solo cambia pertenencia de grupo.
No cambios de versiones/hashes de paquetes ni nuevas migraciones de catálogo.
MinIO usa la receta/imágenes fijadas de F00 con datos/TLS F01 separados, sin puertos
publicados. Límites F01: 3.75 GiB de servicios y 768 MiB de herramienta serial,
4.5 GiB en conjunto; límites no son consumo garantizado ni prueba de capacidad.
Observación durante la batería: servicios y herramienta por debajo de esos límites.

La calibración inicial esperaba rechazo total de ListBuckets; la implementación
upstream filtra por permisos de bucket. Se ajustó la prueba a exigir únicamente el
bucket propio, sin ampliar política. No se aceptaron errores de firma/red como
aislamiento ni se usaron respuestas simuladas para acreditar las denegaciones.

T003 pendiente de CI/revisión/aceptación. No se cierra AC de fase ni Issue #7.
T004–T007 pendientes: saga, concurrencia, compensación, pools, dos instancias y
migraciones coordinadas. No READY, producción, documentos reales, HA o restore.

Código T003 probado y manifiesto verificado:
ba91e1fb2fc590cf4c7e81794409855e2d3f6694,
[PR #11](https://github.com/dlalvarez/rag-platform/pull/11).
Las revisiones posteriores de documentación no alteran las fuentes ejecutadas.


## T003 aceptada y T004 en validación

T003 aceptada e integrada en develop@4593f3832dd601c0d2ca7424281397622eac923a.
[cierre PR #11](https://github.com/dlalvarez/rag-platform/pull/11#issuecomment-6535895042).
Sus anotaciones de revisión pendiente anteriores describen el estado previo a esa aceptación.

F01-R05 → AC-F01-04/05 → P4 → T004 → V05.
[Runbook T004](../../ops/f01/T004.md). Registro persistente, locks de sesión,
propiedad por operación y compensación conservadora implementados.
Revisión control 0004 aplicada y repetida en PostgreSQL real, PASS.
Probe real de lock: segunda conexión rechazada, sin transacción abierta y liberación, PASS.
F00: API, PostgreSQL/vector y roundtrip S3 sintético, PASS.
Pruebas offline de fallos/reintentos/códigos cerrados correctas.
La batería con credenciales reales fue ejecutada por Diego: cuatro PASS T004.
T004 pendiente de revisión/aceptación humana; no se cierra F01.


## Entrega técnica T004 — revisión humana pendiente

Código ejecutado: 2b75e922fa407393004e14fbe29717b6e78cfa77,
[PR #12](https://github.com/dlalvarez/rag-platform/pull/12).
[Log saneado](../../docs/evidence/f01-t004-2026-10-31.txt) y
[manifiesto de fuentes](../../docs/evidence/f01-t004-source-sha256.txt).
Las revisiones posteriores de documentación no cambian las fuentes de ejecución.

Diego ejecutó saga-check en su propia terminal e informó cuatro PASS:
- Fallo real de CreateBucket: FAILED sin READY; recursos SQL conservados y sin nuevos
  accesos. Reintento con los mismos UUID, referencias, credenciales y OID SQL.
- Caída de proceso tras SQL y antes de completar journal: recuperación de la misma operación.
- Dos procesos sobre una clave: exclusión por lock; segundo intento sin efectos.
- Bucket ajeno y canary intactos; conflicto y pendientes REVIEW registrados.

La batería terminó con tres tenants sintéticos READY y uno FAILED/REVIEW.
READY acredita la migración inicial y los probes de esta saga; no sustituye resolver/pools
T005 ni migraciones generales, canary y dos instancias T006. Las fixtures T002/T003
no son adoptadas ni promovidas a READY por esta prueba.

123 pruebas offline correctas; Ruff/formato/documentos y negativos F00 correctos.
Control 0004 aplicado/repetido, lock PostgreSQL real y regresión F00 correctos.
CI docs/lint/tests del commit de código completado correctamente en push y PR.
CI del nuevo HEAD documental se verifica por separado antes de presentar revisión.

No se recibieron contraseñas, tokens o SecretID en el chat. La compensación conserva
datos y referencias, retira nuevos accesos solo a recursos de la operación y deja REVIEW
si no puede verificar propiedad. No termina sesiones SQL ya abiertas. Un commit final
con respuesta perdida se reconcilia sin revocar un READY posiblemente confirmado.
Sin eliminación automática, cambios de API pública ni dependencias nuevas.
T004 no se marca aceptada hasta revisión humana; F01 e Issue #7 siguen abiertos.

Corroboración independiente posterior: control 0004; tres operaciones SUCCEEDED con
los seis pasos completos, tenant READY y revisión observada 0001; marcadores SQL por
operación y recursos S3 propios verificados. Una operación FAILED/OWNERSHIP_CONFLICT
con pendiente REVIEW; tags y canary del bucket ajeno intactos. Sin lectura de valores
de OpenBao ni exposición de credenciales.


## T004 aceptada; inicio de T005

T004 aceptada por Diego e integrada en develop@e46b46f822ca3726086d3b2ba3dc78b71db9ba3e;
[cierre PR #12](https://github.com/dlalvarez/rag-platform/pull/12#issuecomment-6544965980).
Checks y validación postmerge correctos. Las entradas T004 anteriores con aceptación
pendiente son históricas.

F01-R03/R06 → AC-F01-06 parcial → P5 → T005 → V03/V06.
[Runbook T005](../../ops/f01/T005.md). Resolver interno, registro por destino/rol/ref-versión,
QueuePool limitado, LRU y drenado implementados. Sin nuevas migraciones, dependencias,
servicios o API pública. SecretStore se consulta en cada adquisición, sin caché de valores.
Pruebas offline ejecutadas de gates, errores saneados, saturación, LRU, cambio de destino,
drenado, rollback y ocho préstamos concurrentes. Batería real con OpenBao completada por Diego.
No se acredita AC-F01-06 completo: dos instancias reales y pruebas ampliadas son T006.

Validación inicial T005 en servidor: 138 pruebas offline correctas; Ruff/formato,
documentos y pruebas negativas F00 correctos. Inspección real del catálogo: tres
destinos READY distintos; tenants no READY/desconocidos rechazados antes de leer
SecretStore; control con pool separado de dos. Esto no acredita todavía conexiones
tenant reales mediante la factory ni caducidad/revocación con pool caliente.

Regresión F00 real: API, PostgreSQL/vector y roundtrip S3 sintético, PASS.
[Log inicial T005](../../docs/evidence/f01-t005-2026-10-31.txt) y
[manifiesto de fuentes](../../docs/evidence/f01-t005-source-sha256.txt).


## Entrega técnica T005 — revisión humana pendiente

F01-R03/R06 → AC-F01-06 parcial → P5 → T005 → V03/V06.
Código ejecutado: bd3145baf48971c40d77b1f3c9146d0de5ed537a,
[PR #13](https://github.com/dlalvarez/rag-platform/pull/13).
[Log saneado](../../docs/evidence/f01-t005-2026-10-31.txt) y
[manifiesto](../../docs/evidence/f01-t005-source-sha256.txt).
Las revisiones posteriores de documentación no cambian las fuentes ejecutadas.

Diego ejecutó pool-check en su terminal e informó cuatro PASS:
- A→B→A: destino, usuario y PID propios, TLS y flags sin privilegios globales.
  Rollback al devolver; tenants desconocidos/FAILED y contexto/rol inválidos rechazados.
- Ocho conexiones reales en cuatro engines; quinto engine rechazado por CAPACITY.
  Tercera conexión de un pool agotó su timeout; devolución, evicción y cierre correctos.
- Cambio temporal de referencia sintética con la misma credencial: nuevo engine/PID,
  préstamo antiguo vivo hasta retornar y drenado posterior. La prueba comprobó
  restauración de la referencia original. No cambia passwords SQL.
- Token AppRole adicional revocado contra OpenBao real: siguiente adquisición rechazada,
  incluso con pool caliente. Sin fallback ni revocación del operador o del token principal.

La batería no crea tenants, bases, servicios ni migraciones. Conserva una referencia
sintética adicional versión 1 en OpenBao, con la misma credencial, fuera del catálogo.
No es rotación operativa ni limpieza. No se solicitaron secretos al chat.

138 pruebas offline correctas; Ruff/formato, documentos, negativos y regresión F00 correctos.
CI docs/lint/tests del código ejecutado pasó en push y PR. El HEAD documental final
se comprueba por separado. Sin autenticación de usuario F02 ni segundo endpoint real:
T006 mantiene la batería de dos instancias y migraciones ampliadas.
Las conexiones ya prestadas no se revocan al retirar un engine; las cotas son por proceso.
T005 pendiente de aceptación humana. F01 e Issue #7 permanecen abiertos.

Corroboración independiente posterior: seis tenants conservados (tres READY,
dos PROVISIONING y uno FAILED), cuatro operaciones (tres SUCCEEDED y una FAILED),
tres destinos READY distintos y referencias SQL versión 1. Control sigue en 0004;
no quedaron sesiones SQL tenant. Esta inspección verifica estructura/versiones y
conteos; la igualdad con la referencia original fue comprobada por la batería del
operador. Sin lectura de valores de OpenBao. Regresión F00 posterior completa, PASS.


## T005 aceptada; inicio de T006

T005 aceptada e integrada en develop@290e381c3b6c4d4e1ef52a3e81e75ea96b3e818b;
[cierre PR #13](https://github.com/dlalvarez/rag-platform/pull/13#issuecomment-6547808923).
Checks y validación postmerge correctos. Las anotaciones T005 de aceptación pendiente
anteriores describen el estado previo a esa integración.

F01-R01..07 → AC-F01-01..07 parciales → P6 → T006 → V01..V07.
[Runbook T006](../../ops/f01/T006.md).
Coordinador de migración implementado: lock transaccional en la misma conexión Alembic,
identity/version reales, control sin READY durante MIGRATING y FAILED sin versión observada.
Revisión canónica tenant sigue 0001; fixtures reversibles fuera de la pista canónica.

Segunda instancia preparada y arrancada con datos, password y certificado propios,
sin reiniciar servicios anteriores ni publicar puertos. Límites F01 más una herramienta
suman 5 GiB. Antes: unos 14,8 GiB disponibles y 110 GiB libres en ext4.
Observación puntual posterior: postgres2 usaba unos 34 MiB de 512 MiB y CPU cercana a cero;
no es garantía de rendimiento ni prueba de carga.

Calibración real en postgres2 completada: migrator limitado por TLS, Alembic, canary,
upgrade/downgrade/upgrade, rollback transaccional del DDL fallido, dos procesos,
timeout PostgreSQL y reintento. Retenida una BD de calibración y cuatro roles, todos
NOLOGIN al finalizar; nuevas conexiones a la BD deshabilitadas. Sin tenant/catálogo,
SecretStore ni cambio de recursos existentes en esa calibración.
La calibración inicial no acreditaba por sí sola aislamiento tenant. La batería integral
posterior del operador se registra abajo; la aceptación global de F01 sigue pendiente.

Validación previa al operador: 144 pruebas offline correctas; Ruff/formato,
documentación SDD y pruebas negativas F00 correctos. Control-check PostgreSQL/TLS
repetido, PASS. Regresión real F00 API/PostgreSQL/vector/roundtrip S3, PASS.
[Log inicial](../../docs/evidence/f01-t006-2026-10-31.txt) y
[manifiesto de fuentes](../../docs/evidence/f01-t006-source-sha256.txt).
La batería isolation-check con credenciales OpenBao fue ejecutada posteriormente por Diego.


## Entrega técnica T006 — revisión humana pendiente

F01-R01..07 → AC-F01-01..07 parciales → P6 → T006 → V01..V07.
Código ejecutado: fe431aa402ec17382ae4c9cfb33d889038102264,
[PR #14](https://github.com/dlalvarez/rag-platform/pull/14).
[Log saneado](../../docs/evidence/f01-t006-2026-10-31.txt) y
[manifiesto](../../docs/evidence/f01-t006-source-sha256.txt).
Las revisiones posteriores de documentación no cambian las fuentes ejecutadas.

Diego ejecutó isolation-check en su terminal y reportó nueve PASS:
cuatro SAME_INSTANCE, cuatro TWO_INSTANCES y uno adicional de destino erróneo.
Ambas baterías probaron SQL/S3 propios y rechazos en ambos sentidos, pools A→B→A,
fallo real de bucket sin READY, reintento con credenciales/identidad conservadas,
upgrade/downgrade/upgrade sintético, fallo DDL revertido y otro tenant intacto.
Dos procesos comprobaron lock/timeout PostgreSQL, estado FAILED sin versión falsa,
rechazo del resolver y recuperación/repetición correctas.

Entre instancias se comprobó ausencia del principal en el otro nodo y rechazo de
autenticación; no se presenta como un rechazo CONNECT 42501 de una misma instancia.
El destino equivocado se inyectó en un adaptador de catálogo de prueba, sin cambiar
ubicaciones reales. La adquisición falló sin recurrir al préstamo anterior; el destino
correcto volvió a conectar. PID numérico no identifica una conexión entre servidores:
se comprobó junto con endpoint/BD/rol.

Resultado de la batería: cuatro fixtures T006 READY. Secretos versionados en OpenBao,
referencias opacas en control, ningún secreto recibido en chat ni usado como argumento.
La fixture reversible conserva canary y versión propios; la pista canónica sigue 0001.
No se aplicó downgrade canónico ni se borraron bases, buckets o recursos ajenos.
El token de operador se revoca al finalizar; los tokens AppRole mantienen su TTL aprobado.

144 pruebas offline correctas; Ruff/formato, documentación y negativos F00 correctos.
CI docs/lint/tests del código probado pasó en push y PR. El HEAD documental final se
verifica por separado. Sin dependencias nuevas ni endpoints públicos.
T006 pendiente de aceptación humana; T007 y la aceptación global F01 siguen pendientes.
No se acredita backup/restore, HA, PITR independiente ni funcionalidades F02+.

Corroboración independiente posterior: diez tenants (siete READY, dos PROVISIONING,
uno FAILED) y ocho operaciones (siete SUCCEEDED, una FAILED). Las cuatro fixtures T006
están READY/READY con versión observada 0001; tres ubicaciones nuevas en primario y
una en secundario, referencias SQL versión 1 y propiedad/política/principal S3 privados
exactos. No quedaron sesiones SQL tenant en ninguno de los dos nodos. Control 0004,
estados previos preservados y regresión F00 completa posterior, PASS. Esta inspección
lee metadatos, no valores OpenBao; el acceso tenant real, canaries y versiones reales
se acreditan mediante la batería del operador.

Los resultados cubren las pruebas técnicas de T006; las casillas AC globales de F01
permanecen abiertas hasta T007 (CLI/clon limpio) y aceptación de fase.
