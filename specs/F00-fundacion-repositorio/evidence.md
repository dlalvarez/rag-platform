# Evidencias F00 — implementación en revisión

**Estado:** pruebas offline ejecutadas en ragdev01; integración Compose y revisión final en curso.
No se declara la fase cerrada ni se autoriza F01.

Fecha: 2026-10-30. Base: develop@53004ec218074b0fbf36359e437f22bee3f3924a.
Ambiente real: ragdev01, Ubuntu 24.04.5, x86_64, 2 vCPU, 16 GB RAM, Python 3.12.3,
Docker Engine 29.9.2, Compose 5.6.1, uv 0.13.6. /srv/rag-data: ext4; DockerRootDir:
 /srv/rag-data/docker. Código y pruebas ejecutados en servidor, no en equipo personal.

| Requisito / AC | Tareas / pruebas reales | Resultado | Evidencia |
|---|---|---|---|
| R01/R03; AC-F00-01 | T001/T003; V01 config/API y V03 preparación/pins | 11 tests, lint y formato pasan; clon limpio aún pendiente | [Log offline](../../docs/evidence/f00-offline-2026-10-30.txt) |
| R02/R03; AC-F00-02 | T002; V02 Compose, SQL/vector, S3, API, fallos/persistencia | Pendiente al publicar esta revisión inicial | [Runbook](../../ops/F00_RUNBOOK.md) |
| R04; AC-F00-03 | T004; V04 CI docs/lint/tests y fallos controlados | Gates locales rechazan 3 fallos con salida 1; CI del PR pendiente | [Log offline](../../docs/evidence/f00-offline-2026-10-30.txt) |
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
