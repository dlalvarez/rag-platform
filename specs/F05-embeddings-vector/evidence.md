# Evidencia F05 — planificación, sin implementación

2026-11-02. F04 aceptada develop45726ec6477370a3fb466a12dd77488b3b1228e9:
PR44/CI/postmerge,46 tests específicos, checkouts limpios y69 módulos src/instalados
exactos en runtime/API/QA. Baseline702 tests y regresiones reales F00..F03 conservados.
[Registro](https://github.com/dlalvarez/rag-platform/pull/44#issuecomment-6575586701).

Leídos constitución/arquitectura/tenancy/modelo de datos/ingesta/roadmap/decisiones y
spec F05 original. Plan/tareas/checklist y ADR0011 PROPUESTO respetan R01..05/AC01..04.
D-06 es decisión real pendiente, no aprobación rutinaria por pasar de fase.

Consulta de metadatos públicos desde ragdev01 confirmó candidato
intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3:
MIT, hidden_size384, max_positions512 y model.safetensors disponible.
Fichas oficiales E5/BGE y pgvector0.8.7 verificadas; no son benchmark de nuestro corpus.
No se descargaron pesos, instaló inferencia, llamó API embedding, creó schema/índice
ni publicó documento. Ningún AC F05 acreditado aún; no implementación ni aceptación.
F03/F04 API/worker/datos/secretos/políticas intactos por este PR documental.

## Decisión expresa D-06

Diego respondió el 2026-11-02: «Aprobar E5-small local (recomendado)» a la propuesta
PR45/ADR0011 de desarrollo, 384/coseno/512 y gates ES/EN/capacidad. Se registra la
aprobación sin inferir resultados, producción o calidad ya medida. Ningún peso,
modelo, dependencia de inferencia, índice o migración ejecutados por esta actualización.
T002 independiente tiene 45 tests / 747 completos en el checkout, aún sin integrar.

## Sustitución expresa por Qwen (2026-11-02)

Diego pausó E5 antes del merge/descarga/migraciones y eligió «ok, adoptemos qwen».
ADR0011 pasa a Qwen3-Embedding-0.6B/1024/coseno/L2, cota inicial 512/batch4, CPU local.
Metadatos públicos verificados desde ragdev01: revisión97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3,
Apache-2.0, hidden_size1024/max_positions32768, SHA256 de safetensors en ADR.
No hay benchmark ni AC acreditados por la selección; sin cambio de vCPU/servicios/datos.

## T002 — contrato independiente y corpus congelado

Perfil/resultado inmutables y validador completo antes de persistencia. Fixture
SHA256 identificada, offline, sin suplantar Qwen. Pruebas de mismatch incluso con
misma dimensión, NaN/Inf/bool/float32/cero/norma, límites, tokens y error privado.
Instrucción multilínea fija soportada; otros controles rechazados. No schema/runtime.
Corpus ficticio16 documentos/16 preguntas ES/EN con gold previo a medición; SHA256
ca4d53dd72713febe740eebd958b384aae6dd9f2793c8433314c224b3284340e.
No mide calidad de dominio ni aceptación F06; sin AC SQL/indexación acreditados.

Validación ragdev01: 47 casos específicos (incluidos en 749 tests completos),
749 passed en38.91s; ruff/docs/diff correctos. Advertencia Starlette/httpx ya existente.

## T001 — adaptador Qwen y primera medición real

Pesos10 artefactos públicos fijados/verificados en ragdev01. EntornoCPU separado
con lock propio; sin tocar lock principal/servicios/BD/vCPU. Corpus SHA congelado
antes de inferir. Red desactivada, tokenizer/modelo locales, no descargas en ejecución.
Resultado agregado qwen-benchmark-01.json y manual qwen-local.md: recall@3=1.0
ES/EN en16 preguntas ficticias, p50=2.154s/p95=3.95s, picoRSS3796.6MiB.
No afirmar calidad representativa, capacidad concurrente, aislamiento o cierre F05.

Validación entrega Qwen:758 tests completos passed en38.88s (9 nuevos límites/privacidad),
ruff/docs/diff correctos. uv sync --locked separado comprobó25 paquetes sin cambios.

## T003 parcial — fundación aditiva y ensayo transaccional

Preparados catálogo inmutable/tabla vectorial por space/HNSW, FK de procedencia,
perfil/dimensión/norma, cuota/lock y helpers con savepoint. Migración tenant0004
no cambia documentos/chunks/guards F04. Perfiles runtime/control EMBED aún pendientes.
Primera ejecución se detuvo por objeto SQL del controlador (no PASS); corregido.
Un intento posterior no arrancó por resolución de mount; no hubo SQL.
Ensayo final conserva snapshot/control y revierte DDL/datos en cuatro fixtures,
ambas instancias. No hay adopción persistente ni nuevos tenants/objetos S3.
18 negativos/DDL offline;776 tests completos passed en39.55s, ruff/docs/diff correctos.
Manual space-foundation.md detalla límites; no cierre T003 ni AC02/03 completos.

## T003 parcial — compatibilidad F05 opt-in

Perfil embeddings=head tenant0004, fuentes soloF04/head propio, HMAC de contexto
separado. RAG_F05_ENABLED exigeF03/F04; sin bandera conserva configuración previa.
API/worker INGEST compatibles con head exacto, sin rutas embedding/search nuevas.
Claim/fencing INGEST filtran kind para no tomar ni confirmar futurosEMBED.
796 tests completos passed en39.99s (20 nuevos), ruff/docs/diff correctos.
Imágenes rag-f05-api:t003/rag-f05-ingestion:t003 construidas en ragdev01,
75 módulos instalados coinciden por SHA256 con fuentes, comprobado sin red.
No servicios recreados/adopción persistente todavía; no atribuir pruebas HTTP F05
ni cierre deT003. Próxima entrega: adopción controlada y cola EMBED separada.

## T003 parcial — controlador/preflight de adopción

799 tests completos passed en39.23s;3 pruebas nuevas impiden sobrescritura de
checkpoints/symlinks, ruff/docs/diff correctos. QA t003 construida con controladores.
Preflight real4 fixtures pasó scope/TLS/roles/snapshots, sin DDL persistente.
Journal privado: /home/diego/proyectos/rag-platform-f05-adoption-runs/
8f9a197defd04a3baacde6bac5a56886; checkpoints0600 y directorio0700.
Preparados falloDDL=>FAILED/observedNULL/recovery/repetición y registroQwen
vacío, más regresión F01..F04 con profile F05. Adopción/HTTP F05 aún no ejecutados
al preparar este head; realizar solo tras CI/revisión y registrar resultado real.

## Adopción real revisada y regresión F05 (2026-11-02)

Head controlador f9ab217a3433ecf9e9ae52f44ce34fe23dc310c9/PR50 pasó 4 checks y
revisión previa delegada; comentario6577568741. Fuentes QA comprobadas por SHA
antes de ejecutar. Ventana detuvo/recreó SOLO API; entrega reemplazada tras cierre.
Las 4 fixtures pasaronDDL 22012=>FAILED/observedNULL, rollback físico, recuperación
y repetición a tenant0004, registro/repetición de espacio Qwen por tenant y
snapshots de TODAS las tablas F04 intactos antes/después de migrar. Espacios vacíos.
Identidades/jobs/otros tenants de control conservados. Journal 8f9a197defd04a3baacde6bac5a56886.

API rag-f05-api:t003 activa, HTTPS/health phase F05 verificado. Solo API cambió ID;
PostgreSQL/segunda instancia/MinIO/Bao/IdP/F00 y worker anterior conservaron IDs.
API user1000/rootfs+bindsRO/cap_dropALL/no-new-privileges; worker anterior detenido (exit 0).
No vCPU/contraseñas/AppRole/políticas modificados. Entrega QAworker separada, limitada.

Regresión real f05-regression-check exit0: OIDC/JWT/consultas inválidas;4 fixtures
SQL/TLS/vector/roles sin privilegios/crossCONNECT+SETROLE;S3 propio/cruzado;
originales históricos F03 con SHA/ACL/versiones intactos y sin ingesta retroactiva.
Controlador reutiliza T007 de F04 bajo perfil F05; no acredita T007/AC completos F05.
Logs desde 12:54 UTC: postgres/postgres2 con positivos LOG/ERROR, sin canaries
documentales; API/MinIO/Bao también sin canaries. Logs raw no se exportaron.

T003 parcial: fundación+compatibilidad adoptadas, colaEMBED y T004..T008 pendientes.
No vectores documentales generados, PUBLISHED, búsqueda F05 ni cierre de fase.

## T001 — límite operativo real y CPU

Caso de capacidad declarado antes de medir:4 pasajes ficticios de512 tokens, cota
RSS6144MiB por proceso. Resultado qwen-capacity-01.json:2vCPU, batch63.601s,
CPU85.608s/134.6% medio, pico3774.2MiB; llamada simultánea rechazada y llamada
posterior correcta. Dimensión/norma/finitos validados por proveedor real. Sin red,
cambios de vCPU, datos tenant, modelo externo ni procesos persistentes.
T001 inicial completada con fixture semántico previo y capacidad; AC completos
F05/calidad de dominio/carga multi-proceso siguen pendientes. Modelo/space intactos.

## T003 parcial — envelopes control0007 y ensayo con rollback

2026-11-02, ragdev01: evolución aditiva INGEST/EMBED con UUID de espacio y
fingerprint, unicidad por versión+espacio, errores cerrados y sin contenido privado.
Definiciones históricas intactas. Ocho pruebas nuevas; 807 passed en42.82s,
una advertencia Starlette/httpx preexistente. Ruff/docs/diff correctos.

Ensayo PostgreSQL real: fallo DDL22012 y rollback, upgrade/repetición, rechazo
perfil/hash/UUID nulo, duplicado23505 y convivencia de espacios. Consumer INGEST
no toma EMBED. APP_GRANTS falló inicialmente42501 porque el migrador no puede
asumir f02_identity_app; corregido usando has_table_privilege por privilegio y
has_schema_privilege, sin membresías ni grants nuevos. Es comprobación de catálogo,
no ejecución autenticada como app. Todo revertido: control siguef04_control_0006;
snapshots de jobs/identidad/catálogo iguales. Sin adopción persistente ni cierreT003.


## T004 parcial — consumidor durable EMBED
2026-11-02 ragdev01: claim inmutable con espacio/fingerprint, enqueue idempotente,
leases/heartbeat/reclaim/backoff/agotamiento y fence de todas las identidades.
Comparte algoritmo con INGEST conservando tabla/errores/kind F04 por defecto.
El guard usa la tabla del consumidor para evitar mezcla de metadatos SQL.
29 pruebas nuevas; 836 passed en42.22s, advertencia Starlette/httpx preexistente.
70 pruebas focalizadas INGEST/fence/envelopes/EMBED correctas.

PostgreSQL real con rollback: consumer EMBED, heartbeat, espacio/perfil falsificados
rechazados, guard/ack, error de dimensión terminal, replay/conflicto de perfil,
lease expirado/reclaim/token viejo y retry/backoff. Snapshots/control0006 conservados.
Ruff/formato/docs/diff correctos. No prueba de consumidores concurrentes con commits
independientes ni inferencia/publicación/usage: T004 sigue abierta.
PR52 integrado7a42556, cuatro checks antes y tres postmerge correctos.

Revisión final: worker INGEST rechaza cola EMBED antes de I/O. Caso adicional;
837 passed en54.35s,30 nuevas T004; ruff/formato correctos. Sin cambio SQL.


## T005 parcial — expansión del ancla original
tenant0005 añade original_version_id/kind, backfill/FK diferida y guard inmutable;
no cambia todavía el constraint F04 que mantiene current pointer ORIGINAL.
Helper explícito rechaza identidad/head desconocido, verifica columnas/constraints/
función/trigger y usa savepoint. No perfil runtime nuevo ni adopción persistente.

2026-11-02, ragdev01:837 passed42.34s, ruff/formato/docs/diff correctos. SQL real
en4fixtures/2instancias: fallo DDL22012 rollback, repetición/backfill/snapshots intactos,
head desconocido y trigger deshabilitado rechazados; app inserta con esquema F04,
UPDATE ancla app42501, owner no puede cambiarla23514; FK cruzada23503.
El primer ensayo falló por esperar23514 donde app carece de UPDATE42501; ajustado
el probe sin otorgar permisos. Constraint FK se referencia con esquema explícito.
Todos los ensayos revertidos; tenants siguen0004 y control0006. No publicación,
usage, procesamiento ni descarga HTTP postpublicación acreditados. T005 abierta.
PR53 integrado5c9b947, cuatro checks antes y tres postmerge correctos.

Revisión final ancla: INSERT explícito debe coincidir con current original inicial.
Negativo añadido y SQL4fixtures repetido correcto; sin nueva adopción.


## T004/T005 parcial — ledger y publicación física0006
2026-11-02, ragdev01: tenant0006 añade intents, lotes/uso exitoso y bindings completos
por versión+space; estadoPUBLISHED conserva provenance F04. Guards diferidos exigen
puntero/binding/vectores/cobertura/usage/auditoría; app sin UPDATE/DELETE de lotes/vectores/
publicaciones. Identidad inmutable; dispatch tardío puede completarse tras resultado,
pero job ya fijado y resultado no pueden cambiar. Registro de space acepta head0006
solo mediante wrapper explícito; defaults administrativos0004 conservados.

837 passed38.57s, ruff/formato/docs/diff correctos. SQL real4fixtures/2instancias,
todo rollback: DDL fallo22012/replay, binding ausente, chunks inválidos/duplicados/
ordinal/tokens, estados/error/lease incompatibles, intento expirado, usage o vectores
ausentes, auditoría ausente, ACL revocada y tombstone rechazados; publicación completa,
ancla original conservada, relay tardío y reindex a segundo perfil de igual dimensión
sin tocar vectores/publicación anteriores; duplicado23505. Primer negativo falló42702
por alias SQL ambiguo; calificado y repetido correctamente. SQL usa vectores sintéticos
unitarios y uso ficticio; no es inferencia ni medición real del proveedor.

Tenants siguen0004/control0006, sin adopción, runtime compatible ni publicación
persistente. Pendientes worker real/reautorización/heartbeat/crash/usage real, HTTP
original postpublicación, concurrencia con commits independientes y aceptación F05.
PR54 integrado02f6d83 con cuatro checks previos/tres postmerge correctos.


## T005 parcial — compatibilidad runtime opt-in0006
Perfil embedding_publication exige f05_tenant_0006, prefijoHMAC separado y bandera
RAG_F05_PUBLICATION_ENABLED=1 subordinada a F03/F04/F05. Sin bandera conserva0004.
Resolver/authority/servicios/workerINGEST admiten solo perfil exacto; fuentes migración
0004/0005/0006 cerradas. Runner controlado no marca READY un resultado incorrecto.

Original/list/show/replay/solicitud INGEST usan ancla explícita bajo nuevo perfil;
no fallback por inspección del head. INGEST reconciliado tras PUBLISHED confirma ack
sin descargar/parsing de nuevo. SQL real4fixtures/2instancias rollback: original y
replay devuelven el original después de publicar; nueva solicitud ingesta/replay
ancla la procedencia correcta. Primer replay falló InvalidRequestError por FROM
implícito; fijado select_from(documents), repetido correcto.

20 casos nuevos,857passed40.68s;59 focalizados correctos. Ruff/formato/docs/diff
correctos. Sin imagen nueva, activación de bandera ni adopción/HTTP postpublicación.
Pruebas SQL son consultas metadata/ingesta sintéticas, no descarga S3 persistente.
PR55 integrado2c65818 con cuatro checks previos/tres postmerge correctos.


## T004 parcial — worker EMBED y recuperación
2026-11-02, ragdev01: código worker SQL-only con scope fijo/perfil exacto, relay de
intents explícitos, lotes+vectores+usage atómicos, contexto nuevo tras inferir, heartbeat
sin transacción tenant y commit tenant anterior a ack reconciliable. Nuevas ingestas
bajo perfil0006 crean intentQwen en el mismo commit de READY; historia READY anterior
requiere request explícito. Cola filtrada por fingerprint deja otro modelo pendiente.
Fuente/texto de batch ligado a SHA de chunks inmutables; provider/perfil no pueden
derivar durante trabajo. Quota inicial64chunks/32768tokens de contenido persistido;
máximo3intentos. Lote sin commit puede repetirse; no uso/coste exactly-once.

Entrega temporal: no renovación; margen180s o DENIED/INVALID impide nuevos claims y
detiene antes de persistir. Parciales guardados se retoman con consumidor/entrega nueva,
sin consumir intentos repetidos por credenciales vencidas. Lock liberado por cierre.
Sin credenciales admin/día ni S3gateway en nuevo runtime; modelo opcional fuera de API.

47 casos nuevos,904passed58.62s;77focalizados correctos. Ruff/formato/docs/diff correctos.
Offline usa autoridad real y SQLite transaccional, sin guards PostgreSQL: crash tras
batch/tenant-commit, ack perdido incluso con actor revocado después, ACL/membership/
tombstone durante inferencia, contexto30s vencido, lease perdido, rollback vector+usage,
output inválido, límite tokens/quota, parada/acceso vencido, hash distinto y filtro modelo.
SQL real4fixtures/2instancias con rollback valida request/start/next/save/complete/
dispatch/reconciliación tenant usando provider determinista/guard sintético explícitos.
Control SQL rollback valida filtro FP, heartbeats/fences/reclaim sin SETROLE app.
No son E2E de proceso con control+tenant commits independientes ni inferencia Qwen real.

Primera prueba de deriva de provider dejó RUNNING antes de start; ahora deriva detectada
antes de claim. Se verificó pasar fingerprint desde CLI a cola. No activar todavía:
pendientes imagen/lock opcional, adopción control0007/tenant0006, handoffs nuevos,
worker real/crash/proveedor/Qwen y HTTP/S3 originales/regresión. Sin servicios cambiados.
PR56 integradod37b2f6 con cuatro checks previos/tres postmerge correctos.

## T007 parcial — imagen y entrega privada EMBED
2026-11-02, ragdev01. Imagen rag-f05-embedding:t004 con lock CPU separado.
Versiones compartidas iguales al lock de aplicación; Torch fuera del entorno API.
Smoke sin red/credenciales/pesos: Torch 2.7.1+cpu, transformers 4.51.3, cuda=None,
entrypoint importable y hashes de 90 módulos iguales al árbol probado.
Composición validada sin iniciar servicios. La revisión propia corrigió tag y
banderas explícitas antes de ejecución; no atribuir revisión independiente.

Herramientas prepare/status y ensure/replace con consumer.lock antes de abrir día.
Seis pruebas nuevas: locks privados e inodos conservados, status sin bearer,
consumidor activo impide abrir sesión, emisión conserva y libera lock incluso al fallar.
910 passed en 59.01s; ruff/formato/docs correctos. Warning heredado httpx/TestClient.

Se retira SELECT readonly de ops.embedding_intents/batches; SELECT publications
conservado. SQL real sobre cuatro fixtures/dos instancias, rollback completo:
readonly recibe 42501 en ambos ledgers y consulta publicaciones. Sin grants persistentes.
No se ha ejecutado prepare real, emitido handoff, cargado Qwen ni iniciado servicio.
Control 0006 y tenants 0004 permanecen. Falta controlador de adopción de publicación,
ventana revisada, proceso real, fallos entre commits independientes y regresión.
PR57 integrado 9bf87f0 con cuatro checks previos y tres postmerge success.

## Concreción de contrato HTTP aprobada
2026-11-02: Diego respondió «Aprobar búsqueda HTTP de fragmentos en F05» a la
propuesta registrada. docs07 y F05-R06 concretan request, hits, procedencia, score y
uso de embeddings. Se retira del ejemplo de búsqueda la generación que corresponde
a F07. Esta aprobación no habilita la ruta ni acredita sus pruebas pendientes.

## T005 parcial — controlador y preflight de publicación
2026-11-02, ragdev01: controlador para fuentes tenant0004/0005/0006 y control0006/0007,
scope fijo, journal distinto y baseline inmutable; exige preflight previo y repetido
antes de DDL, jobs detenidos, espacio Qwen único/vacío y conexiones app/readonly cerradas.
Preparado fallo22012/FAILED/rollback/recuperar/repetir y comprobación de roles reales.
La ventana adopt completa todavía NO se ha ejecutado; control0006/tenant0004 permanecen.

925 passed en 63.44s, 18 focalizados correctos; ruff/formato correctos. Quince casos
nuevos: checkpoint/conflicto/symlink del journal nuevo, ausencia de preflight/modo
inválido antes de DB y catálogos incompatibles/targets ajenos rechazados sin mutación.
Primer test esperaba FileNotFoundError; helper privado cierra con ValueError, corregido.
Dos preflights reales correctos en cuatro fixtures/dos instancias, roles/TLS/hashes,
originales y espacio vacío conservados. Día ACTIVE verificado sin renovación.
Compose run local no soporta --no-build: rechazó antes de ejecutar; se usó imagen
existente verificada con --pull never y sin dependencias. Orphan F04 se conserva.
No credencial nueva, servicio reiniciado, inferencia ni migración persistente.
PR58 integrado con cuatro checks previos/tres postmerge success; PR59 contrato aprobado
integrado con cuatro checks previos, postmerge pendiente al registrar esta evidencia.

## T007 parcial — runtime de publicación preparado
Imágenes API/INGEST/tools t006 construidas en ragdev01 con Dockerfiles/lock existentes.
Smoke sin red/credenciales: importación y SHA de90 módulos igual al código probado
en cada imagen; ninguna contiene Torch. Wrapper QA final importado sin ejecutar la
batería; sus hashes y el controlador coinciden con las fuentes (dos scripts).
Overlay opt-in fija tenant0006 para API/INGEST; regresión reutilizada con perfil
embedding_publication. Composición conjunta validada con variables F02/F03 necesarias,
sin iniciar servicios. Primera validación omitió RAG_F03_UID/GID y fue rechazada antes
de ejecutar; corregida. Ruff/formato/docs/diff correctos.

No cambia src ni dependencias. Baseline925tests del controlador correcto; la batería
HTTP/SQL/S3 de este perfil no ejecutada hasta adoptar. No servicio nuevo, entrega
emitida ni DDL persistente. PR60 integrado a6c2c56, cuatro checks previos success;
postmerge todavía en curso al registrar. PR59 postmerge tres checks success.

## T004 parcial — QA real preparada, migración bloqueada
La revisión automática rechazó ejecutar adopt por requerir autorización explícita
para migraciones persistentes. La acción no se ejecutó; se pidió autorización al
usuario y quedó pendiente. Control0006/tenants0004 permanecen. Se restableció el mismo
contenedor/imagen API t003, con entrega limitada existente emitida bajo consumer.lock;
OIDC/me y original histórico HTTP/SHA correctos. Día no renovado, políticas intactas.

Se prepara QA request/verify para atomic de cuatro fixtures, scope/actores OIDC
verificados, journal propio y manifest RO. Solicita explícitamente esas versiones;
verifica binding/usage/vectores/publicación/ack y original HTTP/SHA después de Qwen.
Nueve tests nuevos de selección repetible y rechazo de deriva de actores/tenant/
fixtures/documentos; 934 passed en 58.18s, ruff/formato/composición correctos.
Detectado durante revisión: manifest almacena alias alice, no UUID en el campo actor;
se contrasta el alias y el mapa de actores completo contra identidades reales.
No se ejecutaron request, modelo ni verify. No hay intent/embedding persistente nuevo.

## Adopción autorizada y primera publicación Qwen real
2026-11-02, ragdev01. Diego autorizó «Sí, actualizar las bases de prueba».
Control0007 y cuatro tenants0006 adoptados con journal nuevo e inmutable49c88c83.
La restauración temporal de API había añadido tres autenticaciones OK; se verificó
por hash que eran la única diferencia respecto del journal anterior y se conservó
ese journal. Fallo22012/FAILED/rollback/recuperación/repetición por fixture correctos,
roles reales y hashes de originales/F04/identidades/jobs preservados.

API compatible t006 activa en contenedor separado; API t003 detenida y conservada.
Regresión completa OIDC/SQL/TLS/roles/ACL/S3/original HTTP-SHA PASS cuatro fixtures.
Primera ejecución tuvo ProtocolError de transporte S3 no reproducido: diagnóstico
y repetición completa pasaron sin cambios ni relajación de controles. Sin causa
demostrada. No día renovado, políticas nuevas, root ni servicios de datos recreados.

Request explícito de atomic en los cuatro fixtures, seguido de trabajador Qwen real
con modelo RO y cuatro jobs SUCCEEDED. Verify PASS: intent, vectors, publication,
usage, ack de control, repetición idempotente y original HTTP/SHA. Journal
1c70faf0282548499cd601f6ebe9859e: cada fixture1chunk/1batch/1request/13inputtokens,
original_retained=true. Sin texto/vector en logs ni control. Trabajador cerrado
limpiamente, contenedor/imagen conservados. No prueba aún crash/TTL largo ni búsqueda.
PR60/61/62 con checks previos y postmerge correctos.

## T006 parcial — componente SQL exacto
Consulta parametrizada por tenant ya conectado, repositorios UUID y space/perfil
completo. Intersección materializada de ACL, repositorio activo, documento vigente
sin tombstone, ancla original y publicación completa antes de ordenar por coseno.
Desempate por chunk UUID, top_k1..50, excerpt512; section conserva ruta JSONB.
Sin inferencia, contexto nuevo, escritura ni endpoint. El servicio llamante deberá
validar todos los repositorios antes de inferir y reautorizar después.
15 tests nuevos: UUID/inyección, forma/límites, NaN/Inf/norma/dimensión, parámetros
y representación privada. Suite949passed60.33s; ruff/formato/docs/negativos correctos.
Advertencia heredada httpx/TestClient. No prueba ANN ni calidad semántica.
Prueba nativa repetida después de adopción0006: PASS cuatro fixtures/dos instancias,
app/readonly, orden contra coseno Python, unpublished/ACL retirada/tombstone/binding
ausente y modelo distinto de igual dimensión. Rollback exterior y hashes intactos.
Durante desarrollo inicial se detectó section JSONB mediante42883 left(jsonb,integer);
se conserva su ruta en vez de aplicarle una función de texto. Diagnóstico público
limitado finalmente a SQLSTATE, sin mensajes SQL/valores. No error pendiente.

## T006 parcial — servicio de consulta autorizado
SearchService agnóstico al despliegue: ACL de todos los repositorios antes de
tokenizar/inferir, conexión liberada durante proveedor, contexto nuevo al terminar,
repetición ACL/perfil y validación antes de devolver hits. Sin ruta HTTP ni Torch
en API, sin nuevas migraciones/dependencias/servicios.
18 pruebas del servicio con autoridad/ACL/transacciones SQLite reales y backend
exacto sustituido (pgvector ya tiene su prueba nativa): revocación ACL/membresía/
tenant/perfil durante inferencia, contexto expirado, entrada/cota/proveedor inválidos,
traza forjada y conexiones cerradas. Suite967passed67.31s; después siete pruebas
nuevas de selección QA pasaron. El helper real está preparado, todavía NO ejecutado.
Revisión detectó resolución de extends relativa al primer compose, corregida antes
de arranque; composición validada sin iniciar dependencias.

## Consulta Qwen real del servicio y preparación de recuperación
Postmerge PR64 8fd440c: docs/lint/tests success. QA Qwen real + SQL exacto PASS
same-a/same-b/two-a/two-b, procedencia esperada y repositorio ajeno rechazado antes
del proveedor. No nuevos documentos/jobs ni texto/vector en output; cierre revocó
entrega exclusiva. No acredita HTTP, ANN, calidad ni recuperación de proceso.

Controlador de recuperación preparado: positive explícito, presupuestos de todos
antes de intents, cola limitada a versión y dos límites de hard exit real. Demora
QA35s sobre proveedor real, lease15/heartbeat5, comparación ledger/coste y cerca
vieja al retomar. Todavía NO ejecutado. Primer test del hook omitió runtime en su
objeto de prueba; corregido,14focalizados pasan. No cambio de producción.
Suite979passed68.08s,14focalizados finales3.79s, ruff/formato/docs correctos.
La espera QA no se atribuye a latencia del modelo; token de cerca viejo permanece
solo en memoria del proceso de recuperación, nunca se guarda ni imprime.

## Corrección del corpus para recuperación real
PR65 396870c integrado con cuatro checks previos/tres postmerge success.
Primer prepare sobre manifest API a75adb4c: cuatro presupuestos1chunk/16tokens
correctos; petición rechazada por control de ingesta, sin hard exit. El flujo F04
había dado de baja esos positive deliberadamente. Diagnóstico con savepoints
revertidos: los cuatro intents no existen; recursos/journal212416ed conservados.
Primer diagnóstico -c omitió /app/scripts y falló antes de abrir runtime; corregido.

Se elige positive-txt del manifest worker15bbc3e9 conservado, sin revivir documentos
ni crear corpus. Se comprueba estado/permiso de ingesta antes de leer/tokenizar
chunks. Dos pruebas nuevas: tombstone impide lectura/tokenización/intent/checkpoint,
y error desconocido no expone su cuerpo. Recuperación real todavía pendiente.

API compatible t006 cerrada/reabierta para reemplazar entrega F03 bajo lock y día
existente; HTTPS health200 tras arranque, contenedor/imagen conservados. Primer intento
de reemplazo usó ruta de lock inexistente, corregida antes de emitir entrega.
Comprobación de salud inicial apuntó8443; puerto configurado9443 verificado con TLS.
Sin root/políticas/día nuevo ni cambio de servicios de datos.

Diego aprobó «Sí, usar la conexión privada propuesta»: API->trabajador Qwen existente,
una copia del modelo, sin puerto público/terceros, CPU compartida/espera acotada y
reautorización antes de fragmentos, solo desarrollo. Registrar ADR0012 y probar
transporte antes de habilitar HTTP; la aprobación de este contrato ya existe.
Suite981passed68.73s; ruff/formato/docs correctos. Warn httpx/TestClient heredado.
