# Siguiente tarea Codex — F01 T002 después de aceptar T001

**Estado:** T001 implementada y ensayada en [PR #9](https://github.com/dlalvarez/rag-platform/pull/9);
pendientes checks de GitHub, revisión humana y merge. No iniciar T002 por este documento.
Plan ratificado en PR #8; [Issue #7](https://github.com/dlalvarez/rag-platform/issues/7)
abierto. [Evidencia T001](../specs/F01-aislamiento-provisionamiento/evidence.md).

Puerta previa: aprobación explícita de Diego del PR #9, docs/lint/tests del HEAD
correctos, integración a develop y comprobación postmerge. Sin auto-merge/bypass.
Trabajo únicamente por SSH en ragdev01. No instalar ni probar en el Mac.

OpenBao ya inicializado, bootstrap comprobado, root inicial revocado y credenciales
bajo custodia de Diego. No ejecutar init/resume ni pedir claves/passwords por chat.
Tras reiniciar OpenBao, Diego introduce unseal en su terminal; seguir runbook.
No regenerar credenciales para resolver errores.

## Instrucción de implementación, solo después de esa puerta

Implementa solo F01 T002 (F01-R02; AC-F01-01/02; P2; V01/V02).
Lee AGENTS, documentos rectores y seis documentos F01; respeta ADR-0001/0004/0006.

Trabaja en /home/diego/proyectos/rag-platform de ragdev01. Parte de develop
sincronizada tras PR #9, crea feat/F01-T002-* y abre PR hacia develop. No merge.
Conserva F00 y recursos/secretos F01; comprueba montaje y presupuesto.

Prepara bootstrap explícito de instancia/plantilla vector propia y provisionador
NOSUPERUSER con CREATEDB/CREATEROLE; reconoce su alcance administrativo.
No modificar template0/template1. Mantener pins PostgreSQL/pgvector y TLS verificado.
Owner tenant NOLOGIN; migrator/app/readonly propios sin privilegios globales.
UUID internos, identificadores citados del driver y parámetros para valores.
Crear BD con conexiones bloqueadas, reaplicar REVOKE PUBLIC/grants antes de habilitar.

Usa SecretStore para credenciales tenant y refs/versiones en control.
No registrar DSN/passwords, usar root OpenBao ni conservar tokens en Git/.env/logs.
Demuestra control y A/B como bases distintas, privilegios reales, SQL A↔B denegado
y SET ROLE cruzado prohibido. Conservar recursos ante colisión/ownership incierto.
No DROP ni borrar para reintentar. No publicar READY sin probes futuros SQL/S3
y migración coordinada.

Mantén distinción entre contrato/migración inicial T002 y locks, canary y baterías
completas T006. No cerrar AC-F01-01/02 o fase solo por DDL.
No iniciar MinIO F01/T003, saga/T004, resolver/pools/T005, F02 o datos de negocio.

Entrega código y pruebas offline/integración, evidencia saneada R→AC→P→T→V,
regresión F00/T001, rollback conservador y limitaciones.
Si una decisión no resulta viable, proponer ajuste sin cambiar alcance/tenancy.
