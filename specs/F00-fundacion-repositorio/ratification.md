# Ratificación F00 — aprobada el 2026-10-30

Spec, plan, tareas F00 y ADR-0002/0006 aprobados por el responsable en la conversación.
[Registro de aprobación](https://github.com/dlalvarez/rag-platform/pull/5#issuecomment-6526924875).
PR #5 integrado en 53004ec218074b0fbf36359e437f22bee3f3924a; develop se creó desde ese commit.

La aprobación conserva F00-R01..05, AC-F00-01..04, constitución P01–P14 y roadmap F00–F11.
No se ratifica ADR-0004 ni se habilita F01. El ZIP se toma a través de los documentos
recuperados en PR #3; este trabajo no repite la comparación contra el ZIP original.

## Decisiones aplicadas

| Decisión | Estado y evidencia |
|---|---|
| Spec, plan, tareas F00 | Aprobados en PR #5; [plan](plan.md), [tareas](tasks.md) |
| ADR-0002 y ADR-0006 | Ratificados por aprobación del responsable registrada en PR #5 |
| Develop | Creada desde main aprobado, 53004ec218074b0fbf36359e437f22bee3f3924a |
| Protección main/develop | Ruleset activo 26218280; [política](../../docs/14-release-and-governance.md) |
| Revisión humana | Diego, único responsable; PR obligatorio, sin segundo revisor exigido ni bypass |
| Ejecución de F00 | Autorizada expresamente por SSH en ragdev01; código, dependencias y servicios allí |
| Visibilidad | Público, sin cambio autorizado |
| Versiones y validación | pyproject/uv.lock, Dockerfiles y [evidence](evidence.md) |
| Merge del PR técnico | Pendiente de revisión y autorización posterior |
| F01, producción y backup externo/restore | No ejecutados ni aprobados por esta entrega |

## Alcance de la ejecución

El responsable corrigió el flujo para que implementación y pruebas se realicen en
ragdev01, no en su equipo personal. Autorizó acceso SSH y operaciones F00 en ese servidor,
habilitó el grupo docker y preparó /srv/rag-data/rag-platform.
Ver [runbook](../../ops/F00_RUNBOOK.md) y [checklist](checklist.md).

La autorización de ejecución no sustituye pruebas ni aceptación. El PR técnico va
hacia develop; promoción a main mediante otro PR revisado para un hito aprobado.
Ninguna fusión ni despliegue de producción automático.
