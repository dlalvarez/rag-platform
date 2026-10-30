# Siguiente tarea Codex — F01 tras ratificación

**Estado:** preparada para revisión, no iniciada.
Fuente: [ratificación F01](../specs/F01-aislamiento-provisionamiento/ratification.md),
[Issue #7](https://github.com/dlalvarez/rag-platform/issues/7).

Antes de código, comprobar aprobación humana de spec/plan/tasks y ADR-0004.
Antes de inicializar OpenBao, Diego confirma custodia externa y establece/introduce
sus credenciales de operador en terminal. No pedir secretos por chat ni capturarlos
en logs de automatización.

```text
Implementa exclusivamente F01-aislamiento-provisionamiento, según planificación
aprobada y Issue #7. Lee AGENTS, constitución, arquitectura/tenancy, modelo de datos,
operaciones, NFR, roadmap, gobierno y ADRs aplicables; luego los seis documentos F01.
Trabaja únicamente en ragdev01, /home/diego/proyectos/rag-platform.
Crea feat/F01-* desde develop aprobada y abre PR hacia develop. No merge.

Sigue T001..T007 y la matriz R→AC→P→T→V. Usa fixtures sintéticas.
No toques servicios/datos F00 ni aprovisiones producción. Prepara perfil F01 separado
bajo /srv/rag-data/rag-platform/f01 después de comprobar montaje, espacio y recursos.
OpenBao solo según ADR-0004 aprobado: pins, TLS, KV v2 persistente, unseal manual
y políticas; root no es runtime. Sin fallback a .env para credenciales de tenant.

Entrega catálogo rag_control sin contenido/credenciales, Alembic control/tenant,
CLI idempotente, DB/roles y buckets privados por tenant, resolver y pools limitados.
Bootstrap de vector separado del rol app. No SQL por interpolación ni grants globales
al tenant. No basta con crear una BD o un bucket para declarar READY.

Demuestra aislamiento A↔B SQL/S3, reintento/fallo de bucket, recuperación, migración
con locks y dos endpoints PostgreSQL reales. Registra versión real y recursos ajenos
intactos. Las pruebas offline no requieren servicios ni APIs de pago; integración
real corre en ragdev01. Mantén regresión F00 y CI docs/lint/tests.

No OIDC/F02, usuarios/membresías de producto, alta HTTP pública, documentos,
ingesta, retrieval ni chat. Sin borrar automáticamente BD/buckets con datos,
sin exportar secretos, sin cambios de visibilidad ni promoción a main.
Reporta límites, pruebas omitidas, comandos/versiones/resultados y rollback.
No cierres Issue #7 ni F01 sin evidencia completa y aceptación humana.
```

Si una decisión aprobada no resulta viable, registrar el bloqueo y proponer ajuste
por PR/ADR; no cambiar secret manager, aislamiento o alcance silenciosamente.
