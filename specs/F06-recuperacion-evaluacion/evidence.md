# Evidencia F06

## Planificación

Dependencia F05 aceptada en PR74, merge 7f7f180d400d28203d2b20f1947d792661237251.
Cuatro checks HEAD y tres postmerge correctos, revisión propia delegada ADR0007.
El2026-11-03 Diego aprobó aclarar AC-F06-03: solo versiones publicadas completas,
conservando estado de recepción del original. Sin migración por esta aclaración.

Plan y tareas preparados antes de implementar. RRF con k=60/50candidatos por modalidad,
FTS simple y contratos internos registrados. No se ha implementado ni probado
todavía la recuperación híbrida, citas o evaluación F06. No hay métricas F06.
El Recall@3=1.0 del corpus F05 no es evidencia de aceptación F06.

## T002 — contratos y fusión offline

Contratos internos inmutables para filtros, referencias tenant/space/repo/doc/
versión/chunk, extracto y offsets normalizados, con repr privado. RRF versionada
k=60, hasta50 candidatos por modalidad y top_k1..50. Rechaza duplicados dentro
de modalidad, evidencia contradictoria del mismo chunk, mezcla tenant/space
y puntuaciones no consistentes con rangos. Un chunk compartido aporta una vez
por modalidad; desempate por UUID y sin modificación de entradas.

61 pruebas offline correctas en0.30s: promoción de evidencia compartida,
simetría, límites, desempates, deduplicación segura, provenance/offsets inválidos,
filtros acotados y privacidad. No SQL/inferencia/HTTP/DDL ni métricas semánticas.
Ruff focalizado correcto; validación completa e integración pendientes.

Validación completa T002:1188passed,1warning heredado,87.61s; runnerexit0/93.78s.
Journal d9ffc7edf033475e93fa03ccc7ebc586. HEADbase55bf9e3 con cambios T002
sin commit durante la corrida; no se modificó código durante la batería.
Ruff completo/formato275archivos/docs/diff correctos. Revisión propia: referencias
incluyen tenant/space, mismochunk exige procedencia/texto idénticos, un aporte
por modalidad y score consistente con rangos. Sin revisión independiente.

## T003 — componente SQL y comprobador preparado

Mismo conjunto permitido materializado F05, ampliado por opción explícita para
texto/offsets sin cambiar proyección por defecto. Filtros tipados se materializan
antes de dos listas limitadas a50candidatos; vector exacto y FTS simple con
plainto_tsquery/ts_rank_cd unidos en una sentencia/snapshot. Query/config/perfil/
UUID parametrizados o constantes confiables; sin identificadores de cliente.
RRF conserva ambos rangos y devuelve procedencia, rechazando filas inválidas.

114pruebas focalizadas PASS3.27s incluyendo F05exact/ANN y contratos F06.
Comprobador SQL preparado, aún no ejecutado: reutiliza publicación/retrieval F05
con fixtures y DDL siempre revertidos, prueba FTS SELECT, filtros metadata,
app/readonly, ACL/publicación/baja/perfil y huellas/control intactos.
No modelo ni S3, no esquema persistente. Manual ops/f06/README.md.
No acredita aún cita autorizante, recuperación semántica o aceptación T003/F06.

Validación completa T003:1209passed/1warning heredado en88.75s;
runnerexit0/95.05s, journal6320affea5854212b7d7a41dc18697a1.
Ruff/formato278/docs/diff/composeconfig correctos. Código sin cambios durante
la corrida. Revisión propia de filtros comunes/proyección F05 por defecto,
parámetros FTS/JSON/vector y una sentencia/snapshot; prueba real aún pendiente.
PR76/T002 integrado510ac6f5a5ac62257b116345ccfa127712de5307,4pre/3postSUCCESS.

## T004 — servicio híbrido y citas preparados

HybridService reutiliza preflight de repositorios/perfil y la misma validación
de tokenización/embeddings extraída de SearchService F05. Libera conexiones
durante inferencia y autoriza de nuevo antes de recuperar. La API F05 permanece
exacta. Citation resolver exige tenant/repo/doc/versión/chunk/space coincidentes,
permisos actuales y publicación vigente completa; offsets de texto normalizado.

65pruebas focalizadas PASS11.72s: autoridad/ACL reales offline, revocación
durante inferencia, contexto vencido, referencias ajenas/inexistentes/perfil,
trazas falsas, procedencia contradictoria y errores cerrados, más regresión
SearchService F05. Comprobador SQL ampliado para citas válidas y fabricadas,
bajas/ausencia de publicación/ACL sin cambios persistentes; aún no ejecutado.
Sin HTTP nuevo, modelo generativo, migración ni aceptación F06.

