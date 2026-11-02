# F04 T007 — aceptación final y regresiones

Alcance original, sin embeddings/PUBLISHED ni cambios de arquitectura. T006 aceptada
en PR43, develop6398c62100327b4fbf21716f07d5fdcc12793308: tres checks/67 tests
postmerge, checkouts limpios y69 hashes exactos en tres imágenes.

## Puertas trazables

| Requisito/AC | Evidencia ya ejecutada | Puerta T007 |
|---|---|---|
| R01/R04/R06, AC01/03 | PR36..43: cola SQL/carreras, lease/fencing, worker crash/retry/SIGTERM | revalidar estado retenido, CI/postmerge |
| R02/R03/R06, AC02/05 | PR37/42: cuatro parsers, corpus/límites, páginas/offsets, negativos y sandbox | no fabricar OCR/embeddings ni omitir límites |
| R04/R05, AC01/03/04 | PR38..43: commit atómico, tombstone/ACL/membresía durante parseo, HTTP baja | preservar originales/chunks/current pointer |
| P01/P02/P03/P08 | PR42/43: ambas topologías, rol/TLS, readonly/ACL, A→B→A | SQL CONNECT/SET ROLE y S3 propios/cruzados actuales |
| F00..F03 | 702 tests y evidencia histórica; T006 HTTP/rollback/historial T005 | fixture F00 nueva retenida; OIDC/historial F03 actual |
| R06/P08/P09 | PR42 logs con positivo/error y canario ausente, temporales limpios | nuevo canario/log positivo en ambas instancias |

## Comprobadores preparados, aún sin resultado online T007

scripts/f04_regression_check.py usa el runtime limitado y el run T006 ya retenido.
SQL app/readonly propios con TLS/vector y flags limitados; UPDATE/DELETE/CONNECT/
SET ROLE cruzados rechazados sin escribir datos. S3 lee/verifica original propio,
niega stat/get/list de buckets ajenos; no prueba delete cruzado sobre recursos reales.
OIDC real y negativas, originales F03 con SHA/metadata/ACL y una sola versión ORIGINAL,
sin ingesta retroactiva. Probe de privacidad con siete GUC, LOG positivo y rechazo
de INSERT tardío dentro de savepoint revertido. Capturar logs solo en VM.
Perfil f04-regression-check: siete montajes, solo journal RW, sin día/admin/migrator.

scripts/f04_f00_check.py se ejecuta en la imagen/red/secrets históricas F00, separada
del runtime F04. Health API/MinIO, SELECT vector y fixture sintética de UUID nuevo
SQL/S3 en f00_scratch. Segundo proceso verifica lo confirmado por primero; conservar
tabla/bucket/objeto sin limpieza ni reinicios. La fixture histórica f00_probe ya fue
retirada por smoke clean según [evidencia F00](../F00-fundacion-repositorio/evidence.md);
su ausencia actual es esperada y no acredita persistencia histórica nueva.
Esta repetición no ensaya restore ni caída/reinicio, ya acreditados en F00 original.

## Salida

Registrar resultados reales/límites, matriz AC, revisión delegada, CI exact-head,
PR hacia develop y postmerge. Solo entonces aceptar F04 y preparar F05 original.
No cambiar main/tag/visibilidad/producción ni recuperar root/renovar día por iniciativa.
F05 mantiene D06 modelo/dimensión como decisión de arquitectura bajo gobernanza.
