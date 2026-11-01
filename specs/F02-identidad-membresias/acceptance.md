# Aceptación técnica F02 — 2026-11-01

F02 implementada y validada en ragdev01 conforme a R01..R05 y AC-01..04 originales.
T001..T006 integradas mediante PR #20..#25. Base de T007:
develop@29a3a84f79925001ff57dafa3debfa5997a325e7.
Este cierre documental no cambia código, dependencias, migraciones, permisos o servicios.
La efectividad del cierre se registra en la conversación del PR T007 tras CI, revisión,
merge y verificación postmerge; no se presenta una propuesta de documentos como prueba.

## Autoridad y alcance

Diego autorizó continuar las actividades del plan sin revisiones/confirmaciones rutinarias,
delegó la revisión e integración según ADR-0007 y eligió expresamente Keycloak solo dev
en D-04/PR #19. Codex registra su revisión técnica del mismo agente. No existe revisión
independiente ni se atribuye una nueva aprobación personal de Diego a esta evidencia.

Se mantienen Constitución, ADRs aprobados, arquitectura, tenancy, roadmap y requisitos.
Solo identidad OIDC configurable, catálogo/membresías/roles y contexto de solicitud;
GET /api/v1/me y /api/v1/tenants autenticados, CLI interna auditada.
Sin endpoints administrativos públicos, ACL de repositorio, documentos, ingesta o chat.

## Trazabilidad y pruebas observadas

| Validación | R / AC | Evidencia |
|---|---|---|
| V01 firma/OIDC | R01/R05; AC-03/04 | T001 CA/TLS real; T002 tokens, rotación de claves y expiración real de 5 s; T005 ID token/credencial inválida; offline none/HS, issuer/audience/nbf/iat, límites/JWKS/cache/fallo de dependencia |
| V02 identidad/membresía | R02/R04; AC-01/03 | T003 PostgreSQL: par issuer+sub, unicidad/FK/CHECK y 12 intentos concurrentes; T004/T005/T006 cuatro identidades reales, roles A/B distintos y usuario sin membresía |
| V03 contexto/IDOR | R03; AC-02/03 | T005 contexto frozen/MAC/trace/TTL y falsificación offline; T006 ruta/cabecera/payload/contexto ajenos con cuatro contadores reales iguales, antes de secretos/pools |
| V04 administración | R04/R05; AC-01/03/04 | T004 bootstrap explícito, sin takeover, matriz owner/admin/editor/reader/support; dos procesos compiten y preservan último owner; último operador protegido |
| V05 estados/aislamiento | R02/R03; AC-01/02/03 | T006 SAME_INSTANCE y TWO_INSTANCES: SQL/vector/TLS/S3 propios, cruces directos bidireccionales denegados, A/B/A; suspensión/revocación/versión observadas en siguiente request |
| V06 auditoría | R05; AC-04 | T003 tabla identidad separada y grants; T004/T005/T006 captura CLI/API sin bearer/password/subject; códigos/UUID cerrados; logs privados con tres flags false |
| V07 reproducibilidad | R01..05; AC-01..04 | 297 tests offline; Ruff/formato 94 archivos/SDD; imágenes por fuentes/hashes, IdP/SQL/S3 reales; F00 smoke y CLI F01/canary; CI y postmerge PR #20..#25 |

Detalle de ejecuciones y correcciones: [evidence.md](evidence.md).
[Resultados saneados T006](../../docs/evidence/f02-t006-2026-11-01.txt).
[Fuentes T006](../../docs/evidence/f02-t006-source-sha256.txt).
[Manual](../../ops/f02/README.md) y [fuentes del cierre](../../docs/evidence/f02-acceptance-source-sha256.txt).
Los manifiestos previos son históricos y se verifican
contra el commit de su entrega; este PR modifica documentación, no aquellas fuentes de código.

Los negativos de algoritmos/claims/JWKS y el fallo de dependencia HTTP 503 usan pruebas
offline; la caducidad, rotación, OIDC/TLS, permisos/estados y SQL/S3 señalados como reales
sí se ejecutaron con servicios del servidor. No se presenta un mock como integración.

## Revisión de seguridad y compatibilidad

Identidad validada antes de registrarla; roles JWT nunca conceden autoridad.
User activo, membresía activa, tenant READY y versión compatibles preceden al resolver.
Contexto de 30 s ligado a request UUID y protegido frente a alteración, sin credenciales
ni destinos físicos en respuestas. Reader usa SQL readonly. No contexto administrativo
de F01 aceptado desde cliente. Pools F01 conservan cotas/drenado y no cambian bases/roles.

API interna TLS, 512 MiB/0.25 CPU, un worker y concurrencia limitada; filesystem de solo
lectura, sin puertos publicados. Solo SQL identity_app y material TLS/clave de autoridad;
sin admin/migrator, secretos IdP/MinIO o sesión diaria. Herramientas de prueba separadas.
No ampliar grants para probes: ops_identity y versión operativa permanecen restringidas.

Control conserva solo identidad/estado/membresías/roles/auditoría y referencias opacas.
Migración f02_control_0005 aditiva y repetible, sin contenido privado ni FK entre bases.
Fixtures previas y datos F01 preservados; estados temporales restaurados.
La CLI F01 usada en regresión conserva su alta sintética esperada; T006 reutiliza sus
cuatro fixtures, sin crear bases/buckets ni rotar contraseñas existentes.

## Operación, reversión y límites

Continuidad de la sesión diaria tras logout mediante Linger=yes; bearer solo en tmpfs
privado, caduca aunque se conserve el runtime y se pierde con reboot. Vencimiento
observado 2026-11-02T06:38:16-05:00; comprobar status/canary antes de usarlo.
No revocar/renovar al cerrar, leer bearer en chat, repetir configure/root o automatizar unseal.

Reversión: retirar solo tráfico/servicio API F02 o volver al código compatible sin borrar
datos. No downgrade destructivo del catálogo/tenants/IdP, borrado de buckets, rekey ni
promoción main/tag. No se ejecutó una reversión de datos de producción.

No login UI/PKCE ni SSO empresarial acreditados: ROPC existe solo en fixture sintética
privada de desarrollo. Proveedor de producción, HA, p95/capacidad, backup/restore externo
y PITR independiente no acreditados. No ACL, URLs firmadas, upload o RAG de F03+.
La API de F02 no usa la autorización infra diaria para servir contenido.
Al planificar F03 deberá definirse acceso de aplicación a secretos con privilegio mínimo;
no sustituirlo por montar la sesión de provisionamiento en la API.

Aviso de compatibilidad Starlette/httpx ya existente; 297 pruebas correctas y sin
silenciarlo. Revisar actualización compatible en una tarea justificada, no por este cierre.
La revisión del mismo agente conserva la limitación de ausencia de revisión independiente.
