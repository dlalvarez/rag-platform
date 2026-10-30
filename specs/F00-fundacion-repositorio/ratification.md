# Ratificación F00 — propuesta del 2026-10-30

**Estado:** pendiente de revisión y decisión humana. Preparar este PR fue autorizado; no se registra como aprobación de su contenido ni como permiso de implementación/despliegue.

Base revisada: `main@1532ee74f0b1b41f06cc1d0d369e2eac386cdef0`, PR #3 integrado e [Issue #4](https://github.com/dlalvarez/rag-platform/issues/4) abierto. El ZIP se toma a través de los documentos rectores recuperados en PR #3; este PR no repite una comparación contra el ZIP original.

## Decisión solicitada al revisar

- Ratificar F00-R01..05 y AC-F00-01..04 sin cambios de alcance, con [plan](plan.md), [tareas](tasks.md), [checklist](checklist.md) y [evidencia](evidence.md).
- Adoptar el flujo original main/develop/feat mediante [ADR-0006](../../docs/adr/0006-branch-policy.md) y [política](../../docs/14-release-and-governance.md). Este PR excepcional de arranque apunta a main; tras su aprobación y merge humano, crear develop desde ese main aprobado.
- Confirmar por separado ADR-0002 antes de implementar la estructura modular propuesta. No se ratifica ADR-0004 ni se habilita F01.
- Registrar decisión de protección: checks obligatorios, revisores humanos, tratamiento del administrador y excepciones. Las reglas no están verificadas ni modificadas por este PR.

## Registro para completar por el responsable

| Decisión | Estado / evidencia necesaria |
|---|---|
| Spec, plan, tareas F00 | Pendiente; revisión/aprobación explícita en este PR |
| Main/develop y ADR-0006 | Pendiente; aprobación humana |
| Creación de develop | Pendiente después del merge aprobado; verificar SHA de origen |
| Protección efectiva main/develop | No verificada; aplicar tras decisión y registrar configuración/fecha |
| ADR-0002 | Propuesto; aprobación explícita pendiente |
| Versiones exactas Python/uv/librerías/imágenes | Seleccionar y verificar en T001/T002; no se inventan versiones probadas |
| Ejecución de integración en ragdev01 | No autorizada por este PR; usar entorno de ensayo autorizado |
| Visibilidad | Público, se conserva; cualquier cambio requiere decisión explícita |

La constitución P01–P14 y el roadmap F00–F11 siguen siendo las fuentes canónicas. La ratificación de F00 no altera su texto ni equivale a ratificar todas las decisiones futuras.

## Separación de entregas

Este PR entrega planificación y gobierno. El siguiente PR implementará F00 y aportará V01–V05 reales. La integración en develop no completa la fase sin revisión humana de todos sus AC. La promoción develop → main se hará mediante otro PR revisado cuando exista un hito aprobado. No auto-merge.
