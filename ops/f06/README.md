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

## Servicio con identidad y originales existentes

Primero cerrar cualquier otro Qwen. Emitir una entrega limitada F05 nueva mediante
el emisor ya aprobado, solo con sesión diaria válida y consumidor cerrado. No
montar día/bootstrap/migrator en el comprobador. Definir RAG_F04_QA_ROOT al journal
API a75adb4c445c46d698abc558a8308112, RAG_F05_EMBED_QA_ROOT al proof Qwen
1c70faf0282548499cd601f6ebe9859e y RAG_F06_SERVICE_QA_ROOT a un journal nuevo0700.

    docker compose --env-file .env.f02 -f ops/f02/compose.yaml -f ops/f06/service-check.compose.yaml run --rm --no-deps --pull never f06-service-check

Valida scope/perfil/IDs contra manifest retenido; no modifica documentos ni cola.
Usa identidad real y autorización vigente en los cuatro tenants, HybridService
filtrado a versiones seleccionadas, resolución de citas y regresión SearchService
exacto F05. Ocho consultas reales al único Qwen cargado; repos ajenos y citas de
otro tenant/inexistentes se deniegan sin inferencia adicional. Cierre revoca su
entrega limitada; no renovar automáticamente. Solo contadores en verified.json.
No nuevo endpoint HTTP, acceso bootstrap, S3 o generación.
