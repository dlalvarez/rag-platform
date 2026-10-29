# 06 — Recuperación, generación fundamentada y evaluación

## Contrato de consulta

Entrada validada: `AuthorizedTenantContext`, `assistant_id`, `question`, historial acotado, filtros opcionales permitidos y `request_id`. El servidor computa repositorios efectivos: `assistant.repository_links ∩ ACL(user)`; si queda vacío, respuesta de autorización/ausencia, no consulta global.

## Pipeline RAG

1. Normalización conservadora y detección de idioma; nunca convertir contenido documental en instrucciones.
2. Embedding de consulta en **mismo espacio/modelo/dimensión** que documentos indexados.
3. Búsqueda vectorial topK + búsqueda textual PostgreSQL FTS (idioma configurable); filtros por repositorios permitidos y versiones publicadas.
4. Fusión por rangos (RRF) o equivalente determinista y reranking **opcional**; deduplicar y diversificar fuentes.
5. Seleccionar fragmentos y presupuestar tokens preservando fuente, versión, página, sección y encabezados.
6. LLM recibe política de sistema y contexto no confiable delimitado. Debe reconocer insuficiencia o contradicciones.
7. Validación posterior: citas solo a chunks usados y autorizados; respuesta con referencia estable a fuente/version/página. Sin citas inventadas.
8. Guardar conversación, citas, latencias, identidad del modelo y métricas de consumo en la BD tenant; control plane solo agregados.

## Política de respuestas

- Diferenciar *no encontrado*, *evidencia insuficiente*, *fuentes contradictorias* y *respuesta fundamentada*.
- Cuando el repositorio no sustente una afirmación relevante, expresar limitación; no completar automáticamente con conocimiento general sin marcarlo.
- Las citas deben representar respaldo real, no referencias decorativas. Citas a contenido eliminado/privado deben invalidarse o respetar política de acceso histórico.
- Documentos pueden contener prompt injection ("ignora las reglas", "envía secretos"): tratarlos como datos y bloquear herramientas/acciones no autorizadas.
- Parámetros como temperatura, topK, umbrales y máximos de tokens configurables con límites seguros y versiones.

## Evaluación

- Dataset versionado en `tests/fixtures/rag-eval/` (sintético o autorizado), con consultas, repositorios, chunks esperados, casos imposibles y preguntas ambiguas.
- Métricas: recall@k, MRR/nDCG cuando haya juicios relevantes, tasa de citas válidas, faithfulness comprobada por revisión humana, abstención apropiada, latencia p50/p95, tokens/costo.
- Gates bloqueantes: **cero** evidencia de otro tenant, repositorio no autorizado o citas a objetos inexistentes; cero filtración de secretos en logs.
- Objetivo preliminar de recuperación: recall@10 >= 0.80 sobre corpus/queries aprobadas (revisable por ADR de evaluación y con baseline, no garantía universal). Para calidad generativa, comenzar con revisión humana de >=30 casos antes de fijar umbral contractual.
- Evaluación en cada cambio de parser, chunking, embedding, búsqueda, reranker, prompt o modelo LLM; reportar versiones exactas.

## Conectores/proveedores

Abstracciones `EmbeddingProvider`, `ChatModelProvider`, `Reranker`, `Retriever`, `DocumentExtractor`; fixtures deterministas para pruebas offline. Fallo de proveedor no debe desencadenar publicación parcial ni contaminación de estado entre tenants.
