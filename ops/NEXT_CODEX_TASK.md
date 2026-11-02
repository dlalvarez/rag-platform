# Tarea activa Codex — F04, continuidad autónoma

Leer AGENTS/ADR-0010. No cerrar turno por tarea/PR/fase; seguir roadmap autorizado.
Consultar solo decisiones reales, desvíos/inconsistencias o bloqueo externo que requiera
intervención. Toda ejecución manual permanece en ragdev01, nunca en el Mac.

## Estado real y primera actividad

Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T005-runtime-acceptance,
PR #42 borrador. Base develop e0b73e7f36fa1d73474df36f3e09deed64b9196c (PR41).
F00..F03 aceptadas. F04 componentes PR35..41 integrados con CI/revisión/postmerge;
675 tests, 43 postmerge y tres imágenes con 66 módulos src/instalados exactos.

ADOPCIÓN YA EJECUTADA desde PR42 head4df769eb41cb94cec1f101981b2da2267e3b4ccb,
con cuatro checks y revisión previa: las cuatro fixtures están F04 READY; fallo
DDL22012/rollback/FAILED honesto/recovery/repetición/TLS/roles/logs/snapshots correctos.
Cola pública instalada; control app solo SELECT/INSERT/UPDATE. Datos/identidades/
tenants previos y día conservados. NO repetir adopción ni promoción al recuperar contexto.

API actual rag-f04-api:t005, perfil F04 compatible con rutas F03; solo API recreada,
siete RO y HTTPS health F04 correcto. Entrega limitada reemplazada DESPUÉS del cierre
anterior. Datos/IdP/Bao no reiniciados. Todavía no worker normal ni endpoints T006.

Seed primer run cfe3a53d-09e7-4626-993c-641df19f8ca7 falló antes de recursos por
tmpfs /run/f02-auth ausente. Directorio conservado con solo started.json en
/home/diego/proyectos/rag-platform-f04-worker-runs/cfe3a53d09e74626993c641df19f8ca7.
No reutilizarlo ni borrarlo: seed crea started.json exclusivo. Corrección tmpfs 1MiB
0700 + cleanup ya implementada; smoke del helper OIDC real pasó en imagen reconstruida.

Run ACTUAL correcto: 15bbc3e9-06dd-4cdb-ad15-1c9ab055d8d3, directorio
/home/diego/proyectos/rag-platform-f04-worker-runs/15bbc3e906dd4cdbad151c9ab055d8d3
y envfile /tmp/f04-worker-qa-15bbc3e906dd4cdbad151c9ab055d8d3.env.
Seed HTTPS/replay pasó: 52 originales, 16 intenciones positivas, manifest privado.
Worker real pasó los 16 positivos/4formatos/4fixtures: procedencia/hash/offsets/páginas/
TLS/rol/destino/replay correctos. Seis RO reales, sin día/admin/migrator/OIDC passwords.
Scan/malformado/cifrado en same-a/two-b quedaron terminales sin chunks.
Crash real os._exit85 después del commit tenant antes del ack, y recuperación con
intento2 SIN reparse/duplicados, pasaron en ambas topologías. Dependencia/retry también.
No repetir esos casos ya terminales ni reseed. Originales/resultados conservados.

Primera actividad: publicar/CI/revisar cambios de controlador A→B→A/config y operador
scripts/f04_worker_actions.py + actions.compose.yaml + perfil opcional en f03_testing.py.
675 tests y build/config del operador correctos. Luego ejecutar modo sequence y
pausas stop/tombstone/acl/membership en same-a/two-b. El operador separado valida
repo/run/owner/actores; el worker permanece sin día/admin. Restaurar ACL y membresía
siempre. Para pause-stop enviar SIGTERM al QA propio; para otras pausas aplicar
acción y enviar SIGUSR1 al contenedor QA propio para continuar.
No editar el script QA mientras haya un contenedor usándolo como bind RO.

Cada consumidor normal cierra y revoca su app token: f04_runtime_host.py replace
ANTES del siguiente. Tras crash, usar ensure para reutilizar token aún activo y
revocarlo al cerrar recuperación. Todo desde día vigente, sin password por prueba.
API puede requerir ensure de su entrega al pasar una hora, sin reinicio ni día nuevo.

Completar canary/logs/temporales/capacidad/fingerprints y controles finales; CI/revisión/
merge/postmerge del PR42 antes de aceptar T002/T003/T005 y continuar T006.
El PR42 permanece borrador. No cerrar F04 hasta T006/T007 ni anticipar F05.
Continuar sin pausas de trámite, guardar evidencia real, no declarar éxito por mocks.

## Límites, fuentes y acceso

Contratos schema.md/worker.md/runtime.md y ops/f04/adoption.md; docs04/05/07.
Versiones/jobs HTTP usarán rutas rectoras docs07 en T006. Sin PUBLISHED/embeddings
ni cambios a current_version_id, purge, downgrade, main/tag, producción o visibilidad.
No consumir indiscriminadamente documentos anteriores; solo manifiesto/run propio.

Sesión diaria hasta 2026-11-02T06:38:16-05:00. No exportar bearer, renovar/revocar día
ni repetir root/unseal automáticamente. AppRole existente de doce refs/cuatro fixtures,
entregas separadas de API/worker. Reemplazar aplicación después de revocación/cierre;
no compartir consumer.lock. No ejecutar en paralelo baterías que toman el día.

Venv /home/diego/proyectos/rag-platform-f04-parser-venv, PYTHONPATH=src; pytest/ruff.
No sincronizar venv operativo innecesariamente ni instalar nada local.
Datos originales F00..F03, colisiones T005 y repos DELETED conservados.
Corpus original F04 retenido en /home/diego/proyectos/rag-platform-f04-corpus.
Capturar registros privados solo en servidor, devolver PASS/códigos cerrados.
