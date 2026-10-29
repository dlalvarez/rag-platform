# 05 — Especificación del procesamiento documental

## Fuentes

MVP: carga manual autenticada de PDF **con texto extraíble**, DOCX, Markdown y TXT. El sistema detecta PDF sin texto útil y notifica `NEEDS_OCR`, sin inventar extracción. Fuentes externas (Google Drive/carpetas) en fases posteriores, mediante adaptadores.

## Máquina de estados

`RECEIVED -> VALIDATING -> EXTRACTING -> CHUNKING -> EMBEDDING -> READY_TO_PUBLISH -> PUBLISHED` con estados alternos `FAILED_RETRYABLE`, `FAILED_TERMINAL`, `NEEDS_OCR`, `REPLACED`, `TOMBSTONED`.

## Algoritmo documental

1. Verificar pertenencia, ACL, cuota, límite de bytes, MIME real/firma y nombre seguro; detectar archivos maliciosos en controles disponibles.
2. Guardar original en espacio privado del tenant con clave opaca y hash SHA-256, persistir recepción idempotente.
3. Registrar trabajo durable: tenant, documento, versión, idempotency key, estado; **sin contenido** en cola de control.
4. Extraer texto/estructura por adaptador, con page mapping y errores explícitos. Respetar tablas, encabezados, bloques de código y secciones cuando sea posible.
5. Normalizar Unicode/espacios preservando significado; no eliminar sistemáticamente puntuación técnica, SQL, parámetros ni código.
6. Crear chunks configurables con metadatos de sección/página; validar offsets, tamaño y cobertura. Decidir límites por tokens cuando sea necesario.
7. Crear embeddings con un space compatible y registrar fallos/reintentos/uso; comprobar dimensiones y ausencia de NaN.
8. Construir y validar versión íntegra; realizar publicación transaccional: pointer `current_version_id` y estado visible solo cuando chunks/vectores estén completos.
9. Mantener versión antigua por política de retención, sin exponer simultáneamente índices incompletos.

## Actualizaciones y borrados

- Reprocesamiento con mismo hash y parámetros = no-op o resultado idempotente.
- Si cambia contenido o configuración relevante, nueva versión. Hash de contenido no sustituye identidad documental (`source_id + source_locator`).
- Eliminación manual -> tombstone inmediato para consulta; eliminación física asíncrona según retención y políticas. Cancelar jobs antiguos o impedir su publicación tardía.
- Conector de sincronización debe diferenciar ausencia temporal/error de listado de **borrado confirmado**; no borrar todo ante un error de API.
- Soportar paginación y checkpoints de conectores, deduplicación, reintentos con backoff y dead-letter / estado terminal inspeccionable.

## Límites y fallas

Timeouts por etapa, tamaño máximo configurable, memoria acotada, streaming cuando aplique y circuit breakers de proveedores. No cargar muchos PDFs grandes en memoria en una ejecución única. Rechazar zip bombs, rutas inseguras y tipos no permitidos. Registro de errores redigido y sin fragmentos sensibles por defecto.

## Trazabilidad

Por documento: fuente, hash, versión de parser, versión de chunker, perfil embedding, número de páginas/chunks, duración/errores, fecha publicación, actor y cita navegable al original autorizado.
