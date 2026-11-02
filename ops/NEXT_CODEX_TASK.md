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

Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T003-versioned-schema.
Checkout operativo /home/diego/proyectos/rag-platform en develop, limpio.
T004 integrada en PR #37, develop@f1a7a3ddc077302b4c1bdebaeef3ba60b3489716.
Cuatro checks del head/tres del merge, revisión delegada y postmerge correctos.
618 tests previos y 34 postmerge; imagen con diez hashes correctos.
T003 núcleo implementado y probado: 631 tests, lint/formato/docs/diff; cuatro fixtures
SQL/ambas instancias, diez hashes de imagen, migración repetida, FKs/procedencia/roles,
completitud/auditoría/tombstone/ACL y rollback correctos. Logs con errores/control
positivo y canary de cuerpo ausente. Todavía sin esquema/perfil/worker F04 persistidos.
Publicar PR del núcleo, revisar head, CI/merge/postmerge; continuar T005 sin pausa.

T003: esquema tenant aditivo para versiones de procesamiento/chunks, intención durable
y tombstone; conservar originales/recepciones/versiones F03 y factoría histórica.
Leer plan/spec, docs/04-data-model.md, docs/05-ingestion.md, docs/07-api-contracts.md y
migraciones/perfiles actuales antes de fijar detalle. schema.md fija el contrato ya implementado; revisar antes de integrar worker. No fingir atomicidad entre bases ni PUBLISHED sin embeddings.
No consumir indiscriminadamente documentos previos; usar manifiesto/corpus propio.
T004 no acredita aún AC E2E ni integración del worker.

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
