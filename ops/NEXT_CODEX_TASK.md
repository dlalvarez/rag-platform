# Tarea activa Codex — F04 T006

Continuidad autónoma bajo AGENTS/ADR0010; no cerrar turno por PR/tarea/fase.
Toda ejecución manual de código/tests/build/servicios en ragdev01, nunca Mac.
PR42 aceptó T002/T003/T005 y quedó integrado en develop4405f848546ebccd2203f902e9032ab88a770ea9,
con CI/revisión/postmerge correctos (19 tests y checkouts limpios).

Worktree /home/diego/proyectos/rag-platform-f03-schema, rama feat/F04-T006-document-api.
Contrato specs/F04-ingesta-versionada/api.md y código opt-in T006 implementados.
702 tests/ruff/formato/docs/diff; imágenes rag-f04-api:t006, worker:t006, tools:t006
preparadas. Publicar PR y revisar CI/head/fuentes exactos antes de promoción manual.
No atribuir despliegue/aceptación T006 a tests offline. T006/T007 y F04 siguen abiertas.

Primera actividad: completar build/inspección exacta, publicar/revisar head, activar solo
API T006 (api.compose.yaml con F02+F03 handoff) y reemplazar entrega después del cierre
de API anterior. Datos/IdP/Bao no reiniciar. Crear run nuevo exclusivo para api-check,
sin repetir seed/adopción anteriores. api-check.compose.yaml reutiliza seed limitado
con tools:t006, siete mounts (solo journal RW), sin día/admin/migrator. Modos seed/verify
con --run UUID. Seed necesita worker detenido: crea originales HTTP y candidatos/
intenciones automáticos, prueba rollback real inyectado tras journal y recuperación
tras lease sin rotación. Manifest privado registra IDs/hashes, recursos conservados.

Después de seed/cierre reemplazar entrega worker y arrancar worker normal con
worker.compose.yaml + worker-api.compose.yaml. Esperar jobs terminales con códigos
saneados, parar limpio; reemplazar entrega y ejecutar api-check verify. Comprueba cuatro
fixtures, reader/ACL/cursor/cruces/jobs/bajas idempotentes y chunks retenidos.
Checkpoints predelete/verified permiten continuar verify tras interrupción; no falsificar
ni borrar sus archivos. Completar logs/temporales y regresiones reales T007 antes de
aceptar F04. Al completar PR seguir actividad siguiente sin pedir aprobación rutinaria.

Fixtures fijas same-a/same-b en instancia compartida, two-a/two-b en dos instancias,
cuatro tenants READY f04_tenant_0003, cola f04_control_0006. No repetir migraciones,
adopción, seed de worker ni parsings de negativos terminales.
Run T005 15bbc3e9-06dd-4cdb-ad15-1c9ab055d8d3 retenido en
/home/diego/proyectos/rag-platform-f04-worker-runs/15bbc3e906dd4cdbad151c9ab055d8d3.
52 originales/cuatro repos e historial/chunks/tombstones retenidos; ACL/membresía
restauradas. Primer run cfe3... conserva solo started.json. Worker normal quedó parado
exit0 después de prueba; API actual t005 compatible F03 hasta promoción T006.

Sesión diaria hasta 2026-11-02T06:38:16-05:00; usar sin password/exportar bearer ni
renovar día/root/unseal por iniciativa. Entregas API/worker separadas, rol existente doce
refs. Consumidor normal revoca app token al cerrar: replace antes del siguiente; tras
crash ensure conserva token vigente. No ejecutar emisores que toman día en paralelo.
Nunca editar código QA mientras se monte en un contenedor activo. Logs brutos solo VM,
publicar PASS/códigos. Venv /home/diego/proyectos/rag-platform-f04-parser-venv, PYTHONPATH=src.

Sin embeddings/PUBLISHED/F05 antes de aceptar F04; sin main/tag/producción/visibilidad/
purge/downgrade/passwords/políticas nuevas. Mantener originales/current_version_id.
Después de F04 completa, preparar F05 original; D06 modelo/dimensión es decisión de
arquitectura con su gobernanza. Consultar solo decisiones reales/desvíos/bloqueos,
continuar siempre trabajo independiente.
