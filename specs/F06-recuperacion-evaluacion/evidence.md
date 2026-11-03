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
Ruff completo/formato275 archivos/docs/diff correctos. Revisión propia: referencias
incluyen tenant/space, mismochunk exige procedencia/texto idénticos, un aporte
por modalidad y score consistente con rangos. Sin revisión independiente.

## T003 — componente SQL y comprobador preparado

Mismo conjunto permitido materializado F05, ampliado por opción explícita para
texto/offsets sin cambiar proyección por defecto. Filtros tipados se materializan
antes de dos listas limitadas a50candidatos; vector exacto y FTS simple con
plainto_tsquery/ts_rank_cd unidos en una sentencia/snapshot. Query/config/perfil/
UUID parametrizados o constantes confiables; sin identificadores de cliente.
RRF conserva ambos rangos y devuelve procedencia, rechazando filas inválidas.

114 pruebas focalizadas PASS3.27s incluyendo F05exact/ANN y contratos F06.
Comprobador SQL preparado, aún no ejecutado: reutiliza publicación/retrieval F05
con fixtures y DDL siempre revertidos, prueba FTS SELECT, filtros metadata,
app/readonly, ACL/publicación/baja/perfil y huellas/control intactos.
No modelo ni S3, no esquema persistente. Manual ops/f06/README.md.
No acredita aún cita autorizante, recuperación semántica o aceptación T003/F06.

Validación completa T003:1209passed/1warning heredado en88.75s;
runnerexit0/95.05s, journal 6320affea5854212b7d7a41dc18697a1.
Ruff/formato278/docs/diff/composeconfig correctos. Código sin cambios durante
la corrida. Revisión propia de filtros comunes/proyección F05 por defecto,
parámetros FTS/JSON/vector y una sentencia/snapshot; prueba real aún pendiente.
PR76/T002 integrado 510ac6f5a5ac62257b116345ccfa127712de5307,4pre/3postSUCCESS.

## T004 — servicio híbrido y citas preparados

HybridService reutiliza preflight de repositorios/perfil y la misma validación
de tokenización/embeddings extraída de SearchService F05. Libera conexiones
durante inferencia y autoriza de nuevo antes de recuperar. La API F05 permanece
exacta. Citation resolver exige tenant/repo/doc/versión/chunk/space coincidentes,
permisos actuales y publicación vigente completa; offsets de texto normalizado.

65 pruebas focalizadas PASS11.72s: autoridad/ACL reales offline, revocación
durante inferencia, contexto vencido, referencias ajenas/inexistentes/perfil,
trazas falsas, procedencia contradictoria y errores cerrados, más regresión
SearchService F05. Comprobador SQL ampliado para citas válidas y fabricadas,
bajas/ausencia de publicación/ACL sin cambios persistentes; aún no ejecutado.
Sin HTTP nuevo, modelo generativo, migración ni aceptación F06.

## T003 — PostgreSQL real completado

PR77 integrado c9f1d01fbb5929aba71cb56e417184588d718cf1,4pre/3postSUCCESS.
Journal 63eb55824f8242939eeaf0733f81ef05 exit0/46.34s. Cuatro tenants/dos
instancias,40 comparaciones y4 pruebas FTS/4metadata correctas; app/readonly,
ACL/publicación/baja/perfil, historia/control/DDL y rollback intactos.
Sin Qwen ni cambios persistentes. No acredita calidad de recuperación F06.

Validación completa T004:1235passed/1warning heredado en97.96s,
runnerexit0/104.43s, journal 0b40d97f4f3e4f5eb3f6bc3b29ecf72b.
Ruff/formato281/docs/diff correctos. Fuente fija durante la corrida.
Revisión propia: mismo preflight/inferencia F05, autoridad nueva tras modelo,
resolver con filtros compartidos y referencia exacta; no revisión independiente.
Ejecución SQL ampliada de citas y consulta real autorizada con Qwen pendientes.

## T005 — corpus y métricas congelados antes de inferencia

Corpus técnico nuevo:16 documentos ficticios/40 consultas,20ES/20EN;
16directas/8semánticas/8 comandos/4ambiguas/4negativas. SHA256
35976933e799d23ca87e4718dceedab0f8989b3204c881dc4972294d4b8b4bb7.
Golds definidos antes del modelo, un chunk512/64 por documento completo.
Revisión propia de cobertura/target/idioma/comandos, bajo ADR0007;
no se atribuye aprobación personal nueva ni calidad medida todavía.

Evaluador offline:document_recall_at_10 sobre36 preguntas con gold no vacío,
negativas aparte sin falsa abstención, desglose idioma/tipo y percentiles
nearest-rank con denominador explícito. Rechaza resultados fuera del corpus,
gold inválido y muestras no finitas.27 pruebas PASS0.26s.
Módulo independiente sin cambios SQL/servicio/DDL/API; suite completa anterior
1235PASS permanece como base, CI ejecutará1262. No se repite localmente sin
cambio de runtime previo. Medición Qwen/SQL/baseline real aún pendiente;
T005/F06 no aceptadas por crear fixtures o métricas.

