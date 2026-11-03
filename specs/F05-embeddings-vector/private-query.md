# Consulta privada al trabajador Qwen

Implementa ADR0012, aprobado por Diego. El transporte está apagado por defecto.
La API no carga Torch ni pesos; usa el mismo modelo del trabajador EMBED.
No se abre puerto público ni se cambian esquemas, políticas o documentos.

## Preparación
Usar exclusivamente una revisión integrada con CI y postmerge correctos.
Comprobar que las cuatro recuperaciones del journal b6e1cd49609c4f6e8b8de8f06ff2f268
terminaron antes de iniciar un trabajador normal que pueda recoger sus intents.
Conservar imágenes, contenedores y journals anteriores. Una sola instancia Qwen.

Construir rag-f05-embedding:t008 con ops/f05/embedding.Dockerfile y su lock opcional,
sin añadir Torch al lock de API. Verificar imports y hashes de todos los módulos
contra la revisión aprobada; no cargar credenciales o pesos durante ese smoke.
Ejecutar scripts/f05_query_host.py prepare: crea o valida únicamente el directorio
tmpfs privado /run/user/1000/rag-f05-query (0700), sin emitir credenciales.

Comprobar estado y hora del día existente. No renovarlo por iniciativa.
Con consumidor anterior detenido y lock libre, emitir entrega limitada mediante
embedding-issue del compose aprobado. Nunca reemplazar la entrega de un consumidor
activo. El trabajador conserva el control exclusivo del handoff durante su vida.

## Arranque y verificación
Combinar ops/f02/compose.yaml, ops/f05/embedding.compose.yaml y
ops/f05/query-runtime.compose.yaml, con .env.f02 privado ya preparado.
Iniciar embedding-worker mediante compose run -d --no-deps --pull never, con nombre
rag-f05-embedding-query-t008 y sin --rm. No arrancar dependencias ni borrar huérfanos.
El overlay habilita RAG_F05_QUERY_ENABLED=1 y el socket /run/f05-query/qwen.sock;
mantiene los límites del trabajador y monta solo su directorio privado en RW.

La prueba scripts/f05_query_rpc_check.py usa la imagen tools:t006 sin Torch,
el handoff F04 independiente y fuente/scripts de la revisión aprobada en RO.
Combinar su overlay query-rpc-check.compose.yaml; manifest API a75adb4c445c46d698abc558a8308112,
prueba Qwen 1c70faf0282548499cd601f6ebe9859e y nuevo journal privado 0700.
RAG_F04_QA_ROOT, RAG_F05_EMBED_QA_ROOT y RAG_F05_RPC_QA_ROOT señalan esas rutas.
Preparar F04 bajo su lock y día vigente; no compartir entrega con otro consumidor.
Ejecutar el servicio f05-query-rpc-check sin dependencias ni pulls.
Verifica cuatro búsquedas con uso/procedencia y rechazos de repositorios ajenos en
el trabajador. No crea corpus, publica documentos ni imprime consulta/vector.
El log query_embedding contiene solo request_id, input_tokens y requests; sirve
para contrastar cálculos reales frente a trazas de consultas denegadas.

## Límites y cierre
Mensajes JSON enmarcados hasta 64 KiB, lectura de solicitud 2 s, count 5 s y embed
30 s en cliente; espera del modelo hasta 2 s y hasta dos handlers. Indexación tiene
prioridad. No hay reintentos automáticos. Una inferencia iniciada puede continuar
después del timeout; no se promete una cota de ejecución del modelo.
El trabajador comprueba firma, membresía, ACL, espacio y perfil antes y después.
La API debe volver a autorizar antes de recuperar/devolver fragmentos.
No registrar contextos firmados, texto, vectores, tokens de acceso ni errores crudos.

Detener limpiamente el nuevo trabajador para deshabilitar el transporte. Se cierran
listener y handlers antes de revocar la entrega; solo se retira su socket propio.
Conservar contenedor e imagen. No hay migración ni downgrade de bases de datos.
Esta prueba no acepta por sí sola HTTP, ANN, calidad de recuperación ni F05.
