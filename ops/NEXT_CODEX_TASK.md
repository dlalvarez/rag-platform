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

## Punto de continuación F03-T002

Adaptador de aplicación read-only y bootstrap fijo en ops/f03/README.md.
333 tests offline, lint/format/docs correctos y prueba OpenBao real aislada correcta.
Cuatro fixtures F03 propias creadas, refs públicas enumeradas sin credenciales.
El día vigente tiene deny administrativo; falta acción única del operador con su clave
para instalar el rol mínimo (dos reinicios SOLO OpenBao, root revocado/config restaurada).
Preparar PR/CI/revisión/integración y checkout limpio antes de solicitar esa acción.
No pedir contraseña para baterías: tras setup el día puede emitir el AppRole limitado.
No reutilizar bearer diario en API ni dar T002 por cerrada. Continuar esquema/módulos
T003 de forma independiente; preservar checkout de operación limpio si hay intervención.
