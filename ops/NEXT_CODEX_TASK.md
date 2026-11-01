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
T001 integrada en PR #27 con CI/postmerge correctos. T002 en preparación técnica;
seguir T003 mientras el bootstrap administrativo esté pendiente, sin pausa de trámite.
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

## Punto de continuación F03 — componente CRUD/ACL preparado, seguir T005

PR #28: bootstrap real completado y verificado; PR #29 lock de mantenimiento;
PR #30 T003 integrada con CI/postmerge correcto en abae0e6d91b8c02e34816be00393ad1d437b2855.
No repetir configure ni pedir otra contraseña. Día vigente emite AppRole read-only
de una hora con SecretID de un uso, sin bearer infra en runtime.

Worktree técnico ragdev01 /home/diego/proyectos/rag-platform-f03-schema,
feat/F03-T004-repositories. Checkout de operación /home/diego/proyectos/rag-platform limpio.
T004 componente CRUD/ACL y dos ejecuciones reales correctos en cuatro fixtures,
415 tests offline y regresión T003 con datos CRUD presente correcta. Ver acl.md/evidence.md.
Revisar CI/PR/integración/postmerge y continuar T005 sin otra aprobación de trámite.

Repos semilla: ops/f03/repositories-fixture.json, solo UUID lógicos sintéticos.
Alice owner explícita de tenants ORG F03; Bob editor, Carol reader, Dave admin.
Repo a: Alice owner/Bob editor/Carol reader, Dave sin ACL. Repo b: Dave owner y
Alice sin ACL aunque sea operador/owner del tenant. Repo c: Alice owner.
No modificar roles/membresías de fixtures F01/F02 ni conceder contenido implícito.

T002 handoff privado/runtime pendiente; T005 recepción validada/idempotencia/fallos
SQL-S3 y T006 proxy/API pendientes. Mantener AC documentales abiertos.
No desplegar con sesión diaria en API; usar identidad de aplicación limitada.
Reutilizar límites del API existente y sus funciones F02, sin microservicios/puertos
extra. No iniciar F04 antes de acreditar F03 ni alterar la fábrica DDL histórica.
