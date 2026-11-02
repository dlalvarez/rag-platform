# Tarea activa Codex — F04 T006, continuidad autónoma

Leer AGENTS/ADR-0010 y documentos rectores. No cerrar turno por tarea/PR/fase;
seguir el roadmap original. Solo consultar decisiones reales, desvíos o bloqueo externo
que requiera intervención. Todo código/tests/build/servicios en ragdev01, nunca Mac.

## Primera actividad y estado

PR #42 acredita T002/T003/T005 en ragdev01: adopción persistente, cola, cuatro
fixtures READY F04, worker real/S3/cuatro formatos, negativos, crash después del commit
antes del ack, reintento, A→B→A, bajas/revocaciones, SIGTERM y privacidad/temporales.
675 tests. Completar CI/revisión/integración develop y comprobación postmerge del PR42;
registrar hashes/checks/evidencia en su conversación. Después continuar T006 sin pedir
aprobación rutinaria. F04 sigue abierta hasta T006/T007.

Checkout /home/diego/proyectos/rag-platform-f03-schema. No repetir adopción ni seed.
API rag-f04-api:t005 usa perfil F04 con superficie HTTP F03 todavía; solo API fue
recreada, datos/IdP/Bao intactos. Worker operativo probó dos jobs y quedó detenido
limpiamente (exit0); no confundir con servicio continuamente activo.

Run correcto retenido: 15bbc3e9-06dd-4cdb-ad15-1c9ab055d8d3,
directorio /home/diego/proyectos/rag-platform-f04-worker-runs/15bbc3e906dd4cdbad151c9ab055d8d3,
envfile /tmp/f04-worker-qa-15bbc3e906dd4cdbad151c9ab055d8d3.env.
52 originales HTTPS/cuatro repos; manifiesto privado. Negativos/pausas ya terminales,
no repetirlos esperando nuevas etapas. ACL/membresía restauradas; tombstones retenidos.
Primer run cfe3a53d-09e7-4626-993c-641df19f8ca7 conserva solo started.json, sin recursos.
No sobrescribir ni purgar. Originales F00..F03 y corpus F04 conservados.

## T006 y controles

Crear rama específica desde develop postmerge. Formalizar contrato detallado antes del
código: GET documentos/{doc_id}/versions y jobs/{job_id} de docs07; DELETE documental
con tombstone del plan F04. Borrador preparado en /tmp/f04-api-contract-draft.md:
validarlo contra fuentes antes de incorporarlo. Recepción nueva F04 debe crear
ORIGINAL/recibo/candidato/intención en la misma TX tenant; relay posterior sin falsa
atomicidad entre bases. Replay COMMITTED no crea nuevos candidatos, no ingesta retroactiva.
Mantener respuestas/límites/ACL/upload/original F03, perfil opt-in conocido.
Lista versiones acotada/cursor firmado; jobs filtra tenant+vínculo documental/ACL;
sin texto/chunks/blob/secretos/tokens en control o respuestas de progreso.
Reader conserva SQL readonly sin permisos ops: vincular jobs mediante metadata pública
de control y conocimiento autorizado, no ampliar grants para consultar el journal.
DocumentStateService ya probado preserva objetos/versiones y bloquea commit tardío.
Pruebas HTTP/SQL reales de ambas topologías, permisos/revocaciones, errores y regresión.
Luego T007 aceptación F04 completa y postmerge; solo después F05, cuya decisión D06
modelo/dimensión debe tratarse bajo su gobernanza, sin anticiparla.

## Acceso y operación

Sesión diaria hasta 2026-11-02T06:38:16-05:00. Reutilizar sin password/exportar bearer,
renovar día/root/unseal por iniciativa. Entregas limitadas API/worker separadas.
Cada consumidor normal cierra y revoca su app token: replace ANTES del siguiente;
tras crash, ensure reutiliza token aún activo y recuperación lo revoca al cerrar.
API puede necesitar ensure después de una hora, sin reinicio ni password.
No ejecutar en paralelo herramientas que toman el día; no compartir consumer.lock.

Scripts f04_runtime_host.py y f03_runtime_host.py aceptan --f02-env del checkout operativo.
Venv /home/diego/proyectos/rag-platform-f04-parser-venv, PYTHONPATH=src, pytest/ruff.
No editar el comprobador mientras un contenedor use su bind. Logs privados solo en VM;
salidas PASS/códigos cerrados. Sin F05/PUBLISHED/main/tag/producción/cambio de visibilidad,
purge/downgrade/passwords/políticas nuevas. Conservar historial/current_version_id original.
