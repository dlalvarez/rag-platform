# ADR 0011 — Perfil inicial de embeddings de desarrollo (propuesta D-06)

**Estado:** PROPUESTO; requiere decisión expresa de Diego. No es un ADR aprobado.
**Ámbito:** F05 original, desarrollo en ragdev01; no selecciona proveedor de producción.
F05-R01 exige selección por ADR; P10/ADR0007 reservan arquitectura a Diego.
La continuidad ADR0010 autoriza planificar la fase, no fingir esta decisión.

## Propuesta concreta

Evaluar y adoptar como baseline de desarrollo intfloat/multilingual-e5-small,
revisión 614241f622f53c4eeff9890bdc4f31cfecc418b3, embeddings de384 dimensiones,
métrica coseno y normalización L2. Tokenizador/revisión, prefijos query: y passage:,
límite512 tokens incluyendo prefijo/especiales y dtype se congelan en el space.
No truncar silenciosamente: entrada excedida falla de forma cerrada; otra configuración
de chunking crea otra versión sin sustituir original/chunks anteriores.

Modelo local en CPU, sin enviar textos a terceros ni contratar API. Artefacto público
safetensors y tokenizer con revisión/hash verificados; no trust_remote_code, pickle
o descargas durante inferencia. Pesos compartidos RO son públicos; contenidos/vectores
y caches de usuario siguen aislados por tenant. Sin servicio/GPU/plataforma nuevos.
Dependencias de inferencia se fijarán aparte, sin upgrades silenciosos del lock actual.

Es una propuesta por el presupuesto de la VM (2vCPU/16GiB), no un benchmark realizado
ni una afirmación de calidad/latencia. Batch inicial acotado y un trabajo simultáneo;
medir RSS/CPU/frío/caliente antes de aceptar. No cambiar producción por este ADR.

## Alternativas para la decisión

| Opción | Hecho verificable | Implicación a evaluar |
|---|---|---|
| E5-small local propuesto |384 dimensiones, límite512, MIT, multilingüe | baseline CPU pequeño; calidad español/inglés y latencia aún sin medir |
| BAAI/bge-m3 local |1024 dimensiones, contexto8192, MIT, multilingüe | otra dimensión/espacio y evaluación de recursos; no activar sparse/ColBERT/F06 |
| API externa configurable | proveedor separado del core según arquitectura | requiere decisión de salida de textos/coste/credencial y benchmark; no seleccionada |

Ninguna alternativa está aprobada por esta tabla. No mezclar modelo/dimensión en un
índice. Otro modelo/revisión/tokenizador/normalización crea space nuevo y reindexación,
sin sobreescribir vectores incompatibles ni borrar el espacio anterior.

## Gate de evaluación después de la decisión

Corpus sintético ES/EN de temas SQL/PostgreSQL/RAG, con pares relevantes y negativos,
mismas frases en tenants/repos autorizados y no autorizados. Congelar manifest/dataset
antes de ejecutar; medir top-k exacto/ANN, recall por idioma, fallos/límites y recursos.
Criterio inicial del fixture: recall@3 >=0.8 por idioma, cero cruces y dimensiones/
valores finitos correctos. No confundir este umbral de desarrollo con evaluación F06
ni SLA. Si falla calidad/capacidad, no publicar ni declarar MVP: documentar resultados
y proponer alternativa bajo D-06. No inventar medidas ni elegir comercial sin benchmark.

## Datos, publicación y reversión

vector(384) e HNSW cosine en tabla tipada por space dentro de cada DB tenant,
nombres solo de UUIDs/DDL confiable. El perfil queda inmutable; baseline exacto sirve
para contrastar ANN y ACL. La reindexación nueva no interrumpe el espacio previo.
Adaptador local y fake determinista de tests usan el mismo contrato de validación.

F05 evoluciona explícitamente perfil/esquema desde F04. Conservar ancla original para
upload/replay/download F03, mientras current_version_id se usa solo para resultado
publicado completo. Publicación/bindings por versión+space transaccionales y con
fencing, ACL/membresía/tombstone vigentes; ningún índice parcial es recuperable.
No purge ni downgrade. Reversión operativa: no activar espacio nuevo; mantener anterior
y toda evidencia/datos. Migraciones históricas F01..F04 no se reescriben.

## Fuentes verificadas (2026-11-02)

- [Ficha oficial E5-small](https://huggingface.co/intfloat/multilingual-e5-small):
  dimensión, límite, prefijos y licencia. Su benchmark publicado no mide nuestro corpus.
- [Config de revisión propuesta](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/config.json).
  Metadatos públicos consultados desde ragdev01 confirman384/max_positions512/MIT y
  model.safetensors disponible; no se descargaron pesos.
- [Ficha oficial BGE-M3](https://huggingface.co/BAAI/bge-m3).
- [pgvector0.8.7](https://github.com/pgvector/pgvector/blob/v0.8.7/README.md):
  búsqueda exacta, vector tipado y HNSW/cosine; no actualizar la extensión de F00.

## Decisión pendiente

Diego confirma si este perfil local de desarrollo y sus gates son el camino elegido,
o si se prepara otra alternativa. Registrar su respuesta antes de cambiar este estado
a aprobado o crear el esquema/índice del modelo. No atribuir aprobación por silencio.