## T004 — resolución SQL real completada

PR78 integrado e068c5c7fe58dbf3f0e8bde6a9dbb8d32ce30eb8,4pre/3postSUCCESS.
Journal b5dcd20e39f246c09ef3fbea14bd412c exit0/75.01s:
4 fixtures/40 comparaciones/4FTS/4metadata/264 comprobaciones de citas correctas.
Referencias fabricadas, estado no publicado/baja/ACL y roles app/readonly
probados; historia/control/DDL y rollback intactos. Consulta del HybridService
con identidad real y Qwen aún pendiente; no se declara T004 completa.

## T006 — baseline real preparado, sin ejecutar

Script/overlay Qwen con corpus SHA35976933...,44 operaciones reales antes de SQL
y una copia del modelo. Por fixture:40 consultas top10 vector/híbrido,400 citas,
8 comandos FTS, negativos y rollback. Métricas/baseline reales se guardarán antes
del gate; verificado solo si cuatro fixtures pasan recall/citas/FTS/rollback.
Latencias de modelo y SQL separadas; no representan HTTP.

39 pruebas focalizadas PASS1.99s incluyendo27del evaluador y12de preparación/
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

## Baseline Qwen/SQL real completado

PR80 integrado a4d01bed310adc0ed3aaf7dd9afa33e271a39437, cuatro checks HEAD
y tres postmerge correctos. Journal ac2b8e1743994b4c9bed1aa5a0573126,
exit0 en361.21s; baseline.json y verified.json conservados.
44 operaciones reales/2281 tokens de entrada, calculados una vez antes de SQL.
Cuatro fixtures: recall@10 vectorial e híbrido=1.0 por idioma,400 citas válidas
y8 comandos FTS por fixture, cero fallos y rollback/historia/control intactos.
Total1600 citas/32 comprobaciones FTS. Ambos modos alcanzaron1.0; este corpus
no demuestra una mejora de recall híbrido frente al vectorial.

Cuatro negativas por fixture devolvieron resultados autorizados, según baseline:
no cuentan en el denominador36 ni prueban abstención. Citas válidas acreditan
procedencia y acceso, no respuesta a una pregunta sin evidencia.
El corpus y los golds no cambiaron tras medir; hash35976933... conserva su versión.

Latencia inferencia40 consultas: p50=2358.87 ms,p95=3361.46 ms.
Componente SQL híbrido40 consultas/fixture: p50=53.79..62.83 ms,
p95=111.91..400.69 ms. Incluye construcción/validación/ejecución del componente;
no es tiempo puro del servidor SQL ni HTTP. El máximo vectorial observado
fue8053.46 ms; una pasada no establece SLA ni capacidad de producción.
Ver [baseline versionado](baseline-v1.json), que conserva todos los valores,
denominadores, negativos, corpus/perfil y commit de fuente.

## HybridService con identidad real y regresión F05 completados

PR81 integrado 09eb86159211e5d91f0b4ed924d512adf8c3d791, cuatro checks HEAD
y tres postmerge correctos. Journal 7e04eee3dac24d269d825a0fb37bde66,
exit0 en56.42s. Cuatro tenants/dos instancias, identidad/ACL actuales:
4 consultas híbridas filtradas a originales sintéticos publicados,4 citas
correspondientes y12resultados exactos F05 también resueltos.
8 operaciones reales/184 tokens, cero operaciones extra por denegaciones o citas.
Referencias de otro tenant, chunk fabricado y repo ajeno rechazados.
Entrega limitada cerrada/revocada, sin bootstrap ni mutación documental.

Privacidad inicial: logs del baseline y ambas instancias PostgreSQL sin los
marcadores documentales F06/F04 ensayados ni patrones Bearer. Comprobación final
de logs/regresión/cierre aún pendiente; no se afirma detector universal de secretos.

## Diagnóstico y corrección de transporte durante regresión final

La regresión4e261ea651884a0fab74f691846a9e1a falló F02/NewConnectionError:
terminó15:05:30UTC y la API empezó a escuchar15:05:38UTC. Se lanzó antes de
disponibilidad; se confirmó luego /healthz HTTPS200. Una sonda auxiliar usó
por error /health y recibió404; no es fallo del endpoint de salud real.

