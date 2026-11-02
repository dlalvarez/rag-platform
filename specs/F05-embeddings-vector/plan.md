# Plan F05 — embedding spaces y búsqueda vectorial

Alcance original autorizado mediante ADR0010, sin cambiar roadmap/requisitos.
Dependencia F04 aceptada en PR44, develop45726ec6477370a3fb466a12dd77488b3b1228e9
y [postmerge](https://github.com/dlalvarez/rag-platform/pull/44#issuecomment-6575586701).
Toda ejecución manual en ragdev01. D-06 aprobado por Diego en ADR0011 para desarrollo; gates aún pendientes.

## Entregas y dependencias

T001 formaliza propuesta ADR/benchmark. T002 implementa contrato de provider y fake
determinista offline, independiente de elegir modelo comercial/local; no acredita
calidad semántica. T003 evoluciona esquemas/espacios tipados tras aprobar D-06.
T004 embedding por lotes, límites/retries/usage. T005 publicación/reindexación seguras.
T006 servicio vectorial autorizado exacto/ANN. T007 operación/manual y ejemplo real
opt-in. T008 aceptación dos topologías/CI/revisión/postmerge. Ver tareas y checklist.

La etiqueta BORRADOR de la spec original no requiere otra orden para planificar:
ADR0010 autoriza continuidad. El ADR obligatorio de F05-R01 conserva decisión humana, ya registrada para este
perfil de desarrollo; no interpretar esa aprobación como benchmark exitoso. Trabajos agnósticos y preparación
de pruebas pueden avanzar sin tocar datos ni resolver D-06 unilateralmente.

## Perfil e inferencia

Congelar provider/model/revisión, tokenizer y su revisión, dimensión, métrica, dtype,
normalización, prefijos y límite de tokens en fingerprint inmutable de space.
Contrato: lotes acotados, orden/cantidad exactos, números reales finitos y dimensión
exacta; rechazar NaN/Inf/cero incompatible/mismatch antes de persistir el lote.
No texto/vectores en excepciones/logs/control; solo código cerrado e IDs/uso agregado.
Inputs del worker salen solo de chunks autorizados de su tenant; revalidación antes
de I/O y confirmación, reuse de guards/fencing/lease sin fallback administrativo.

Fake determinista de CI no descarga pesos ni llama servicios; perfiles distintos no
se confunden aunque coincida dimensión. Ejemplo real opt-in con modelo aprobado,
artefactos/licencia/hash registrados, paquetes opcionales fijados y sin GPU nueva.
No presentar providers fake como evidencia semántica. Medir ES/EN y capacidad en VM.

## Datos y migración

Una DB por tenant, control solo metadata/jobs/uso agregado, sin contenido/vectores.
No joins entre bases. Definiciones/migraciones F01..F04 congeladas; nuevos heads y
perfiles explícitos, rollback físico/FAILED honesto/recovery/repetición en ambas
topologías antes de adopción persistente. Sin downgrade ni nuevo tenant automático.

knowledge.embedding_spaces y bindings/registro de publicación por versión+space;
tabla vector(dimension) e índice HNSW/cosine por space, DDL propietario y UUID validado,
jamás tabla/dimensión/endpoint enviados por cliente. Límites de espacios/DDL; app y
readonly reciben solo grants necesarios, migrator/instalación fuera del runtime.
Compatibilidad F03/F04 no se logra aceptando heads desconocidos: API nueva opt-in
antes de adopción, igual que F04. Conservar roles/refs/secretos existentes cuando viable.

F04 ancla current_version_id al ORIGINAL y hace inmutables resultados/chunks.
F05 debe introducir ancla original explícita/reutilizar procedencia sin romper upload,
replay, show y descarga: pointer de publicación puede conmutar a procesado completo,
pero objeto original sigue accesible solo con ACL. Diseñar/testear el contrato físico
antes de DDL; no eliminar guard F04 sin equivalente F05 ni reescribir originales.

## Worker y publicación

Jobs EMBED por tenant/actor/version/space con idempotencia por esa identidad;
evolución aditiva de envelope control sin texto/vector, manteniendo INGEST anteriores.
No fingir commit entre control/tenant. Publicación inicial requiere todos los chunks/
vectores/uso/auditoría y contexto vigente; confirmar binding/publication y pointer
atómicamente en tenant, ack control después. Crash commit-before-ack reconcilia sin
coste/embedding duplicado. Dependencias reintentan con cota/backoff; errores de perfil/
dimensión terminales, sin parcial visible.

Un documento publicado en space viejo sigue recuperable mientras se indexa el nuevo.
No basta state PUBLISHED global para consultar space incompleto: filtro/binding de
publicación completo por versión+space además de repo/ACL/tombstone/pointer vigente.
Reindexar misma identidad es no-op o recuperación, no sobrescribe otro modelo.
Baja/revocación entre lotes o durante confirmación impide publicación tardía.
Usage local real (tokens/requests/tiempo de proveedor), sin billing/planes F11.

## Consulta y operación

Servicio parametrizado recibe contexto servidor verificado, repos lógicos autorizados,
space compatible y top_k acotado. Embedding query usa mismo perfil/prefijo que índice.
SQL filtra ACL/estado antes de recuperar; validar cómo HNSW mantiene cobertura del filtro
y comparar con exacto, sin asumir que postfiltrar siempre entrega top-k correcto.
No URI/secret_ref/table/vector arbitrarios del cliente ni contenido en control.
F05 no incorpora asistente/chat F07 ni híbrida/reranking/FTS F06. Detallar superficie
HTTP/operación antes de habilitar ruta propuesta docs07, sin inventar assistant F07 o
alterar un contrato rector unilateralmente.

Batería offline/SQL/real opt-in, cuatro fixtures autorizadas y corpus nuevo explícito,
conservar previas. CI, revisión delegada honesta, PR hacia develop y postmerge antes
de aceptar fase. Sin main/tag/prod/visibilidad/purge, nuevas políticas Bao/root por
iniciativa ni claims de backup/restore no ensayados.


## T004 incremental — cola de ejecución antes de inferencia
Primera entrega: consumidor EMBED separado, envelope inmutable con espacio/perfil,
idempotencia, lease/heartbeat, retry acotado y fence completo. Reusar algoritmo de
cola INGEST mediante hooks internos manteniendo sus defaults y pruebas históricas.
Pruebas offline y PostgreSQL con rollback de cruces kind/space/tenant, token viejo,
backoff/agotamiento y códigos privados rechazados. No arranca worker ni adopta0007.
Luego conectar procesamiento/usage/publicación con contratos tenant explícitos.
