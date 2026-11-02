# ADR 0011 — Perfil inicial de embeddings de desarrollo (D-06 aprobada)

**Estado:** APROBADO por Diego el 2026-11-02: «ok, adoptemos qwen».
Sustituye la elección inicial de E5-small, pausada por Diego antes de fusionar PR45,
descargar pesos o ejecutar migraciones. No se atribuye aprobación de benchmarks.
**Ámbito:** F05 original, desarrollo local en ragdev01. Sin decisión de producción.
F05-R01/P10/ADR0007 requieren esta decisión humana; ADR0010 mantiene continuidad.

## Perfil elegido

Qwen/Qwen3-Embedding-0.6B, revisión
97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3, 1024 dimensiones, coseno,
normalización L2 y salida float32. Modelo local CPU; no enviar textos a terceros.
Pesos públicos Apache-2.0; safetensors SHA256
0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd.
Congelar revisión del tokenizador y hashes de todos los artefactos en manifest.

Consulta con instrucción fija oficial:
Instruct: Given a web search query, retrieve relevant passages that answer the query
seguida de salto de línea y Query: y la consulta. Documento sin instrucción.
Pooling del último token válido y L2 según implementación oficial; preservar EOS
y padding correctos del tokenizador fijado. No copiar mean pooling/prefijos de E5.

Capacidad publicada: 32768 tokens. Límite operativo inicial: 512 tokens por entrada,
incluyendo instrucción/especiales; batch máximo 4, un trabajo de inferencia simultáneo.
Estas cotas permiten comparar coste en la VM; no cambian la capacidad del modelo.
No truncar: exceso falla cerrado. Otra cota/instrucción/dimensión/precisión/revisión
crea perfil y espacio nuevos, con evidencia; no sobrescribir embeddings previos.
No reducir dimensiones ni cuantizar antes de medir la referencia float32 en CPU.

Artefactos compartidos públicos RO, descarga explícita verificada, sin pickle,
trust_remote_code o red durante inferencia. Dependencias opcionales fijadas en entorno
separado; no actualizar silenciosamente el lock o servicios F00..F04.
Contenido, vectores y caches de usuario permanecen aislados por tenant.

## Recursos y alternativas

ragdev01 tiene 2 vCPU/16 GiB. Diego permite considerar 4 vCPU si las mediciones
demuestran necesidad y beneficio; no se ha cambiado VMM ni se promete duplicar capacidad.
Mantener límites, medir RSS/frío/caliente/CPU y efecto sobre servicios/NAS.
Más contexto aumenta coste y no implica mejor recuperación ni mejores citas.

E5-small (384/512/MIT) queda como referencia de eficiencia, no perfil activo.
BGE-M3 (1024/8192/MIT) es otra alternativa no seleccionada.
API comercial, nuevas GPU/servicios y selección de producción no están autorizados.
Reconocimiento de marca o dimensiones no acreditan calidad.

## Gates de evaluación

Congelar corpus sintético ES/EN, gold y SHA antes de medir. Recall@3 >= 0.8 por
idioma, salida finita/dimensión exacta, cero cruces tenant/repo. El fixture pequeño
valida integración, no basta para calidad de dominio ni aceptación F06.
Para comparar modelos usar primero los mismos fragmentos compatibles, después medir
contexto distinto por separado. Documentar latencia p50/p95, indexación, RSS, frío,
caliente y concurrencia limitada, sin inventar SLA ni resultados en nuestra VM.
Si falla, conservar recursos/evidencia y plantear ajuste/alternativa antes de aceptar.

## Datos, publicación y reversión

vector(1024), HNSW/cosine por espacio en cada DB tenant. Nombres por UUID validado,
DDL confiable y privilegios mínimos. Exacto como referencia ANN/ACL.
Perfil inmutable; modelo nuevo necesita vectores/índice nuevos, conserva el anterior.
Adaptador real y fake usan validación común; fake no acredita calidad semántica.

F05 evoluciona explícitamente esquema/perfil desde F04, sin modificar migraciones
históricas. Conservar ancla original de upload/replay/download F03; pointer publicado
solo a versión completa. Publicación por versión+space atómica, guards/fencing/ACL/
membresía/tombstone vigentes, sin índice parcial recuperable ni ACID entre bases.
Reversión operativa sin purge/downgrade: no activar espacio fallido, conservar datos.

## Fuentes verificadas y decisión

- [Ficha oficial Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B):
  licencia, dimensión, contexto, instrucciones y pooling.
- [Config fijada](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/blob/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/config.json).
- [Código oficial](https://github.com/QwenLM/Qwen3-Embedding).
- [E5-small](https://huggingface.co/intfloat/multilingual-e5-small).
- [pgvector](https://github.com/pgvector/pgvector/blob/v0.8.7/README.md).

Metadatos públicos consultados desde ragdev01 confirman revisión/1024/32768/
Apache-2.0 y huella LFS. Descargar/verificar no equivale a benchmark aprobado.
Diego eligió Qwen 0.6B tras revisar calidad, dimensiones, recursos y cambio futuro.
Esta decisión sustituye E5; no fusionar PR45 con la elección anterior.
