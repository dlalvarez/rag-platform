# Tareas F01 — planificación ratificada

**Estado:** ratificadas en PR #8; T001 aceptada e integrada en develop mediante
[PR #9](https://github.com/dlalvarez/rag-platform/pull/9), con checks y postmerge correctos.
T002 aceptada e integrada mediante PR #10; T003 aceptada e integrada mediante PR #11. T004 aceptada e integrada mediante PR #12; T005 aceptada e integrada mediante PR #13; T006 aceptada e integrada mediante PR #14; T007 en validación.
No se cierra F01.
Referencias: [plan P1–P7 y pruebas V01–V07](plan.md), [ratificación](ratification.md).
Se conservan los IDs T001–T007 originales. Orden: T001 → T002/T003 → T004 → T005 → T006 → T007;
cada tarea comienza solo después de ratificar la planificación y sus decisiones.

- [x] T001 [F01-R01/R03; AC-F01-01/06; P1; V01/V03] Fijar SQLAlchemy/psycopg/Alembic y cliente secreto; crear catálogo mínimo y pista control, contrato tenant, SecretStore y perfil OpenBao aprobado. Artefactos: migrations/control, configuración Alembic separada, control/ y providers/secrets. Probar constraints, refs opacas, bootstrap sin root de runtime, secretos conservados tras restart/unseal, token caducado/denegado y logs saneados. La inicialización requiere que Diego confirme disponibles el gestor y la copia fuera de línea del esquema Shamir 1/1 aprobado; no confundir aprobación del esquema con custodia ya materializada.
- [x] T002 [F01-R02; AC-F01-01/02; P2; V01/V02] Bootstrap revisable de instancias/template vector y cuenta de provisionado separada; crear roles/BD tenant con grants explícitos y nombres UUID. No editar F00 ni template0/template1. Probar tres BD distintas, ACL reaplicadas, app/migrator A↔B denegados, roles sin superusuario ni SET ROLE cruzado y fallo seguro en colisión de recurso.
- [x] T003 [F01-R04/R03; AC-F01-03; P3; V03/V04] Validar MinioAdmin de minio==7.2.20 ya fijado, crear bucket/principal/policy por tenant, guardar credenciales en OpenBao y refs en control. Probar get/put/list propios, cruces y anónimo denegados con credenciales reales; no secretos en argumentos/procesos ni privilegios de administración en principal tenant.
- [x] T004 [F01-R05; AC-F01-04/05; P4; V05] Implementar saga y journal de pasos con lock/idempotencia, CAS de secretos y errores cerrados. Inyectar fallo de bucket, caída después de efecto externo y reintento concurrente. Demostrar un único tenant/BD/bucket, no READY parcial, recuperación y conservación de recursos ajenos; ninguna eliminación automática de BD/bucket con datos.
- [x] T005 [F01-R06/R03; AC-F01-06; P5; V03/V06] Resolver administrativo interno y factory por tenant/instancia/rol/ref-versión. Probar límite por proceso, saturación, timeout, drenado/evicción y cambio A→B→A sin conexión/credencial compartida. Destino desconocido/tenant no READY falla cerrado; no simular autorización de usuario ni implementar F02.
- [x] T006 [F01-R01..07; AC-F01-01..07; P6; V01..V07] Completar pista tenant y locks/versionado/migración canary. Ejecutar dos baterías reales en ragdev01: dos tenants en una instancia y fixtures independientes en dos instancias. Probar ambas direcciones SQL/S3, aislamiento de pools, fallo/reintento/migración concurrente y revisión reversible. Mantener F00 sin regresión; registrar los comandos y resultados reales.
- [ ] T007 [F01-R01..07; AC-F01-01..07; P7; V01..V07] CLI create/show/check/retry/migrate, runbook de bootstrap/TLS/unseal y rollback no destructivo. Ejecutar clon limpio y CI offline, completar matriz evidence/checklist y abrir PR hacia develop. No exportar secretos, no alta HTTP pública, no merge automático ni F02+.

T002/T003 pueden dividirse en PR pequeños manteniendo las puertas y dependencias;
esta lista no autoriza ejecución paralela ni agentes adicionales. Ninguna casilla
se cierra por crear scaffolding. Guardar evidencias de éxitos, denegaciones, fallos
y recuperación; pruebas omitidas bloquean el AC correspondiente.

T002 aceptada e integrada: [cierre PR #10](https://github.com/dlalvarez/rag-platform/pull/10#issuecomment-6535497540).
T003 aceptada: [cierre PR #11](https://github.com/dlalvarez/rag-platform/pull/11#issuecomment-6535895042).
T004 aceptada: [cierre PR #12](https://github.com/dlalvarez/rag-platform/pull/12#issuecomment-6544965980).
T005 aceptada: [cierre PR #13](https://github.com/dlalvarez/rag-platform/pull/13#issuecomment-6547808923).
T006 aceptada: [cierre PR #14](https://github.com/dlalvarez/rag-platform/pull/14#issuecomment-6548128680).
T007 autorizada e implementada; clon limpio, batería CLI y revisión pendientes.
No cerrar F01 ni iniciar F02 todavía.
