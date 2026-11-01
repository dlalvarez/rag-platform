# Tarea activa Codex — continuar F03 sin pausas de trámite

Diego autorizó expresamente el 2026-11-01 continuidad por el roadmap original y pidió
persistirla. Leer AGENTS y [ADR-0010](../docs/adr/0010-roadmap-continuity.md).
No terminar el trabajo al cerrar una tarea/PR/fase ni esperar otro «procede».
Integrar con evidencia/CI/postmerge y seguir con la siguiente actividad/dependencia.
Consultar solo ante inconsistencias/desvíos, stop conditions o bloqueo externo comprobado;
seguir trabajo independiente y preparar solución concreta antes de pedir intervención.

F00/F01/F02 aceptadas; F02 cerrada en develop@81e213c0682ec1766358b29328e52df968c4d8ea
mediante PR #26. F03 activa: [spec](../specs/F03-repositorios-documentos/spec.md),
[plan](../specs/F03-repositorios-documentos/plan.md), tasks/checklist/evidence.
T001 integrada en PR #27. T002 tiene identidad mínima instalada/probada; handoff y
runtime pendientes antes del despliegue T006. T003/T004 integradas en PR #30/#31.
No crear otro roadmap ni anticipar F04 antes de aceptar F03.

F03: repositorios/ACL, carga validada y objetos privados, metadata RECEIVED y proxy de
original autorizado. Sin parsing/embeddings/Drive/UI/chat. Definir credencial runtime
de mínimo privilegio; no dar a la API el bearer diario, SQL migrator o MinIO admin.
Preparar bootstrap fijo y pruebas; si requiere una acción administrativa no disponible,
solicitar solo esa intervención mientras se avanzan módulos/migraciones independientes.

Código, dependencias, builds, tests y servicios manuales solo en ragdev01:
 /home/diego/proyectos/rag-platform. Mantener PR a develop, revisión delegada ADR-0007,
checks y postmerge; no atribuir revisión independiente/aprobación personal nueva.
Sesión diaria reemitida con vencimiento observado 2026-11-02T06:38:16-05:00.
Comprobar status/canary antes de uso; no leer bearer, renovar/revocar automáticamente,
repetir configure/root o pedir password por batería. Linger=yes conserva tmpfs tras
logout; reboot elimina archivos y unseal permanece con Diego.

Conservar F00/F01/F02, sus fixtures/datos, versiones y clon T007 F01. Sin main/tag,
producción, cambio de visibilidad, borrado/downgrade destructivo o relajación de aislamiento.

## Punto de continuación F03 — finalizar recepción T005 y seguir T006

PR #28: bootstrap real completado y verificado; PR #29 lock de mantenimiento;
PR #30 T003 y PR #31 T004 integradas con CI/revisión/postmerge correctos.
Base actual develop@ea4554fb70425b3df61d9198aeb907e1216fec82.
No repetir configure ni pedir otra contraseña. Día vigente emite AppRole read-only
de una hora con SecretID de un uso; no bearer infra en runtime.

Worktree ragdev01 /home/diego/proyectos/rag-platform-f03-schema,
feat/F03-T005-document-receipt. Checkout operativo /home/diego/proyectos/rag-platform.
T005 implementa validación acotada, objeto condicional privado y diario SQL con
fencing/cuota/recuperación. Ver receipt.md/evidence.md para resultados y límites.
Completar CI, revisión del mismo agente e integración/postmerge del PR correspondiente.

Repos semilla: ops/f03/repositories-fixture.json. Alice owner explícita de tenants ORG
F03; Bob editor, Carol reader, Dave admin. Repo a: Alice owner/Bob editor/Carol reader,
Dave sin ACL. Repo b: Dave owner; Alice sin ACL pese a operador/owner tenant.
Repo c: Alice owner. No modificar permisos de fixtures F01/F02.
conditional-fixture.json conserva los cuatro originales de prueba idempotente;
receipt-fixture.json identifica la última batería T005 completa. No borrar anteriores.

Continuar T002 handoff/T006 API y proxy tras T005. La API recibe solo identidad AppRole
F03 verificada; nunca día/admin/migrator/MinIO admin. Reutilizar servicio API existente
(512 MiB/0.25 CPU, un worker), sin puertos/microservicios extra. Temporales privados
con cuota y concurrencia de carga/descarga; verificar original antes de HTTP exitoso.
Pruebas de cabeceras/errores v1, ACL/cruces y regresiones T007 antes de aceptar F03.
No iniciar F04 ni elegir parser antes de esa aceptación; conservar DDL histórico.
