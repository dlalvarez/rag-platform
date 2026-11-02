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
