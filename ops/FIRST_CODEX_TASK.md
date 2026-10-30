> F00 finalizada y aceptada en PR #6/Issue #4; este archivo conserva la tarea ya ejecutada. La siguiente propuesta está en [NEXT_CODEX_TASK.md](NEXT_CODEX_TASK.md), pendiente de ratificación F01.

# Tarea Codex activa — F00 en ragdev01

Planificación/ADRs ratificados en PR #5; develop y protecciones ya existen.
La implementación fue autorizada por el responsable para ejecutarse exclusivamente
en ragdev01. Estado y pruebas: [evidence](../specs/F00-fundacion-repositorio/evidence.md).

1. Leer AGENTS, constitución, arquitectura/tenancy, NFR, roadmap y política de ramas;
   seguir spec/plan/tasks/checklist/ratification de F00.
2. Trabajar en /home/diego/proyectos/rag-platform, feat/F00-bootstrap desde develop.
3. Ejecutar dependencias, tests y Compose en ragdev01 según
   [F00_RUNBOOK.md](F00_RUNBOOK.md). Persistencia en /srv/rag-data/rag-platform/f00;
   comprobar el montaje antes de cada operación. Sin datos ni secretos reales.
4. Mantener trazabilidad F00-R01..05 → AC-F00-01..04 → tareas → pruebas V01..V05.
   Reportar fallos, limitaciones, versiones y comandos exactos.
5. Abrir PR hacia develop; no merge ni auto-merge. No cerrar Issue #4 sin revisión humana.

No instalar servicios en el equipo personal, no iniciar F01/tenants/negocio ni
producción, no cambiar visibilidad ni modificar servicios ajenos.
La siguiente tarea depende de la revisión del PR y sus evidencias; no asumir
que la fase terminó por disponer de scaffolding.
