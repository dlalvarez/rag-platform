# Plan F06 — recuperación híbrida y evaluación

Alcance original autorizado ADR0010. Dependencia F05 aceptada en PR74,
merge 7f7f180d400d28203d2b20f1947d792661237251, cuatro checks HEAD y tres
postmerge correctos. [Aceptación](https://github.com/dlalvarez/rag-platform/pull/74#issuecomment-6605895334).
Diego aprobó aclarar AC-F06-03 el 2026-11-03: original recibido puede tener
versión procesada publicada; solo esta última, completa/vigente/autorizada,
puede recuperarse. No cambia estado original ni requiere migración.

## Alcance y archivos previstos

Nuevo módulo src/rag_platform/retrieval para contratos, filtros, FTS,
fusión RRF, orquestación y citation_resolver. Tests/unit separados y corpus
versionado tests/fixtures/rag-eval. Comprobadores opt-in en scripts/ops/f06,
ejecutados únicamente en ragdev01; documentos SDD/evidencia/manual.
Se reutilizan autoridad y RepositoryService F05, tabla por tenant/space y
proveedor Qwen privado aprobado. No introducir LLM generativo o reranker.

La API HTTP F05 conserva contrato y búsqueda exacta. F06 entregará primero
servicios internos y comprobadores reproducibles. Cualquier nueva superficie
HTTP o cambio de respuesta se concretará antes de activarlo bajo gobernanza
de contratos. No inventar assistant_id ni conversaciones F07.

## Recuperación y fusión

FTS PostgreSQL parametrizada, configuración simple fija para términos técnicos
ES/EN, plainto_tsquery para texto no confiable y ts_rank_cd. No aceptar nombres
de configuraciones/tablas/SQL del cliente. Verificar comandos y parámetros
con tests concretos; FTS no promete coincidencia literal de puntuación ignorada
por su parser. Describir este límite al medir.

RRF versionada: k=60, contribución1/(60 + posición) por modalidad, posiciones
desde 1, candidatos únicos por chunk y desempate estable por UUID. Dos listas
(vectorial exacta y textual), hasta 50 candidatos por modalidad, top_k 1..50.
La puntuación híbrida es una suma de rangos; no es similitud coseno.
No truncar candidatos globales antes de aplicar autorización.

Compartir el filtro materializado F05: actor/ACL/repositorio activo/documento
sin baja/pointer procesado vigente/versión PUBLISHED/ancla original/publicación
completa por space y fingerprint. Filtros opcionales internos acotados por
documentos/versiones/página/sección permitidos se aplican a ambos recorridos,
antes de ordenar y limitar. No consultas entre bases de tenants.

Primera implementación calcula FTS sobre el conjunto autorizado mediante
to_tsvector; no requiere nuevo DDL persistente. Registrar planes y latencia real.
No prometer escala ni crear GIN/migrar datos por iniciativa; si mediciones
justifican índice persistente, preparar migración/reversión/pruebas y revisar
su adopción separadamente.

## Citas y autorización

Cada resultado lleva tenant lógico del contexto, repository/document/version/
chunk/space, página/sección y start_offset/end_offset de texto normalizado.
Los offsets no son posiciones binarias del PDF/Word original.
citation_resolver recibe IDs tipados, verifica de nuevo membresía/ACL/perfil/
publicación/pointer y devuelve procedencia/extracto limitado. No token firmado
como sustituto de permiso actual; no presigned URLs ni lectura S3 necesaria.
Chunk inexistente, otra versión/tenant/repo, baja o permiso revocado deniegan
sin exponer contenido o confirmar existencia a un usuario no autorizado.

Orquestación valida todos los repositorios antes del proveedor, libera SQL
durante inferencia y autoriza de nuevo antes de construir resultados/citas.
No devolver texto ni IDs de repos no autorizados. Errores cerrados y repr
privado; logs solo metadatos operativos.

## Evaluación y puertas

Corpus técnico sintético revisado por delegación ADR0007, sin atribuir aprobación
personal nueva: >=30 preguntas ES/EN con golds identificados, términos exactos,
semántica, ambigüedad y casos imposibles. Congelar archivos/hash antes de medir;
no ajustar golds al observar resultados. Dataset y baseline versionados.

Evaluador offline determinista para métricas y negativos. Integración real
Qwen/SQL opt-in en cuatro fixtures/dos instancias, una sola copia del modelo,
sin corpus privado. Fixtures SQL temporales con rollback y huellas de historia/
vectores/publicaciones conservadas; uso real separado de ledgers sintéticos.
Recordar que fixtures de ranking no acreditan fencing real ya probado en F05.

Recall@10 >= 0.80 sobre preguntas con golds no vacíos; documentar denominador,
reporte por idioma y modalidad. Negativas/ambiguas informadas por separado,
sin fingir abstención semántica: RRF siempre puede ordenar evidencia irrelevante.
Citas 100% resolubles/autorizadas;0 fugas tenant/repo y0 versiones no publicadas.
Latencias p50/p95 y fallos con tamaño/candidatos/perfil/recursos/hash conocidos;
sin umbral de latencia inventado ni garantía general de calidad.

## Secuencia y validación

T001: plan/criterios/decisión RRF. T002: contratos/fusión/filtros y tests offline.
T003: FTS/recuperación compartida y negativos PostgreSQL. T004: citas/orquestación
y revocación durante consulta. T005: corpus/evaluador/baseline. T006: integración
real/exact-vs-hybrid/citas/aislamiento/regresión/privacidad. T007: manual,
CI/revisión/PR/merge/postmerge y aceptación. Cada entrega con diff acotado.

No cambiar esquemas/catálogos/secretos para probar ranking. Conservar documentos,
objetos, imágenes, contenedores y journals existentes. Sin main/tag/producción,
GPU/VMM/Bao root/políticas/renovación automática ni funciones F07.
