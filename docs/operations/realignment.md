# Registro de realineación SDD — 2026-10-28

## Motivo
El PR #2 inicializó una constitución resumida, un roadmap reorganizado y una F00 exclusivamente documental. El kit rector original definía una constitución P01–P14, F00 con bootstrap técnico verificable (Python, Compose PostgreSQL/pgvector + MinIO, documentación, CI), F01 con provisionamiento aislado y fases hasta F11 comercialización.

## Resolución propuesta en este PR
- Restituir exactamente los **53 archivos** del ZIP original, salvo ajustes documentados de estado posterior en `ops/DECISION_STATUS.md`, `ops/BOOTSTRAP.md` y `docs/13-decisions-risks.md`.
- Unificar autoridad: `docs/01-constitution.md` y `docs/10-roadmap.md` son fuentes canónicas. Archivar las versiones simplificadas del PR #2.
- Conservar runbooks sobre `ragdev01` y recuperación en `docs/operations/`; el ADR de Synology se renumera a 0005 sin desplazar ADR 0002 del monolito modular.
- Tratar la aprobación del PR #2 como aprobación **documental**, no cumplimiento de F00-R01..05 ni AC-F00-01..04.
- F00 y F01 originales siguen con código/despliegue pendiente. `specs/F00-fundacion-repositorio` es la única carpeta F00 activa; `specs/F01-aislamiento-provisionamiento` la única F01 activa.
- Se preserva trazabilidad en `docs/history/pr2/`.

## Evidencia y límites
La VM de desarrollo Ubuntu y Docker fue validada; snapshot VMM creado. No existe todavía prueba de backup externo/restauración, stack Compose de F00, implementación de control plane ni aislamiento real de tenants.

## Decisiones pendientes de aprobación formal
- Detalles de backend/cola/almacenamiento descritos como **propuestas** en ADR 0002/0004 y `ops/DECISION_STATUS.md`.
- Política de ramas con `develop`, protecciones GitHub y CI: acordar antes de completar F00.
- Estándares de restauración y RPO/RTO; confidencialidad adecuada del repositorio público.
- Versiones reales de Python/PostgreSQL/pgvector/MinIO y secretos dev/prod antes de F00/F01.
