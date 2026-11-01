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

## Punto de continuación F03 — esquema preparado, seguir CRUD/ACL

PR #28: bootstrap real completado por Diego y verificado autónomamente. PR #29:
lock compartido entre ventanas/baterías, CI/postmerge correctos. No repetir configure.
El día vigente ya puede emitir f03-application de solo lectura; prueba real de 12 refs,
SQL/TLS propios y denegación de admin/migrator/canary, SecretID de un uso y revocación.

Worktree técnico en ragdev01: /home/diego/proyectos/rag-platform-f03-schema,
feat/F03-T003-schema. Checkout operativo /home/diego/proyectos/rag-platform limpio.
T003 preparado: migración f03_tenant_0002, perfiles explícitos y DDL congelado,
batería real cuatro fixtures correcta, 351 tests offline y regresión F02 ambas
topologías correctos. Revisar CI/PR/integración/postmerge y seguir T004.
Consultar schema.md/evidence.md de F03. No dar AC documentales ni fase por cerrados.

T002 aún necesita handoff privado/runtime sin bearer infra. Continuar T004 CRUD/ACL,
T005 recepción validada/idempotencia/compensación y T006 proxy/API, usando identidad
de aplicación limitada para acceso de datos. Crear perfiles/membresías F03 explícitos
y auditados para las fixtures, sin cambiar membresías F02 ni dar contenido implícito
al operador. La API F02 existente conserva sus límites y funciones; no microservicios
o puertos extra. No iniciar F04 antes de acreditar F03.
