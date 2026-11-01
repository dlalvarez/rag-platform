# ADR 0010 — Continuidad autónoma del roadmap original

**Estado:** autorizado expresamente por Diego el 2026-11-01.
**Origen:** tras el cierre F02, Diego indicó «No puedes detenerte, debes continuar segun
el plan» y pidió guardar la instrucción y consultar solo bajo los criterios ya definidos.

## Decisión

Continuar las tareas y fases del roadmap original en orden, sin esperar otra orden de
inicio al terminar cada tarea/PR/fase. La dependencia debe quedar aceptada y comprobada
antes de pasar a la siguiente. Formalizar plan/tareas/trazabilidad antes de implementar.

La aprobación humana de alcance original y la delegación de revisión/integración se
ejercen mediante esta instrucción continuada y ADR-0007. La leyenda de borrador de una
plantilla no exige otra confirmación rutinaria para ejecutar ese alcance sin cambios.
Se conserva la diferencia entre autorización previa de Diego y revisión del mismo agente;
no hay aprobación personal nueva ni revisión independiente fingida.

Este ADR amplía expresamente la autorización de transición entre fases que ADR-0007
reservaba a una orden posterior. No reescribe su evidencia histórica ni cambia P01..P14,
requisitos, dependencias, decisiones de arquitectura o roadmap.

Consultar ante inconsistencias con contratos/specs, decisiones fuera del alcance original,
stop conditions de seguridad/datos o impedimentos externos comprobados que requieran
intervención. Avanzar tareas independientes del bloqueo y preparar una solución concreta.

## Controles y límites

PR hacia develop, checks correctos, evidencia real, revisión del diff y postmerge.
No auto-merge, bypass, force-push, promoción a main/tag, producción, cambio de visibilidad,
operaciones destructivas, secretos en chat/repo/logs ni ejecución local de servicios.
La sesión diaria es para pruebas/operación delegada; no sustituye mínimo privilegio del
runtime. Su vencimiento o pérdida real de acceso puede requerir una acción del operador.

## Persistencia y reversión

AGENTS.md contiene la instrucción ejecutable; ops/NEXT_CODEX_TASK.md conserva contexto
actual y trabajo restante. Los documentos de fase distinguen avances, pruebas y bloqueos.
No detener el trabajo solo por producir una entrega o por compactación del chat.
Diego puede revocar o acotar esta autorización expresamente. Mantener evidencias y ramas;
no retirar protecciones ni modificar retrospectivamente aprobaciones.
