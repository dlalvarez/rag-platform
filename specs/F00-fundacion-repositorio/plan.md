# Plan F00 — propuesta de ratificación

**Estado:** planificación aprobada en PR #5 (2026-10-30); implementación en revisión. Referencias: [spec](spec.md), [tareas](tasks.md), [ratificación](ratification.md), [Issue #4](https://github.com/dlalvarez/rag-platform/issues/4).
Este plan desarrolla F00-R01..05 y AC-F00-01..04 sin cambiar su alcance. No implementa F01 ni tenancy.

## Secuencia y archivos previstos

1. **P1 / T001:** Python 3.12, uv con versión fijada y lockfile versionado; `pyproject.toml`, `uv.lock`, `src/rag_platform/`, configuración tipada mínima y `tests/unit/`. Solo paquete y API placeholder; no crear todos los módulos futuros. Registrar versiones exactas y compatibilidad Linux antes de incorporarlas.
2. **P2 / T003:** `.env.example` con nombres y valores no secretos, `.gitignore`, configuración de pytest y Ruff (lint/formato). Secretos de prueba efímeros provistos fuera de Git, sin imprimirlos. Rechazar configuración incompleta sin revelar valores. No introducir secret manager ni dependencias de F01.
3. **P3 / T002:** `compose.yaml`, Dockerfile de API, health checks y `tests/integration/` o scripts de smoke. PostgreSQL con pgvector, MinIO y API placeholder verificable. Versiones exactas de imágenes/dependencias, sin `latest`; verificar compatibilidad y disponibilidad, documentar digest si se usa. Salud de API sin lógica de negocio, disponibilidad SQL, extensión vector y roundtrip sintético S3. Ningún endpoint de tenants/documentos ni migración de control/tenant.
4. **P4 / T004:** conservar `scripts/check_docs.py` y `.github/workflows/docs.yml`; añadir CI de lint/formato y pytest offline para PR hacia `develop` y `main`. Sin secretos ni despliegue. Probar que fallos controlados producen salida no cero en copias temporales, sin dejar sabotajes en la rama.
5. **P5 / T005:** README y manual de bootstrap con comandos exactos, prerequisitos, diagnóstico, límites, persistencia y limpieza segura de datos sintéticos.
6. **P6 / T006:** clon limpio, suite offline, integración Compose en entorno desechable autorizado, revisión de seguridad y evidencia por AC. PR de implementación hacia `develop` una vez ratificado el gobierno y creada esa rama.

## Matriz spec → plan → tareas → pruebas previstas

Los IDs de prueba identifican verificaciones por implementar; no son resultados.

| Requisito | AC | Plan / tareas | Test y resultado esperado |
|---|---|---|---|
| F00-R01 | AC-F00-01 | P1 / T001, T006 | V01: importar paquete, smoke API y configuración válida/inválida; pytest y Ruff sin API keys |
| F00-R02 | AC-F00-02 | P3 / T002, T006 | V02: Compose config, salud de los tres servicios, SQL/pgvector y put/get/delete de objeto sintético; dependencia caída da error controlado y timeout acotado |
| F00-R03 | AC-F00-01, AC-F00-02, AC-F00-03 | P1–P3 / T001, T002, T003, T006 | V03: instalación con lock sin resolver nuevas versiones; pins y ausencia de secretos; configuración faltante rechazada; montaje inexistente no escribe silenciosamente en raíz |
| F00-R04 | AC-F00-03 | P4 / T004, T006 | V04: CI docs/lint/tests verde; retirar fuente rectora, introducir infracción de lint y test fallido en copias aisladas produce fallos reales |
| F00-R05 | AC-F00-04 | P5 / T005, T006 | V05: desde raíz se descubren AGENTS, constitución y roadmap canónicos; validador documental y enlaces locales pasan; revisión de PR y política registrada |

Comandos objetivo: `uv sync --frozen`, `uv run pytest -m "not integration"`, `uv run ruff check .`, `uv run ruff format --check .`, `python scripts/check_docs.py`, `docker compose config --quiet` y smoke de integración documentado por T002. Ajustar solo sintaxis al artefacto implementado y registrar los comandos realmente ejecutados.

“Offline” significa sin APIs externas ni servicios de pago durante tests; instalar dependencias requiere red o caché previamente preparada. La suite obligatoria no depende de Docker. Integración Compose se ejecuta aparte y sigue siendo obligatoria para cerrar AC-F00-02; una omisión no cuenta como éxito.

## Host, operación y rollback

Contexto comunicado por el responsable: `ragdev01`, Ubuntu 24.04.5, 2 vCPU, 16 GB RAM, ext4 120 GiB en `/srv/rag-data`, Docker/Compose instalados. No se verificó acceso al host en este PR.

Persistencia configurable: ruta local aislada en sandbox; perfil de host bajo `/srv/rag-data`. Antes de cualquier arranque autorizado en la VM, validar montaje ext4, espacio, permisos/UID y puertos; fallar si falta el montaje. Documentar límites de recursos compatibles con 2 vCPU/16 GB, sin reservar toda la capacidad ni publicar servicios de datos a Internet. El responsable autorizó posteriormente implementar y probar F00 por SSH en ragdev01; ver ops/F00_RUNBOOK.md. No se autoriza producción ni F01.

Pruebas solo con datos sintéticos y secretos efímeros externos a Git. Detener el proyecto Compose de ensayo sin borrar volúmenes ajenos; limpieza destructiva solo del entorno desechable identificado. Rollback de código por revert mediante PR. Sin migraciones ni datos de negocio en F00. Snapshot local no equivale a backup externo/restauración validada.

## Puertas de aceptación

Spec/plan/tareas, ADR-0002/0006 y política de ramas ratificados en PR #5. Versiones y resultados registrados en el PR técnico. ADR-0004 y secret manager corresponden a F01. Quedan la revisión humana, decisión de merge y comprobación postmerge. No declarar F00 cerrada antes de esos pasos.

## Ejecución autorizada

PR #5 ratificado; ADR-0002/0006 aprobados y reglas aplicadas. El responsable autorizó ejecución exclusivamente en ragdev01. Ver [runbook](../../ops/F00_RUNBOOK.md). Python host 3.12.3, CI/imagen 3.12.12, uv 0.13.6. Tests y dependencias exactas en pyproject/lock; resultados en evidence. El estado final depende de pruebas, revisión y merge.
