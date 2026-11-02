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

Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T005-runtime-acceptance.
Operativo /home/diego/proyectos/rag-platform en develop@e0b73e7f36fa1d73474df36f3e09deed64b9196c.
T004 PR37, núcleos T003 PR38 / intención PR39 / fencing PR40 / runtime PR41 integrados.
CI/revisión/postmerge correctos; 675 tests, 43 postmerge, tres imágenes de 66 módulos
src e instalados exactos. Ninguna migración/worker F04 activa; API actual F03.

En curso: PR operativo acotado, cinco fuentes restauradas/preparadas:
scripts/f04_adopt.py, f04_seed.py, ops/f04/activate.compose.yaml, seed.compose.yaml,
adoption.md. Originales públicos de preparación preservados en /tmp/f04-runtime-operations-pending.
PDF malformado comprobado: página uno válida, segunda inválida -> PARSER_INVALID sin parcial.

Primera actividad: validar config/build/hashes de herramientas operativas, publicar
PR borrador y comprobar CI/head/revisión. Ejecutar adopción manual solo desde ese
head revisado, conservando datos/roles/identidades/tenants previos y fallo/recovery real.
Después API compatible: recrear solo API con los envfiles operativos F02/F03 y override
F04. Reemplazar su entrega limitada DESPUÉS del cierre/reinicio del consumidor previo.
El cierre anterior puede revocar el token; health solo no prueba acceso documental.

Preparar entrega propia del worker (f04_runtime_host.py), crear run QA privado nuevo
0700 fuera del repo, emitir identidad limitada desde día vigente. Seed HTTPS explícito,
sin ingesta indiscriminada de originales anteriores. Su cierre revoca el token de
aplicación: replace antes de la siguiente batería. Nunca renovar/revocar el día.
Completar controlador QA del worker, S3/parser, crash tras commit antes de ack,
dependencia/reintento, baja/ACL/membresía durante PARSED, parada/reinicio, A→B→A,
logs/temporales/roles/TLS y no regresión. Evidencia/CI/revisión/merge/postmerge antes
de aceptar T002/T003/T005 y continuar T006. T005/F04 siguen abiertas.

Conservar originales/recepciones/versiones F03 y factorías históricas. Leer
schema.md/worker.md/runtime.md, ops/f04/adoption.md, docs04/05/07 y perfiles actuales.
Versiones/jobs HTTP usarán rutas rectoras docs07 en T006. No fingir ACID, PUBLISHED,
aceptación F04 ni anticipar F05. Continuar sin pausa salvo decisión real/bloqueo.

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
