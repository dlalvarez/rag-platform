# F04 — herramientas de desarrollo

Solo ragdev01. No ejecutar en equipo local ni contra producción.
F04 aún no aceptada: T002/T003/T005 acreditadas con runtime real; faltan T006/T007.
[Plan/tareas](../../specs/F04-ingesta-versionada/plan.md) y
[evidencia](../../specs/F04-ingesta-versionada/evidence.md).

## Reproducir la cola

Desde un checkout con estas fuentes, usar la configuración existente F02:

    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/check.compose.yaml build queue-check
    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/check.compose.yaml run --rm -T --no-deps queue-check

No pide contraseña de OpenBao ni utiliza la sesión diaria. El servicio es QA de SQL,
con cuatro montajes RO y red control; nunca reutilizarlo como worker de aplicación.
Bootstrap prepara su esquema aislado, migrator lo posee y ejecuta las pruebas.
La migración pública se prueba dentro de una transacción revertida; no queda activada.
Esquema/fixtures sintéticos de QA se conservan, incluidos intentos interrumpidos.
No se consumen documentos F03, no hay borrado, rotación o reinicios de infraestructura.

Conservar la definición histórica queue_schema_f04_0006.py: una migración futura
debe usar su propia definición y mantener intacta la anterior.
El consumidor debe revalidar permisos/tenant/ACL fuera de la cola. Un envelope o
un claim no autoriza acceso a contenido. Antes de confirmar, worker debe reconciliar
commit tenant y respetar tombstone; READY_FOR_EMBEDDING no equivale a PUBLISHED.

Offline: suite pytest en venv de ragdev01, ruff, check_docs y diff --check.
No publicar logs brutos ni materiales de /run/secrets.

## Extracción y chunking sin servicios de datos

Solo ragdev01; mismo env F02 para UID/GID, sin inyectarlo en el servicio:

    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/extract.compose.yaml build extraction-check
    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/extract.compose.yaml run --rm -T --no-deps extraction-check

Cero red/montajes/secretos/puertos; solo corpus sintético interno y tmpfs privado.
El hijo sella syscalls antes de leer el original, con límites de memoria/CPU/salida.
No utiliza la sesión diaria ni inicia ingesta de documentos existentes.
[Contrato y límites](../../specs/F04-ingesta-versionada/extraction.md).
Corpus original nuevo retenido en /home/diego/proyectos/rag-platform-f04-corpus;
manifest SHA-256 en este directorio, sin sobreescribir originales ante colisión.

## Esquema SQL con rollback

    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/schema.compose.yaml build schema-check
    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/schema.compose.yaml run --rm -T --no-deps schema-check

QA con dos bootstrap SQL, control migrator y CA, todos RO; sin Bao/día/S3/IdP.
No usar este servicio como runtime. Pruebas SQL temporales, no extracción S3: se
revierte cada transacción y se verifica que datos, roles y head anteriores se conservan.
No instala persistentemente F04 ni cambia el catálogo. Validar logs solo en servidor
con controles positivos y canary, sin copiar salida bruta.
[Contrato físico y límites](../../specs/F04-ingesta-versionada/schema.md).

## Intención y confirmación de despacho

    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/intent.compose.yaml build intent-check
    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/intent.compose.yaml run --rm -T --no-deps intent-check

Mismos cuatro RO SQL/TLS que schema-check; no usar como worker. Transacciones tenant
revertidas; envelopes QA con UUIDs conservados en f04_intent_probe_0001. Prueba una
confirmación perdida y reenvío, no el crash de un worker real ni migración persistente.
[Contrato T005](../../specs/F04-ingesta-versionada/worker.md).

## Fencing y resultado transaccional SQL

    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/processing.compose.yaml build processing-check
    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/processing.compose.yaml run --rm -T --no-deps processing-check

Mismos cuatro RO SQL/TLS; QA privilegiada, nunca runtime. Repite journal/esquema
y prueba resultado/rollback, lease, dos procesos y locks administrativos.
No realiza extracción S3 ni commit tenant persistente: conserva datos, roles y head.
Envelopes sintéticos de QA retenidos en f04_intent_probe_0001.
No confundir estas pruebas con un worker de aplicación aceptado.

## Runtime de worker, adopción y batería reales

