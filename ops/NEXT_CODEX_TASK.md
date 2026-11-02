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

Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T005-worker-runtime.
Checkout operativo /home/diego/proyectos/rag-platform en develop.
T004 PR37 y núcleos T003 PR38 / intención PR39 / fencing PR40 integrados.
Develop@3ec113a6a60ee3c20bdb178c6ba8f93e949f96c7; CI/revisión/postmerge correctos.
656 tests previos, 25 postmerge; dieciséis hashes exactos. Todavía sin esquema/perfil/
worker F04 persistidos. API normal conserva F03.

En curso: worker.py/runtime.py/worker_main.py, entrega propia rag-f04-worker con
AppRole F03 limitado de doce refs, Dockerfile sin scripts admin, Compose de cuatro
montajes RO sin día. Emisor separado usa sesión diaria válida, nunca contraseña.
Pool worker de un socket/engine (máximo cuatro), contrato runtime.md antes del código.
API compatible opt-in mediante RAG_F04_ENABLED=1 más F03_ENABLED=1; misma superficie
F03 hasta T006, sin aceptar heads futuros. Defaults F02/F03 conservados; 656 tests
pasaron después de los cambios del perfil. 675 tests/lint/formato/docs/diff correctos; 19 tests nuevos y 30 focalizados.
Tres imágenes con 66 hashes de src y paquete instalado correctos; sin despliegue.

Primera actividad: cerrar QA SQL de los guards con la imagen runtime exacta y
publicar el PR acotado del runtime. CI/revisión/merge/postmerge.
Seguir inmediatamente PR operativo: restaurar los tres archivos públicos guardados
con sus hashes en /tmp/f04-runtime-operations-pending/manifest.json (adopt, seed,
activate.compose), sin borrarlos ni perder su contenido. Ninguna credencial allí.
Completar QA S3/parser/crash tras commit/baja/revocación/parada de las cuatro fixtures.
Adopción explícita con FAILED honesto/recuperación y logs/roles mínimos; preparar PR/CI/
revisión antes de ejecutar migración y promoción coordinada. Reemplazar entrega API
DESPUÉS de reiniciar/recrear su consumidor, para no usar el token revocado al cerrar.
No promover API/worker por solo pasar mocks. T002/T003/T005 siguen abiertas.

Conservar originales/recepciones/versiones F03 y factorías históricas. Leer schema.md,
worker.md/runtime.md, docs04/05/07 y migraciones/perfiles antes de integrar.
No consumir indiscriminadamente documentos previos: usar manifiesto/corpus propio.
Versiones/jobs HTTP usarán rutas rectoras de docs07 en T006, después del worker.
No fingir ACID entre bases, PUBLISHED, aceptación F04 ni anticipar F05.

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
