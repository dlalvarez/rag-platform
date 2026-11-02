# Worker EMBED F05, código preparado
T004 parcial. No ejecutar sobre la instalación actual0004/control0006. Falta imagen y
ventana de adopción revisada; no hay evidencia de proceso Qwen E2E todavía.

Entrada: python -m rag_platform.embeddings.worker_main, con RAG_F05_ENABLED=1 y
RAG_F05_PUBLICATION_ENABLED=1. Exige perfil tenant0006 y shape EMBED de control0007;
control head exacto se comprueba en el controlador migrador previo, sin otorgar SELECT
de Alembic control al runtime. Modelo en ruta RO fijada y verificada por hashes.
Torch/inferencia van en entorno opcional del worker, nunca lock/dependencias de API.

Solo intents explícitos. El ingestor nuevo crea intent Qwen al confirmar READY bajo
perfil0006; READY histórico no se barre automáticamente. Request administrativo/QA
de versión anterior requiere autorización y ACL frescas del actor, no credencial admin.
Relay lleva solo IDs/hash a control, filtrado por fingerprint del provider.

Un lote por proceso; límites Qwen512/batch4. Lease180s y heartbeat cada30s durante
inferencia, sin tenant transaction; después contexto nuevo y revalidación ACL/tombstone.
Cota64chunks/32768tokens de contenido guardado,3intentos. Un batch sin commit puede
repetirse; vectores+uso guardados juntos y resultados completos se reconcilian sin
volver a inferir. No prometer coste ni uso exactly-once entre fallos de proceso/BD.
Usage contabiliza lotes exitosos persistidos, no es billing ni garantía de uso total
del proveedor cuando una inferencia se pierde antes de commit.

Entrega privada SQL-only en /run/f05-worker, consumidor único. No token de día,
migrador, root ni auto-renew. Antes de faltar180s o tras DENIED/INVALID, para de tomar
jobs y cierra; trabajo en curso pasa RETRY/STOP_REQUESTED con parciales retenidos.
Reemitir entrega solo tras cierre/lock libre con herramienta aprobada y sesión diaria
válida; no reemplazar mientras consumidor tenga lock. No nuevas políticas Bao.
Main valida esquema/perfil antes de cargar modelo y desactiva red HF/trust_remote_code.
No texto, vectores ni errores de proveedor en logs/control; solo job_id y código cerrado.

Pruebas actuales:47 casos nuevos/904 completos, worker/heartbeat/handoff; SQL componentes
tenant y control en4fixtures/2instancias, todo rollback. Guard del componente SQL es
sintético y provider determinista; no confundir con ciclo real control/tenant/modelo.
Pendiente ensayar proceso real, reautorización larga, crash, TLS/roles/handoffs y
originales HTTP/S3 postpublicación antes de aceptar T004/T005/F05. Conservar recursos.
