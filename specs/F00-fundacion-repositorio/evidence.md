# Evidencias F00 — implementación en revisión

**Estado:** fase aceptada y cerrada; aprobación humana y postmerge verificados el 2026-10-30.
No se declara la fase cerrada ni se autoriza F01.

Fecha: 2026-10-30. Base: develop@53004ec218074b0fbf36359e437f22bee3f3924a.
Ambiente real: ragdev01, Ubuntu 24.04.5, x86_64, 2 vCPU, 16 GB RAM, Python 3.12.3,
Docker Engine 29.9.2, Compose 5.6.1, uv 0.13.6. /srv/rag-data: ext4; DockerRootDir:
 /srv/rag-data/docker. Código y pruebas ejecutados en servidor, no en equipo personal.

| Requisito / AC | Tareas / pruebas reales | Resultado | Evidencia |
|---|---|---|---|
| R01/R03; AC-F00-01 | T001/T003; V01 config/API y V03 preparación/pins | 11 tests, lint y formato pasan también desde clon limpio | [Log offline](../../docs/evidence/f00-offline-2026-10-30.txt) |
| R02/R03; AC-F00-02 | T002; V02 Compose, SQL/vector, S3, API, fallos/persistencia | PASS: tres servicios saludables; SQL/vector, S3 y API; caída/recuperación y persistencia verificadas | [Log integración](../../docs/evidence/f00-integration-2026-10-30.txt) |
| R04; AC-F00-03 | T004; V04 CI docs/lint/tests y fallos controlados | Gates rechazan 3 fallos con salida 1; CI docs/lint/tests verde en commit a8e56a2 | [Log offline](../../docs/evidence/f00-offline-2026-10-30.txt) |
| R05; AC-F00-04 | T005; V05 validador/descubrimiento | Validador pasa: 12 fases, P01–P14, ADRs y enlaces canónicos | [Log offline](../../docs/evidence/f00-offline-2026-10-30.txt) |

## Pruebas y configuración

V01: tests/unit/test_api.py. V03: tests/unit/test_prepare.py y test_compose_contract.py.
La fixture autouse de conftest bloquea conexiones de red de la suite unitaria.
V04: scripts/f00_negative_checks.py usa copias temporales; elimina constitución,
añade lint inválido y test fallido, y comprueba salida 1 para cada control.
No se dejan esos fallos en la rama.

Las versiones exactas y hashes están en pyproject.toml/uv.lock y los Dockerfiles.
No se usa latest en las imágenes del proyecto. Un hello-world:latest previo en el
host pertenece al entorno existente y no se modifica.
Secretos efímeros generados en /srv/rag-data/rag-platform/f00/secrets, excluidos de Git;
.env solo contiene rutas/UID/GID/configuración. Se revisaron los archivos candidatos
contra esas credenciales y patrones comunes de tokens/claves; sin coincidencias.

## Límites y riesgos

- MinIO se compila de la release oficial fijada porque las imágenes consultadas no
  están disponibles. Upstream está archivado; ver fuentes y limitación de uso en runbook.
- Los tests pasan con un aviso de deprecación de Starlette TestClient/httpx; no se oculta.
- API /healthz solo acredita liveness, sin lógica de negocio. API no recibe credenciales
  SQL/S3. f00_dev es el usuario de bootstrap de una base sintética, no un rol de tenant.
- Sin migraciones, tenants, control plane, datos reales, backup externo/restore ni F01.
  Pruebas de aislamiento tenant/ACL no aplican a F00 y siguen pendientes en sus fases.
- No merge ni promoción a main. Rollback de código por PR; detener solo el proyecto
  rag-f00-dev conserva los datos; no borrar volúmenes ni tocar otros servicios.

## Cierre técnico para revisión

PR: https://github.com/dlalvarez/rag-platform/pull/6, hacia develop, sin merge.
[Clon limpio](../../docs/evidence/f00-clean-clone-2026-10-30.txt) del commit
a8e56a23fa3bd1322cbe554aceb953a75e300a3d: instalación locked con Python del host,
11 tests, lint/formato, docs y fallos controlados, todos con salida 0.
[CI calidad](https://github.com/dlalvarez/rag-platform/actions/runs/41088646426) y
[CI documental](https://github.com/dlalvarez/rag-platform/actions/runs/41088646285)
del mismo commit: éxito. La ejecución del head final se consulta en el PR.

La prueba de seed detectó que Compose reemplazaba CMD; se cambió smoke a ENTRYPOINT
con CMD vacío y se recompiló. Después pasaron seed, fallo de MinIO con salida 1 sin
credenciales/traceback, recuperación, down/up, verificación SQL/S3 y limpieza de fixtures.
[Log completo](../../docs/evidence/f00-integration-2026-10-30.txt).
La constitución ausente, lint inválido y assertion fallida solo se prueban en copias
temporales. La configuración vacía y el montaje inválido devuelven salida 1 sin arrancar.

PostgreSQL real: 17.11 (Debian 17.11-1.pgdg12+2); pgvector 0.8.7.
MinIO reporta DEVELOPMENT.GOGET al compilar con go install, runtime Go 1.24.9:
no confundir ese texto con una versión upstream distinta; el insumo fijado es la
release RELEASE.2025-10-15T17-29-55Z del Dockerfile. No es una imagen oficial publicada.

Los [hashes de fuentes ensayadas](../../docs/evidence/f00-source-sha256.txt) permiten
comparar código, tests, lock y Compose con el head final. Las actualizaciones posteriores
de evidencia no alteran los insumos probados. Revalidar clon/head final queda registrado
en la conversación del PR para no crear una referencia circular al SHA del propio informe.

Reglas actualizadas tras CI verde: docs, lint y tests de GitHub Actions obligatorios en
main/develop, sin bypass ni segundo revisor exigido. API solo 127.0.0.1:8000; datos sin
puertos de host. Estado postpruebas: tres servicios saludables; 112 GiB libres en datos.
Fixtures de persistencia retiradas por smoke clean; no se borran volúmenes.
Aprobación humana del PR técnico y comprobación postmerge en develop: pendientes.

## Cierre confirmado posterior a la entrega

PR #6 aprobado por Diego e integrado en develop@85cd39f401b48e312c1e4fd61906543a4ff588fe. Checkout limpio, hashes coincidentes, instalación locked offline, 11 tests, Ruff/docs y smoke SQL/vector/S3/API pasan en ragdev01; tres servicios saludables.
[Registro postmerge](https://github.com/dlalvarez/rag-platform/pull/6#issuecomment-6527912972), [Issue #4 cerrado](https://github.com/dlalvarez/rag-platform/issues/4), [CI docs del merge](https://github.com/dlalvarez/rag-platform/actions/runs/41090511694), [CI lint/tests del merge](https://github.com/dlalvarez/rag-platform/actions/runs/41090511766).
Este registro completa los estados pendientes del informe entregado arriba, conservado como evidencia histórica. F01 no se inicia por este cierre.
