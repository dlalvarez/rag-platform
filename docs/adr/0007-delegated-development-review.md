# ADR 0007 — Revisión e integración delegadas en desarrollo

**Estado:** autorizado por Diego en conversación el 2026-10-31, al aprobar T007/F01:
«la revision y aprobacion de PR tambien la puedes hacer tu».
Este ADR registra esa instrucción y acota su ejecución; modifica la regla de autorización
por PR de P10, ADR-0003/0006 y docs/14-release-and-governance.md. No altera el roadmap.

## Decisión y motivo

Evitar confirmaciones repetidas en entregas técnicas cuyo alcance ya fue autorizado.
Codex puede implementar, revisar el diff y fusionar hacia develop sin nueva confirmación
si el PR cumple spec/plan/tareas aprobados, evidencia completa, pruebas apropiadas,
checks obligatorios correctos y conversaciones resueltas. Registrar el alcance revisado,
fuentes probadas y resultado postmerge. No presentar esta revisión como independiente
ni enviar una aprobación fingida de Diego a GitHub.

La autorización de iniciar una nueva fase o cambiar su alcance sigue siendo de Diego.
Conservar decisión expresa para arquitectura/contratos/tenancy, promociones a main/tag,
producción, cambios de visibilidad y operaciones destructivas. No añadir requisitos
de aprobación para acciones rutinarias ya autorizadas. Ante fallo esencial, no fusionar.

## Impacto y alternativas

Cambian la autorización operativa y P10; no hay cambios de datos, API, servicios ni
credenciales. Se mantienen PR obligatorios y ruleset sin bypass ni auto-merge.
Con un único responsable no existe revisión independiente; se acepta este límite para
desarrollo, conservando evidencias y controles automáticos. La alternativa anterior
era confirmación humana en cada PR, que Diego solicita sustituir por esta delegación.

La oferta de compartir contraseña de OpenBao no requiere publicarla ni modificar
custodia: unseal permanece con Diego. La siguiente mejora debe preparar una sesión
temporal y revocable en el servidor usando el mecanismo AppRole ya aprobado,
sin contraseña permanente en código/chat/logs. Este ADR no modifica el runtime de acceso
ni afirma que esa automatización esté implementada.

## Reversión

Diego puede revocar o acotar la delegación mediante instrucción expresa. Registrar
el cambio por PR; no reescribir historial ni retirar protecciones. Si se necesita
revertir código, hacerlo por PR y con revisión del impacto en datos.

## Evidencia

T007/F01 fueron aprobadas expresamente y PR #15 integrado antes de aplicar esta
delegación. [Aceptación y postmerge](https://github.com/dlalvarez/rag-platform/pull/15#issuecomment-6548809463).
Esta entrega documental formaliza la instrucción posterior sin iniciar F02.
