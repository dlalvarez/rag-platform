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

## Baseline Qwen/SQL sobre corpus congelado

Después de CI/revisión/integración, crear un journal nuevo0700 fuera del repo y
asignar RAG_F06_QUALITY_QA_ROOT a su ruta. Verificar que no hay otro Qwen activo:

    docker compose --env-file .env.f02 -f ops/f02/compose.yaml -f ops/f06/quality-check.compose.yaml run --rm --no-deps --pull never f06-quality-check

Una sola copia local CPU1.5/6GiB/2threads, pesos aprobados RO y red offline para
modelos.16pasajes/40consultas públicas:44operaciones reales del proveedor una vez,
antes de abrir SQL. Vectores solo en memoria; los ledgers de las cuatro fixtures
son sintéticos y no representan uso independiente del worker ni billing.
No S3, API, renovación diaria, adopción de esquema o documentos persistentes.

Baseline vectorial exacto e híbrido top10 en cuatro tenants/dos instancias;
1600citas deben resolver,32consultas técnicas deben acreditar FTS y negativos
tenant/repo/modelo deben denegar. Rollback de todos los datos nuevos y huellas/
head/vector/publication counts/control intactos. No garantía de latencia o escala.

baseline.json guarda métricas reales antes del gate recall; verified.json solo
se guarda si pasan recall híbrido>=0.80 global y por idioma, citas/FTS/rollback
y cero fallos en las cuatro fixtures. Conservar resultado fallido y analizar;
no cambiar golds para aprobar. Latencia de inferencia medida40veces y SQL160
por modo; no sumar o presentar esos datos como latencia HTTP medida.
Negativas con resultados se informan aparte, sin prometer abstención semántica.
