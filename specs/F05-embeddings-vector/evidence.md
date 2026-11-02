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