## T003 — PostgreSQL real completado

PR77 integrado c9f1d01fbb5929aba71cb56e417184588d718cf1,4pre/3postSUCCESS.
Journal63eb55824f8242939eeaf0733f81ef05 exit0/46.34s. Cuatro tenants/dos
instancias,40comparaciones y4pruebas FTS/4metadata correctas; app/readonly,
ACL/publicación/baja/perfil, historia/control/DDL y rollback intactos.
Sin Qwen ni cambios persistentes. No acredita calidad de recuperación F06.

Validación completa T004:1235passed/1warning heredado en97.96s,
runnerexit0/104.43s, journal0b40d97f4f3e4f5eb3f6bc3b29ecf72b.
Ruff/formato281/docs/diff correctos. Fuente fija durante la corrida.
Revisión propia: mismo preflight/inferencia F05, autoridad nueva tras modelo,
resolver con filtros compartidos y referencia exacta; no revisión independiente.
Ejecución SQL ampliada de citas y consulta real autorizada con Qwen pendientes.

## T005 — corpus y métricas congelados antes de inferencia

Corpus técnico nuevo:16documentos ficticios/40consultas,20ES/20EN;
16directas/8semánticas/8comandos/4ambiguas/4negativas. SHA256
35976933e799d23ca87e4718dceedab0f8989b3204c881dc4972294d4b8b4bb7.
Golds definidos antes del modelo, un chunk512/64 por documento completo.
Revisión propia de cobertura/target/idioma/comandos, bajo ADR0007;
no se atribuye aprobación personal nueva ni calidad medida todavía.

Evaluador offline:document_recall_at_10 sobre36preguntas con gold no vacío,
negativas aparte sin falsa abstención, desglose idioma/tipo y percentiles
nearest-rank con denominador explícito. Rechaza resultados fuera del corpus,
gold inválido y muestras no finitas.27pruebas PASS0.26s.
Módulo independiente sin cambios SQL/servicio/DDL/API; suite completa anterior
1235PASS permanece como base, CI ejecutará1262. No se repite localmente sin
cambio de runtime previo. Medición Qwen/SQL/baseline real aún pendiente;
T005/F06 no aceptadas por crear fixtures o métricas.

## T004 — resolución SQL real completada

PR78 integradoe068c5c7fe58dbf3f0e8bde6a9dbb8d32ce30eb8,4pre/3postSUCCESS.
Journalb5dcd20e39f246c09ef3fbea14bd412c exit0/75.01s:
4fixtures/40comparaciones/4FTS/4metadata/264comprobaciones de citas correctas.
Referencias fabricadas, estado no publicado/baja/ACL y roles app/readonly
probados; historia/control/DDL y rollback intactos. Consulta del HybridService
con identidad real y Qwen aún pendiente; no se declara T004 completa.

## T006 — baseline real preparado, sin ejecutar

Script/overlay Qwen con corpus SHA35976933...,44operaciones reales antes de SQL
y una copia del modelo. Por fixture:40consultas top10 vector/híbrido,400citas,
8comandos FTS, negativos y rollback. Métricas/baseline reales se guardarán antes
del gate; verificado solo si cuatro fixtures pasan recall/citas/FTS/rollback.
Latencias de modelo y SQL separadas; no representan HTTP.

39pruebas focalizadas PASS1.99s incluyendo27del evaluador y12de preparación/
contabilidad/gates. Primera validación compose sin variable de journal fue
rechazada como corresponde; interpolación config--quiet validada después
con ruta de prueba, sin ejecutar contenedor. Sin cambios de runtime del servicio.
Modelo/SQL y baseline aún no ejecutados; no usar métricas simuladas como calidad.

## T006 — consulta autorizada real preparada

Nuevo comprobador de HybridService sobre originales sintéticos ya publicados.
Reutiliza selección/scope/perfil F05 y entrega limitada del worker, sin bootstrap/
migrator/día en runtime. Identidad global y ACL reales, filtro documento/versión,
citas actuales y referencias ajenas/fabricadas; añade regresión exacta F05 tras
extraer su método de inferencia. Ocho consultas reales previstas en un único
modelo, cero extra por denegaciones o resolver. No escribe documentos/jobs.

Ruff/composeconfig/docs/diff validados; ejecución real pendiente tras revisión/
CI/integración/postmerge y después del baseline, sin dos Qwen simultáneos.
No se repite suite local por este comprobador opt-in sin cambio del servicio;
CI sigue ejecutando toda la batería. No se declara resultado todavía.
