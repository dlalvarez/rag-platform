# Tarea activa Codex — F04, continuar sin pausas de trámite

Leer AGENTS y ADR-0010. Diego autorizó continuidad del roadmap original: no terminar
por cerrar tarea/PR/fase. Solo consultar decisiones reales, desvíos/inconsistencias o
bloqueo externo que requiera intervención. Toda ejecución manual en ragdev01.

## Estado y primera actividad pendiente

F00..F03 aceptadas. F04 T001 PR #35 integrado; núcleo T002 PR #36 integrado en
develop@590d4fe385ed3efa4c3743a1a129a3e5692b3beb. Cuatro checks del head/tres del merge,
revisión delegada y postmerge correctos; 22 tests postmerge/hash de imagen correctos.
Cola probada en esquema QA retenido, no migración pública ni worker activos.
T002 sigue abierta hasta activación/grants/parada con T005.

Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T005-intent-reconciliation.
Checkout operativo /home/diego/proyectos/rag-platform, limpio, en develop.
T004 aceptada PR #37. T003 núcleo integrado PR #38,
develop@e69a3af31433291e42158854fca8123675368e47: 631 tests, cuatro fixtures SQL,
CI/revisión/postmerge correctos; 13 tests postmerge y diez hashes exactos.
Todavía sin esquema/perfil/worker F04 persistidos.

T005 contrato en worker.md. Primer componente journal/relay implementado:
14 tests nuevos, PostgreSQL cuatro fixtures/ambas instancias; versión/intención/
auditoría atómicas, config estable, actor conservado, ack perdido recupera un job.
QA tenant revertido, envelopes sintéticos de control retenidos; doce hashes y logs
con controles positivos/errores sin texto. No acredita worker/runtime.
Cerrar regresión y PR específico de componente, CI/revisión/merge/postmerge.
Continuar inmediatamente worker/fencing/parada y activación coordinada con API F04.
T002/T003/T005 abiertas; no fingir ACID entre bases ni PUBLISHED sin embeddings.

Conservar originales/recepciones/versiones F03 y factorías históricas.
Leer schema.md/worker.md, docs/04-data-model.md, docs/05-ingestion.md,
docs/07-api-contracts.md y migraciones/perfiles actuales antes de integrar.
No consumir indiscriminadamente documentos previos; usar manifiesto/corpus propio.
T004 y journal no acreditan aún AC E2E ni integración del worker.

## Fuentes y pruebas

D-05: pypdf 6.21.4/python-docx 1.2.0/lxml 6.1.3; todas las versiones previas del lock
conservadas. Venv separado /home/diego/proyectos/rag-platform-f04-parser-venv.
Con PYTHONPATH=src, ejecutar ese venv/bin/pytest -q y ruff check/format.
No sincronizar innecesariamente el venv operativo ni instalar nada en el Mac.

Corpus nuevo: scripts/f04_corpus.py, ops/f04/corpus-manifest.json; cuatro originales
sintéticos estables retenidos en /home/diego/proyectos/rag-platform-f04-corpus (0700/0600).
No sobrescribirlos si cambian ni reutilizar claves F03. PDF página escaneada → NEEDS_OCR;
blank_page preserva páginas vacías; DOCX sin paginación inventada. No OCR/modelos/embeddings.
Ver extraction.md/parsers.md y evidencia para limitaciones de layout/imagen/capas residuales.

Pruebas de contenedor: ops/f04/README.md, extract.compose.yaml; no datos ni credenciales.
Cola: check.compose.yaml, queue-check SQL QA con cuatro RO. Nunca usar perfil QA como
worker. Definición histórica queue_schema_f04_0006.py inmutable.

## Acceso y operación conservados

Sesión diaria emitida hasta 2026-11-02T06:38:16-05:00; comprobar estado cuando se use.
No exportar bearer, pedir password por prueba, renovar/revocar día ni repetir root/configure
automáticamente. Linger conserva tmpfs tras logout; reboot lo elimina. Unseal con Diego.

API normal sigue F03, no worker F04 desplegado. AppRole limitado de una hora/12 refs;
sin día/migrator/IAM admin en API. Si caducó, issuer ensure emite solo identidad limitada
usando sesión diaria válida; replace tras revocación/reinicio. Sin reinicios de infraestructura.
Composición API ops/f02/compose.yaml + ops/f03/handoff.compose.yaml; .env.f02 operativo.
En worktree indicar --f02-env /home/diego/proyectos/rag-platform/.env.f02 al helper F03.
No ejecutar en paralelo baterías que toman el lock diario.

Conservar todos los recursos/fixtures originales F00..F03, cuatro colisiones T005 y repos
DELETED. No main/tag, producción, cambio de visibilidad, purge ni downgrade destructivo.
Capturar logs/errores privados en servidor y devolver códigos/PASS, nunca salida bruta.
