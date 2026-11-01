# Tarea activa Codex — cerrar F03 y continuar F04 sin pausas

Leer AGENTS y ADR-0010. Diego reiteró después de PR #32 que completar un PR no permite
terminar el turno. Seguir la próxima actividad autorizada; consultar solo decisiones
reales/inconsistencias/desvíos o bloqueos externos bajo los criterios acordados.
La reiteración está persistida en PR #33. No pedir otro «procede» ni aprobación rutinaria.
Toda ejecución manual de código/dependencias/servicios permanece en ragdev01.

## Estado actual

F00/F01/F02 aceptadas. F03: componentes y API integrados en PR #27..#33; T007 completo
en pruebas y pendiente del PR de cierre con CI/revisión/merge/postmerge.
Ver specs/F03-repositorios-documentos/{spec,plan,tasks,checklist,evidence,acceptance}.md.
No cambiar el roadmap original ni iniciar código de F04 antes de cerrar esa puerta.

Base develop@be7643847f6e472ae9b1b5d3011d83d3f75b3260, PR #33 con CI/revisión/postmerge.
API normal rag-f02-dev-api-1 F03 activa con la misma imagen probada. Candidato efímero
cerrado. PostgreSQL/MinIO/OpenBao conservados, sin puertos nuevos ni cambio de claves.
Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F03-T007-acceptance.
Checkout operativo /home/diego/proyectos/rag-platform en develop, limpio.

T007: 562 tests, HTTP en cuatro fixtures/ambas topologías, observadores, cruces SQL/S3,
conservación tras baja lógica, concurrencia HTTP, ZIP expansivo, F00/F01/F02 y esquema
F03 con documentos presentes correctos. Logs sin secretos/contenido/trazas, temporales
cerrados. Nuevos scripts/artefactos/evidencia en el worktree; publicar PR de cierre,
revisar head exacto, integrar develop y verificar postmerge. Continuar F04 al terminar.

## Operación y recursos

Día autorizado observado hasta 2026-11-02T06:38:16-05:00. Reutilizarlo, comprobar estado;
no leer/exportar bearer al chat, renovarlo/revocarlo automáticamente ni repetir root/
configure. Linger=yes conserva tmpfs tras logout; reboot elimina archivos y unseal
permanece con Diego. No solicitar password por batería.

Runtime API: AppRole limitado de una hora, doce refs exactas de aplicación, sin día,
migrator, root o MinIO admin. scripts/f03_runtime_host.py ensure reutiliza/emite entrega;
replace para identidad revocada/reinicio. API verifica/reemplaza y revoca la anterior.
En worktree indicar --f02-env /home/diego/proyectos/rag-platform/.env.f02. .env.f03
solo contiene UID/GID. Usar composición ops/f02/compose.yaml + ops/f03/handoff.compose.yaml.
No ejecutar baterías que toman el lock diario en paralelo.

Conservar todos los recursos F00/F01/F02/F03 y clon F01 T007. Fixtures F03:
repositories-fixture, conditional-fixture, receipt-fixture, http-fixture,
http-race-fixture y lifecycle-fixture en ops/f03. Las cuatro colisiones T005 y repos
DELETED mantienen reserva/historial/objetos; no borrar ni adoptar. La CLI F01 crea
fixtures sintéticas adicionales durante regresión y las conserva.
Sin main/tag, producción, cambio de visibilidad, purge o downgrade destructivo.

## Continuación tras el cierre

Registrar evidencia/postmerge del PR T007 y seguir la fase F04 del roadmap original.
Leer su spec y docs/05-ingestion.md, docs/04-data-model.md, docs/13-decisions-risks.md.
Preparar plan/tareas/trazabilidad y revisar D-05 (parser PDF/DOCX y límites), que el
registro original deja por confirmar antes de F04. Proponer opciones concretas con
fuentes y consecuencias para calidad/tablas/resiliencia/recursos; no inventar una
aprobación de arquitectura ni pedir una aprobación de trámite de toda la fase.
Mientras llega una decisión necesaria, avanzar documentación/trabajo independiente
sin implementar lo que dependa de ella. No terminar el turno solo por cerrar F03.
