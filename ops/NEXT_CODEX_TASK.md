# Siguiente tarea Codex — tras el cierre F02

F00/F01 aceptadas; F02 implementada y probada en PR #20..#25. La entrega T007 formaliza
aceptación técnica delegada y su cierre se registra en el PR tras CI/merge/postmerge.
Leer [aceptación](../specs/F02-identidad-membresias/acceptance.md), checklist/evidence,
Constitución, ADRs, arquitectura/tenancy, API y [roadmap original](../docs/10-roadmap.md).

No queda implementación F02 pendiente por crear scaffolding: los AC tienen pruebas reales
y offline diferenciadas. Conservar código/manifiestos y resultados T006; no volver a
pedir revisión/password por cada batería ni repetir pruebas solo para generar evidencia.

La siguiente fase es [F03](../specs/F03-repositorios-documentos/spec.md): repositorios,
ACL, carga y objetos privados. Antes de tocar código, formalizar su plan/tareas/matriz
de pruebas respetando la spec original y el alcance autorizado. No crear otro roadmap.
Registrar cualquier decisión real fuera de las specs antes de ejecutarla.
En particular, definir acceso de aplicación a secretos con mínimo privilegio:
la API F02 es de metadata y no tiene Bao/MinIO/SQL tenant; no montar en ella el bearer
de provisionamiento/operación diaria como atajo. La delegación evita confirmaciones
rutinarias, pero no amplía por sí misma una decisión de arquitectura o el alcance de fase.

Toda ejecución, dependencias y servicios en /home/diego/proyectos/rag-platform de ragdev01.
Diego reemitió sesión diaria con vencimiento observado 2026-11-02T06:38:16-05:00.
Comprobar status/verify, no leer bearer en herramientas ni asumir vigencia por esta fecha.
Linger=yes conserva runtime tras logout, tmpfs pierde archivos tras reboot.
No renovar/revocar automáticamente, pedir password por batería, repetir configure o root.
Custodia de unseal/password permanece con Diego; no secretos en chat/repo/logs.

Mantener PR hacia develop, checks/docs/lint/tests, revisión del mismo agente y postmerge
bajo ADR-0007. No atribuir revisión humana/independiente nueva. No iniciar servicios de
otra fase sin su alcance/plan ni cambiar main/tag, visibilidad, tenancy o producción.
F00/F01, datos, fixtures y clon T007 F01 se conservan; sin borrados/downgrades destructivos.
