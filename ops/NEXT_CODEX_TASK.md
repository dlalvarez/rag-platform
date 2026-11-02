# Continuidad F05 — ejecutar adopción revisada, después seguir colaEMBED

PR45..49 integrados; develop992ac7c con CI/postmerge,42 pruebas compat/cola.
Qwen aprobado local1024/coseno/L2;2vCPU intactas. Imágenes API/INGEST t003
preparadas75 módulos SHA correctos, no desplegadas. API actualF04t006; worker detenido.

feat/F05-T003-controlled-adoption prepara controlador/compose/QA y regresión
profile embeddings.799 tests correctos; preflight4 fixtures TLS/roles/scope/snapshot
pasó sin migración persistente. Journal existente0700:
 /home/diego/proyectos/rag-platform-f05-adoption-runs/8f9a197defd04a3baacde6bac5a56886
env /tmp/f05-adoption-8f9a197defd04a3baacde6bac5a56886.env
Herramienta rag-f05-tools:t003; build Dockerfile ops/f05/tools.Dockerfile.
Completar CI/revisión de head, ventana soloAPI según ops/f05/adoption.md,
ejecutar adopt, promoverAPI compatible y regresión limitada. Registrar evidencia,
CI/revisión/merge/postmerge; NO cerrar turno, seguir controlEMBED/T004..T008.

Conservar F04 todos datos/objetos/fixtures; no nuevos tenants/purge/downgrade.
Usar manifest F04a75adb4c445c46d698abc558a8308112 para regresión, no resembrar.
Reemplazar entrega API solo después del cierre del consumidor; QAworker entrega
separada tras cierre previo. No montar día/admin/migrator en API/worker.

Sesión diaria renovada activa hasta2026-11-03T07:14:15-05:00. No bearer en salida
ni renovar/revocar sesión activa/root/unseal. Ya se retiró copia vencida anterior.
No password por prueba. Todo ragdev01, sin main/prod/visibilidad/purge.
AGENTS/ADR0010: continuidad entre tareas/PR/fases, preguntas solo decisiones reales.
