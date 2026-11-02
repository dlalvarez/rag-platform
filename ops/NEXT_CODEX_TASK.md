# Continuidad F05 — publicación real verificada; búsqueda en curso

Develop 396870c (PR65). PR60..65 tienen CI del HEAD y postmerge correctos.
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
Nunca iniciar t003 contra0006. API usa entrega F03 reemplazada bajo lock, expira aproximadamente
2026-11-02T23:22UTC: comprobar hora/estado y detener consumidor antes de reemplazar.
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

Rama fix/F05-recovery-active-fixtures en worktree f03-schema sobre develop396870c.
Primer prepare sobre positive API rechazado: F04 los daba de baja para aceptación.
Budgets1chunk/16tokens cuatro fixtures; ningún intent creado según diagnóstico rollback.
Journal212416ed conservado. Corrección preparada hacia positive-txt del manifest
worker15bbc3e906dd4cdbad151c9ab055d8d3, con gate de estado antes de leer/tokenizar.
Revisión/CI/merge/postmerge antes de nuevo journal privado y prepare/crash/resume.
No restaurar tombstones, barrer historia ni cambiar código de producción.
API t006 reabierta en mismo contenedor, entrega F03 vigente23:22UTC, HTTPS health200.
Lock F03 real: /run/user/1000/rag-f03-application/consumer.lock.

Diego aprobó expresamente la conexión privada API->trabajador Qwen existente:
una copia del modelo/sin puerto público/terceros, CPU compartida/espera acotada,
reautorización antes de fragmentos, soloDEV sin cambiar documentos/BD.
Ya NO esperar otra autorización. Registrar ADR0012 antes de implementación.
Contrato HTTP de fragmentos y adopción persistente también ya aprobados.
Continuar recuperación y transporte/ANN, todo en ragdev01.

Siguiente: revisión/CI/merge/postmerge del componente exacto; después servicio,
ANN/HTTP y pruebas reales de recuperación entre commits, inferencia larga/TTL30s,
heartbeat/fences y reautorización. Conservar corpus y recursos. T003..T008/F05 abiertas.
No repetir benchmark de capacidad sin cambio/riesgo. Todo ejecución/dependencias en
ragdev01, Mac solo SSH/documentos. Seguir AGENTS y ADR0007/0010 autónomamente.
GitHub es fuente de verdad; conector para push, árbol idéntico al probado antes del
commit, transferencias pequeñas verificadas. No cerrar turno por tarea/PR/fase.