Repeticióna8ecbd8516ee49cb80a9063991d7ba22 superó F02 y falló
same-a/S3 ProtocolError. Diagnóstico de lectura68bc0f454e9648128f1c41f60c8f6a1a:
HEAD/GET/LIST propios200 y denegaciones ajenas403 reales antes de un
FOREIGN/list_objects sin respuesta, ProtocolError/RemoteDisconnected.
No se observó acceso ajeno. Se registraron solo método/estado/longitud y clases
de excepción, sin URLs, cuerpos ni claves. Diagnóstico inicial4d29f756...
falló por ruta de imports del comprobador; corregida sin cambiar datos.

StorageTarget prepara ahora un reintento de lectura GET/HEAD como máximo,
sin reintentar conexión/TLS, otros errores, status ni escrituras. Un fallo
persistente sigue cerrado. PUT/POST/DELETE/PATCH no se reenvían.
PoolManager procesa redirecciones fuera del Retry del pool; se desactiva
su seguimiento para conservar el endpoint aprobado por catálogo.
Sin cambio de dependencias, credenciales, permisos, datos o contrato HTTP.

18 pruebas focalizadas PASS0.51s sobre el bucle urllib3 real con I/O simulado:
GET/HEAD, segundo fallo, escrituras, denegaciones/status/redirects y TLS/connect.
El primer intento de tests con sockets locales fue bloqueado por el guard
offline; se sustituyó el I/O sin modificar ni desactivar ese guard.
El test301 detectó el seguimiento de redirects del manager y motivó la
corrección explícita; no se relajó la aserción. Suite completa/integración y
regresión S3 real corregida todavía pendientes; F06 no se acepta con esta puerta abierta.

Suite completa del arreglo:1292passed/1warning heredado en93.98s,
runnerexit0/99.81s; journal eb825146c1dd44f1aa69c955d58e8f3a.
Fuente fija durante la corrida. Ruff/formato287/docs/diff correctos.
Overlays F06 preparados para que API/comprobador importen el código revisado
en solo lectura sobre dependencias de imágenes conservadas; no confundir
prueba de imagen antigua con prueba del arreglo. Hash/import/sinTorch y
regresión S3 real deben pasar después de revisión/CI/integración/postmerge.

Revisión adicional del reintento: urllib3 registra repr de la excepción al
repetir. El pool HTTPS ahora convierte errores de lectura/protocolo HTTP a
STORAGE_READ_FAILED antes del bucle de retry, sin conservar payload en el
mensaje. No convierte errores TLS/conexión en lecturas reintentables.
Tres pruebas de privacidad añadidas: ProtocolError, RemoteDisconnected y
ReadTimeoutError con canaries privados nunca aparecen en DEBUG/warnings ni
en la excepción final.21 pruebas focalizadas PASS0.79s. Se repite suite completa
por este cambio de runtime; CI del HEAD anterior no acredita esta ampliación.

Validación final de la sanitización:1295passed/1warning heredado en91.31s,
runnerexit0/97.10s, journal afbd409c3f0b44fbaf93147a7aefcf69.
Ruff/formato287/docs/diff correctos, sin cambios de código durante la batería.
Esta fuente reemplaza al HEAD anterior para la revisión/CI del mismo PR.

## Arreglo integrado y regresión final completada

PR82 integrado 54b4c9684044fc179d7766158e11bd3ae507b31f; HEAD
f9c36e3aa62888f527dec8042070ef8ca0278fe7 con cuatro checks y merge con tres
checks postmerge correctos. Revisión propia delegada, sin revisión independiente.

API t009/herramientas t006 con fuente RO:105 módulos importados desde /app/src,
SHA manifiesto 95f988c4f4db53938f19ceb0f40fc4f6a358a55d5f006cfc09a20bda9732d511
idéntico al checkout, Minio7.2.20/urllib3 2.8.0, Torch ausente, sin red/secretos.
Contenedor nuevo rag-f06-api-source-t010, mismo puerto/límites; anterior retenido.
Salud HTTPS /healthz200 confirmada tras12 sondas antes de emitir nueva entrega F04.

Journal 4fb9bbd4bda24235bb401a7c753051a2 exit0/37.58s: F02 OIDC/contexto;
cuatro fixtures SQL/TLS/vector/roles/CONNECT/SET ROLE, S3 propio/ajeno,
privacidad e historial/originales HTTP/SHA correctos. Denegaciones S3 reales,
sin relajar controles. No rotación de datos/credenciales de tenant.
Logs calidad/servicio/regresión/API/PG:0marcadores documentales ensayados,
0patrones Bearer; positivos PG4(3+1). Este alcance no es detección universal.
Cierre API/consumidores y expediente CI/revisión/merge/postmerge deben completarse
antes de registrar F06 aceptada. Métricas y todos los fallos previos conservados.

Cierre comprobado: rag-f06-api-source-t010 terminó limpiamente, consumidores
F03/F04/F05 con locks libres y ningún Qwen activo. Se conservan imágenes,
contenedores, originales, documentos, espacios y journals, incluida evidencia fallida.
