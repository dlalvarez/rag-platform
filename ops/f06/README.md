# Pruebas F06 de recuperación

## SQL con rollback

Desde el checkout operativo revisado en ragdev01, después de CI/integración:

    docker compose --env-file .env.f02 -f ops/f02/compose.yaml -f ops/f06/retrieval-check.compose.yaml run --rm --no-deps --pull never f06-retrieval-check

Reutiliza imagen de herramientas F05 t003 y monta src/scripts/migrations solo lectura.
Sin Qwen, API, S3 ni sesión diaria. Acceso bootstrap/migrator solo para fixtures SQL
temporales y roles locales; todos los cambios DDL/DML se revierten. No adoptar
esquema ni registrar espacios persistentes. Comprueba cuatro tenants actuales0006,
FTS y filtros antes de ranking, ACL/publicación/baja/app/readonly y huellas históricas/
control tras rollback. Solo códigos cerrados y contadores, nunca textos o vectores.
No acredita calidad semántica, cita autorizante ni rendimiento del corpus F06.

Si falla, conservar journal/logs y código de etapa. No relajar denegaciones,
no reejecutar migración persistente ni borrar fixtures previas.
