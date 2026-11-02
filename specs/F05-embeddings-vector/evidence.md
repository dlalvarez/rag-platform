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
