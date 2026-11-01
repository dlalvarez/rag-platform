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
