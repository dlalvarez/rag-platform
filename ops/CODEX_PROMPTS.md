# Prompts operativos para Codex Cloud o CLI

> Sustituye `Fxx` por la fase aprobada y adjunta/indica las rutas versionadas del repositorio. Mantener la tarea en **una sola fase**.

## Prompt A — Preparar plan y tareas (sin código)

```text
Actúa como arquitecto/implementador de rag-platform. Lee AGENTS.md, docs/01-constitution.md,
docs/02-architecture.md, docs/03-tenancy-security.md, docs/10-roadmap.md,
ADRs y specs/Fxx-*/spec.md. Esta tarea es SOLO PLANIFICACIÓN, no escribas código.
Genera plan.md, tasks.md y checklist.md en la carpeta de la fase Fxx.
Asegura trazabilidad requisito -> criterio AC -> tarea -> test. Identifica migraciones,
negative paths, rollback, riesgos y dependencias. No propongas cambios de tenancy,
no adelantes fases ni alteres acuerdos. Si hallas contradicción, repórtala y detente.
```

## Prompt B — Implementar fase

```text
Implementa únicamente la fase Fxx aprobada siguiendo AGENTS.md,
spec.md, plan.md, tasks.md, checklist.md y ADRs. Trabaja en una rama de feature,
prepara cambios para PR, sin fusionar ni desplegar. Mantén una base PostgreSQL
independiente por tenant, roles/secretos propios y separación control/data.
Incluye migraciones, tests offline y tests negativos de aislamiento donde apliquen.
No cambies arquitectura ni introduzcas herramientas externas sin justificar y
solicitar aprobación. Al finalizar: reporte de AC cumplidos, tests ejecutados,
archivos modificados, riesgos, limitaciones y pasos de prueba reproducibles.
```

## Prompt C — Revisar Pull Request (sin ampliar alcance)

```text
Revisa este PR contra AGENTS.md, la constitución, ADRs y spec Fxx.
Reporta P0/P1/P2: fugas cross-tenant, credenciales, migraciones destructivas,
reintentos/idempotencia, citas no verificables, falta de pruebas, cambios fuera de fase.
Evalúa cada AC con evidencia concreta. No reestructures código fuera del alcance.
Devuelve dictamen APPROVE / CHANGES REQUIRED / BLOCKED con motivos.
```

## Prompt D — Corregir hallazgos

```text
Corrige exclusivamente los hallazgos aprobados del review de Fxx.
Agrega regresión que falle antes de la corrección, conserva contratos públicos,
ejecuta pruebas, documenta resultado. No cambies roadmap, datos tenant ni proveedores
por conveniencia. Deja los hallazgos no resueltos explícitos para aprobación.
```
