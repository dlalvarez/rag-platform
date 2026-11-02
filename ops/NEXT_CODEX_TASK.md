# Continuidad F05 — publicación real verificada; búsqueda en curso

Develop 65f47c8 (PR63). PR60..63 tienen CI del HEAD y postmerge correctos.
Diego aprobó búsqueda HTTP de fragmentos: repository_ids/space_id/query/top_k,
hits con procedencia, similitud y uso; sin asistentes ni generación. No volver a
pedir esa decisión. La ruta todavía no está habilitada.

Diego autorizó expresamente «Sí, actualizar las bases de prueba».
Adopción COMPLETA: control f05_control_0007 y cuatro tenants f05_tenant_0006.
Journal privado 49c88c8301444f33b1e5d6dcbc62a5e3 bajo
/home/diego/proyectos/rag-platform-f05-publication-adoption-runs/.
Fallo22012/FAILED/rollback/recuperar/repetir y conexiones de roles comprobados.
Originales/F04/identidades/jobs/día conservados. Conservar journals anteriores.
No repetir controlador de adopción: los espacios Qwen ya contienen publicaciones.

API compatible rag-f05-api-publication-t006 activa mediante compose run -d
--no-deps --pull never --service-ports --use-aliases, sin borrar API t003 detenida.
Nunca iniciar t003 contra0006. API usa entrega F03, expira aproximadamente
2026-11-02T22:25UTC: comprobar hora/estado y detener consumidor antes de reemplazar.
Día existente vence 2026-11-03T07:14:15-05:00; comprobar, no renovar por iniciativa.
Sin root/configure/reinicios Bao/políticas nuevas/purgas/main/tags/producción.

Regresión completa F02/F03/F04/publicación PASS cuatro fixtures/dos instancias:
OIDC, SQL/TLS/roles/cruces, ACL, S3 propio/cruzado y originales HTTP/SHA.
Una primera corrida tuvo ProtocolError S3; diagnóstico y repetición completa
pasaron sin cambios ni relajar negativos. Causa no demostrada.

Qwen REAL request/verify PASS cuatro atomic explícitos, sin barrido histórico.
Journal privado /home/diego/proyectos/rag-platform-f05-embedding-runs/
1c70faf0282548499cd601f6ebe9859e; verified.json agrega por fixture:
1chunk/1batch/1request/13inputtokens/original_retained=true.
Producción EMBED confirmó cuatro jobs SUCCEEDED, publicación y consumo persistidos;
solicitud repetida idempotente y original HTTP/SHA verificados.
Trabajador rag-f02-dev-embedding-worker-1 detenido limpiamente y conservado.
Imagen rag-f05-embedding:t004, modelo revision97b0c614... RO.
No confundir esta prueba con calidad de recuperación ni crash/TTL real.

Rama feat/F05-T006-query-service en worktree f03-schema, basada en develop65f47c8.
Referencia exacta integrada PR63, 949tests y SQL4fixtures/rollback sobre0006 correctos.
Servicio nuevo: ACL antes de proveedor, inferencia sin conexiones abiertas, contexto
nuevo y ACL/perfil repetidos. 18tests reales SQLite,967suite y7selecciónQA, sin HTTP.
QA Qwen/SQL preparada en search-check.compose.yaml y f05_search_check.py, no ejecutada.
Revisar/CI/merge/postmerge antes de usar entrega F05 y modelo RO con cuatro atomic
publicados. No crea corpus ni jobs; cierra su token. Ver search-service.md.

Siguiente: revisión/CI/merge/postmerge del componente exacto; después servicio,
ANN/HTTP y pruebas reales de recuperación entre commits, inferencia larga/TTL30s,
heartbeat/fences y reautorización. Conservar corpus y recursos. T003..T008/F05 abiertas.
No repetir benchmark de capacidad sin cambio/riesgo. Todo ejecución/dependencias en
ragdev01, Mac solo SSH/documentos. Seguir AGENTS y ADR0007/0010 autónomamente.
GitHub es fuente de verdad; conector para push, árbol idéntico al probado antes del
commit, transferencias pequeñas verificadas. No cerrar turno por tarea/PR/fase.
