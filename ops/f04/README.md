# F04 — herramientas de desarrollo

Solo ragdev01. No ejecutar en equipo local ni contra producción.
F04 aún no aceptada: núcleo de cola probado sin worker ni ingesta activada.
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
