# 14 — Política de ramas, releases y cambios

**Estado:** adoptada por aprobación del responsable en PR #5 (2026-10-30).
Main es la rama predeterminada y contiene hitos/releases aprobados; develop es integración
estable; feat/Fxx-* contiene cambios acotados de una fase. Referencia: [ADR-0006](adr/0006-branch-policy.md).

## Ramas y revisión

- Las ramas de implementación parten de develop y abren PR hacia develop.
- Los hitos aprobados se promueven mediante PR develop → main.
- Todo PR referencia spec, plan, tareas, requisitos/AC y evidencia real. Diego es el único
  responsable y revisa/autoriza explícitamente cada merge; Codex no fusiona por iniciativa propia.
- No hay auto-merge, despliegue ni promoción automática de ambientes.
- Los cambios documentales también pasan por PR. Cambios rectores requieren ADR y autorización.

Develop se creó desde main@53004ec218074b0fbf36359e437f22bee3f3924a, tras integrar PR #5.
El repositorio sigue siendo público; cambiar su visibilidad requiere decisión expresa.

## Protección aplicada

Ruleset [26218280](https://github.com/dlalvarez/rag-platform/settings/rules/26218280),
main-develop-pr-quality, activo para los nombres exactos main y develop:
PR obligatorio, conversaciones resueltas, check docs con fuente GitHub Actions,
bloqueo de borrado y force-push. Lista de bypass vacía, también para administradores.
Se exigen 0 aprobaciones externas porque solo hay un responsable; esto no elimina
su revisión ni convierte a Codex en revisor independiente.
[Registro de aplicación](https://github.com/dlalvarez/rag-platform/issues/4#issuecomment-6527049209).

Lint y tests se añaden a los checks obligatorios cuando existan y sus ejecuciones
se hayan verificado. No exigir nombres inexistentes ni omitir checks fallidos para fusionar.

## Releases y cambios

Versionado semántico de APIs, eventos y migraciones; tags para hitos aprobados.
Cambios incompatibles de datos requieren expand/migrate/contract, backup/recuperación
y pruebas en dos tenants cuando corresponda a su fase. No adelantar tenancy a F00.

No declarar terminado un módulo con tests omitidos, interfaces ficticias o simulaciones
que no se puedan ejecutar. Un placeholder es únicamente el entregable limitado de F00;
no acredita funcionalidades de fases posteriores. Las evidencias y la revisión humana
determinan el cierre de cada fase.
