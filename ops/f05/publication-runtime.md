# Runtime y regresión con publicación F05

Preparación para desarrollo, sin arranque automático. Las imágenes rag-f05-api:t006,
rag-f05-ingestion:t006 y rag-f05-tools:t006 contienen el código de publicación.
Se construyen con los Dockerfiles existentes; el lock principal permanece intacto.
Las tres deben pasar importación sin red/credenciales y comparación de los módulos
src con el árbol probado, sin Torch. EMBED conserva su imagen/entorno opcional separado.

## Composición

Combinar ops/f02/compose.yaml, ops/f03/handoff.compose.yaml,
ops/f04/worker.compose.yaml y ops/f05/publication-runtime.compose.yaml.
Usar las variables F02/F03 existentes. El último overlay selecciona imágenes nuevas
y RAG_F05_PUBLICATION_ENABLED=1 para API e INGEST; API exige también F03/F04/F05.
No usar este overlay contra control0006/tenant0004. El controlador debe completar
y verificar control0007/tenant0006 antes de iniciar los procesos compatibles.
No reconstruir implícitamente ni recrear dependencias en la ventana.

API conserva entrega privada F03; INGEST conserva entrega independiente F04.
Antes de reemplazar cada entrega, detener su consumidor, comprobar cierre y lock libre.
Usar herramientas existentes sin imprimir archivos privados ni crear políticas,
renovar día, ejecutar configure o recuperar root.

Tras CI/revisión y adopción verificada, conservar el contenedor API anterior
detenido e iniciar la API compatible como contenedor separado:
compose run -d --no-deps --pull never --service-ports --use-aliases
--name rag-f05-api-publication-t006 api, combinando F02, handoff F03 y este overlay.
No usar --rm; conservar worker F04 detenido y todas las imágenes anteriores.
El cambio de perfil es explícito: el binario anterior no debe seguir contra0006.

## Regresión

ops/f05/publication-regression.compose.yaml añade f05-publication-regression-check.
El wrapper llama a la batería F01..F04 con profile=embedding_publication exacto;
no relaja heads ni modifica la batería histórica. Reutilizar el manifest QA
conservado y las identidades/corpus anteriores, sin resembrar.
La batería usa credenciales de aplicación, no día/bootstrap/migrador; comprueba
OIDC, originales HTTP/SHA, SQL/TLS/roles/cruces, S3 propio/cruzado y privacidad.
Al cerrar revoca solo su entrega INGEST, así que emitir una nueva entrega limitada
después de su cierre antes de iniciar INGEST. No compartir la entrega con un
consumidor activo. No iniciar el worker mediante una llamada global a up.

Las ingestas nuevas bajo0006 solicitan EMBED. La historia READY no se recorre
automáticamente. Para EMBED seguir embedding-operations.md, entrega propia,
modelo RO y flags/perfil explícitos. Solo iniciar el proceso cuando su aceptación
esté preparada; registrar usage real y recuperación antes de aceptar T004/T005.
Las pruebas de importación/configuración no acreditan regresión HTTP/S3 ni Qwen.