[Contrato de runtime y validación](../../specs/F04-ingesta-versionada/runtime.md).
worker.compose.yaml separa worker (cuatro RO, sin día/admin) y worker-issue (emisor).
No lanzar worker contra head F03; preflight rechaza versiones incompatibles.

    python3 scripts/f04_runtime_host.py prepare --f02-env /home/diego/proyectos/rag-platform/.env.f02
    python3 scripts/f04_runtime_host.py ensure --f02-env /home/diego/proyectos/rag-platform/.env.f02

El emisor usa el día vigente sin contraseña y entrega solo AppRole limitado ya aprobado.
replace se usa tras revocación o cierre/reinicio del consumidor, no renueva el día.
La entrega del worker es distinta de la API; el consumer.lock no se comparte.

api-compat.compose.yaml selecciona perfil F04 explícito, manteniendo rutas F03.
Combinar con ops/f02/compose.yaml + ops/f03/handoff.compose.yaml y sus envfiles.
Construir imagen no cambia servicios. La adopción y promoción coordinada se documentan
y prueban en la entrega operativa; no promover por pasar tests con dobles.

Worker: un job, lease 180 s, pool de un socket por engine/cuatro engines, rootfs RO,
tmpfs 64 MiB privado, 768 MiB RAM y 0.5 CPU. Stop deja de tomar jobs y confirma solo
resultados íntegros con fencing; no borra recursos. No activar F05/embeddings.


## QA real limitada del worker

PR42 activó F04 solo en las cuatro fixtures autorizadas. No repetir adopción/seed
existentes ni lanzar ingesta retroactiva. Seed crea un run exclusivo y conserva recursos;
manifest privado contiene UUID/hash de corpus sintético, nunca credenciales ni texto.
worker-check.compose.yaml añade solo script/manifest RO a la imagen worker de cuatro RO.
actions.compose.yaml es operador separado para pausas, nunca identidad del worker.

Usar --env-file del run propio además del F02; worker-qa recibe mode y --fixture/--case.
Modos positive, sequence, request/process, crash/resume, dependency, pause-*, verify
y privacy. Crash espera exit85 después del commit tenant; resume prohíbe reparse.
Las pausas muestran F04_STAGE PARSED: SIGTERM prueba stop; las demás aplican cambio
del operador y SIGUSR1 para continuar. Restaurar ACL/membresía siempre, conservar tombstone.
No repetir casos terminales esperando STARTED/PARSED. sequence permite tres tamaños
nuevos con --sequence-sizes; --chunk-size crea otra configuración sobre el mismo original.
privacy exige canario real, siete GUC privados, LOG positivo y SQL23514 con savepoint.
Inspeccionar logs solo en VM y publicar PASS, nunca salida bruta.

Cada consumidor normal revoca su app token: replace antes del siguiente. Tras crash,
ensure conserva token vigente y el consumidor de recuperación lo revoca al cerrar.
No editar script mientras esté montado en contenedor; no ejecutar emisores del día
en paralelo. El worker normal probado quedó detenido limpiamente; para operación
iniciar solo worker con su composición, nunca herramientas QA/admin como runtime.
Conservar perfil explícito, límite de scope, lease180, stop70 y entrega separada.

## API T006 y batería limitada

[Contrato HTTP](../../specs/F04-ingesta-versionada/api.md). api.compose.yaml selecciona
imagen t006 con F04 opt-in; mantiene F03. worker-api.compose.yaml selecciona worker:t006.
Combinar API con F02/compose y F03/handoff, preservando siete RO y entorno existente.
Recrear solo API después de CI/revisión; reemplazar identidad limitada DESPUÉS del
cierre del consumidor anterior. No reiniciar datos/IdP/Bao ni repetir adopción.

api-check.compose.yaml conserva el perfil limitado del seed con imagen tools:t006, tmpfs propios
y run privado nuevo (RAG_F04_QA_ROOT), sin día/admin/migrator. seed --run UUID exige
worker detenido, crea corpus explícito e intenciones automáticas; prueba SQL real de
rollback de receipt/candidato/intención y recuperación tras lease, sin borrar objeto.
verify --run UUID se ejecuta tras worker normal y su parada, con entrega reemplazada:
HTTP/ACL/readonly/cursor/cruces/jobs y bajas repetidas, recursos/chunks conservados.
Checkpoints privados predelete/verified permiten reanudar verificación; no omitir pruebas
por editar sus archivos. No ejecutar seed dos veces en el mismo run ni borrar fixtures.
No declarar aceptación por construir imágenes; registrar resultados reales/CI/postmerge.
