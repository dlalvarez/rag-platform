# 14 — Política de ramas, releases y cambios

**Estado:** adoptada por aprobación del responsable en PR #5 (2026-10-30).
Main es la rama predeterminada y contiene hitos/releases aprobados; develop es integración
estable; feat/Fxx-* contiene cambios acotados de una fase. Referencia: [ADR-0006](adr/0006-branch-policy.md).

## Ramas y revisión

- Las ramas de implementación parten de develop y abren PR hacia develop.
- Los hitos aprobados se promueven mediante PR develop → main.
- Todo PR referencia spec, plan, tareas, requisitos/AC y evidencia real. Diego es el único
  responsable. Desde la delegación del 2026-10-31, Codex puede revisar y fusionar PR
  hacia develop dentro de tareas/specs expresamente autorizadas, con evidencia completa,
  checks correctos y sin conflictos pendientes. Ver [ADR-0007](adr/0007-delegated-development-review.md).
- No hay auto-merge, despliegue ni promoción automática de ambientes.
- Los cambios documentales también pasan por PR. Cambios rectores requieren ADR y autorización.

Develop se creó desde main@53004ec218074b0fbf36359e437f22bee3f3924a, tras integrar PR #5.
El repositorio sigue siendo público; cambiar su visibilidad requiere decisión expresa.

## Protección aplicada

Ruleset [26218280](https://github.com/dlalvarez/rag-platform/settings/rules/26218280),
main-develop-pr-quality, activo para los nombres exactos main y develop:
PR obligatorio, conversaciones resueltas, checks docs/lint/tests con fuente GitHub Actions,
bloqueo de borrado y force-push. Lista de bypass vacía, también para administradores.
Se exigen 0 aprobaciones externas porque solo hay un responsable; esto no elimina
la responsabilidad de Diego ni convierte la revisión de Codex en revisión independiente.
La autorización previa acotada sustituye la confirmación repetida en cada PR elegible.
[Registro de aplicación](https://github.com/dlalvarez/rag-platform/issues/4#issuecomment-6527049209).

Lint y tests se incorporaron después de verificar las ejecuciones del PR #6:
https://github.com/dlalvarez/rag-platform/actions/runs/41088646426.
No omitir checks fallidos para fusionar.

## Releases y cambios

Versionado semántico de APIs, eventos y migraciones; tags para hitos aprobados.
Cambios incompatibles de datos requieren expand/migrate/contract, backup/recuperación
y pruebas en dos tenants cuando corresponda a su fase. No adelantar tenancy a F00.

No declarar terminado un módulo con tests omitidos, interfaces ficticias o simulaciones
que no se puedan ejecutar. Un placeholder es únicamente el entregable limitado de F00;
no acredita funcionalidades de fases posteriores. Las evidencias y la revisión humana
determinan el cierre de cada fase.

## Delegación de revisión e integración

Diego autorizó en conversación el 2026-10-31 que Codex revise e integre las entregas
dentro del alcance aprobado, sin pedir una nueva confirmación en cada PR.
Es ejecución delegada, no aprobación de GitHub emitida en nombre de Diego.
Se mantienen PR, checks docs/lint/tests, trazabilidad, revisión del diff, registro del
motivo y comprobación postmerge. No habilitar auto-merge ni cambiar el ruleset/bypass.

Decisiones nuevas de arquitectura/contratos/tenancy, ampliación de alcance o fase,
promoción a main/tag, producción y operaciones destructivas conservan decisión expresa.
Un fallo o evidencia incompleta bloquea la integración. Diego puede revocar la delegación.
No se atribuye revisión independiente a la revisión del mismo agente.


## Continuidad entre fases — instrucción del 2026-11-01

Diego autorizó continuar el roadmap original sin nuevas órdenes de inicio por tarea,
PR o fase. [ADR-0010](adr/0010-roadmap-continuity.md) actualiza la reserva de inicio de
fase de ADR-0007: la transición queda autorizada cuando la dependencia tiene evidencia,
aceptación técnica y postmerge completos. Formalizar el plan de cada fase antes del código.
Cerrar una entrega no habilita una pausa de trámite ni omite sus puertas de calidad.
Cambios fuera del alcance original, arquitectura/contratos, producción/main/tag,
visibilidad y operaciones destructivas conservan decisión expresa; un bloqueo real
requiere intervención solo después de agotar el trabajo independiente autorizado.
