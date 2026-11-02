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
