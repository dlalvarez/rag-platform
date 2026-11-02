# Continuidad F05 — T003 fundación y compatibilidad pendiente

Qwen aprobado: PR45/46/47 integrados; developce4b97d, CI/postmerge correctos.
Qwen local1024/coseno,2vCPU intactas; primera medición ficticia conservada.
Rutas/lock/limitaciones en ADR0011 y qwen-local.md; no repetir selección.

feat/F05-T003-space-schema contiene fundación tenant0004/space/vector/HNSW,
savepoints y ensayo rollback sobre cuatro fixtures/ambas instancias.
Completar evidencia/CI/revisión/merge/postmerge; seguir perfil F05 explícito de
migración/resolver/API y control EMBED, luego worker/publicación/consulta.
T003 sigue abierta. NO adoptar head0004 en fixtures hasta runtime compatible.
Migraciones F01..F04, originales, chunks, roles/refs y recursos retenidos.

Sesión diaria renovada por Diego, activa hasta2026-11-03T07:14:15-05:00.
No extraer bearer/renovar/revocar sesión activa. Para futura sesión vencida,
start rechaza copia local existente: verificar rechazo servidor y usar procedimiento
daily revoke antes de volver a pedir start. Ya se retiró la copia caducada anterior.
No password por prueba/root/unseal. Usar sesión vigente secuencialmente.

API F04 t006/worker t006 detenido; no nuevas credenciales/tenants/servicios.
Sin main/prod/visibilidad/purge. AGENTS/ADR0010: continuar entre tareas y PR.
