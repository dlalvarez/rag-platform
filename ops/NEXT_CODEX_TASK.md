# Continuidad F05 — fundación adoptada; seguir controlEMBED/T004

PR45..49 integrados; develop992ac7c. PR50 controlador/adopción en
feat/F05-T003-controlled-adoption, completar evidencia/CI/revisión/merge/postmerge.
Head previof9ab217 CI/revisión y ventana reales correctos; journal privado:
 /home/diego/proyectos/rag-platform-f05-adoption-runs/8f9a197defd04a3baacde6bac5a56886
env /tmp/f05-adoption-8f9a197defd04a3baacde6bac5a56886.env
No repetir ventana/preflight/journal ni resembrar: adopción ya completada4 fixtures.

ACTUAL: cuatro tenants f05_tenant_0004 READY, catálogo/tablaQwen vacíos por tenant.
API rag-f05-api:t003 activa HTTPS/healthF05,75 módulos SHA verificados, rootfs/bindsRO.
Worker anterior rag-f04-worker:t006 detenido (exit 0), conservarlo; no arrancarlo contraF05.
Imagen rag-f05-ingestion:t003 preparada compatible, aún no iniciada.
Infraestructura/IdP/F00 IDs conservados; no vCPU/secretos tenant/políticas cambiados.
Regresión F01..F04 HTTP/SQL/S3 pasó 4 fixtures, logs privados con positivos sin canaries.
F04manifest a75adb4c445c46d698abc558a8308112 conservado. No nuevos tenants/objetos.

Seguir T003 control0007: añadir space_id/fingerprint paraEMBED, índices únicos
parciales INGEST yEMBED/version+space, códigos cerrados; conservar jobs anteriores.
INGEST claim/fence ya filtran kind (PR49); vistas versiones/job ya filtranINGEST.
Probar controlDDL rollback/repetición, ambas clases sin confusión, sin contenido
encontrol. Después T004 embeddingworker/usage/retry/fencing yT005 publicación/ancla,
T006 queryexactANN, T007ops, T008aceptación. No cerrar turno por PR.

Qwen aprobado local1024/coseno/L2, revisión y límite512/batch4 ADR0011.
Primera medición ficticia no calidad dominio/F06 ni capacidad concurrente.
Modelo /srv/rag-data/rag-platform/models/qwen3-embedding-0.6b/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
Entorno /home/diego/proyectos/rag-platform-f05-inference-venv; lock separado.
Sesión diaria activa hasta2026-11-03T07:14:15-05:00; no exportar/renovar/revocar/root.
API entrega nueva tras cierre, QAworker entrega consumida/cerrada y revocada:
replace antes de otra QA conworker. No revocarAPI ni pedir password por prueba.
Todo ragdev01, conservar recursos, sin main/prod/visibilidad/purge. AGENTS/ADR0010.
