# Búsqueda HTTP de fragmentos

Implementa el contrato aprobado de docs/07-api-contracts.md sobre SearchService
y ADR0012. No incorpora asistentes ni generación. RAG_F05_SEARCH_ENABLED vale0
por defecto y solo admite1 con el perfil embedding_publication completo.

POST /api/v1/tenants/{tenant_id}/search exige identidad OIDC y membresía vigente.
JSON con exactamente repository_ids (1..16 UUID distintos), space_id, query
(1..8192 caracteres válidos, no vacío) y top_k (entero estricto1..50). Rechaza
parámetros extra, claves duplicadas, NaN, compresión y framing ambiguo. Máximo
64KiB/20s para el cuerpo, dos operaciones concurrentes y respuesta hasta256KiB.
Los límites de tokens son reales e incluyen instrucción/especiales, sin truncar.
El cliente privado tiene count5s/embed30s; no reintentos ni modelo local en API.

Todas las ACL y perfil se comprueban antes de tokenizar/inferir, se libera SQL
durante el proveedor y se reautoriza antes de recuperar fragmentos. Perfil409,
validación422, tamaño413, saturación429 y dependencia503, con vocabulario cerrado.
La respuesta ofrece request_id, space_id, hits y usage. Solo identificadores
lógicos, score coseno, excerpt autorizado, page/section; sin vector/query/secretos.
Cache-Control no-store y X-Request-ID del servidor, ignorando la traza entrante.

## Operación de desarrollo
Requiere PR revisado/CI/merge/postmerge y prueba privada real antes de activar.
Construir rag-f05-api:t009 mediante ops/f02/api.Dockerfile desde la revisión
integrada. Comprobar hashes/imports de todos los módulos y ausencia de Torch.
Conservar API t006 e imagen anterior; no arrancar t003 contra tenant0006.
Comprobar día vigente sin renovarlo y entrega del único trabajador Qwen t008.

Detener API t006 antes de reemplazar entrega F03 bajo su consumer.lock exclusivo
(/run/user/1000/rag-f03-application). Combinar compose F02, handoff F03,
publication-runtime F05 y search-runtime F05, con .env.f02/.env.f03 privados.
Iniciar api como oneoff persistente con --no-deps --pull never --service-ports
--use-aliases y nombre rag-f05-api-search-t009. No borrar contenedores anteriores.
Solo se añade montaje RO del directorio Unix; no nuevo puerto ni servicio de datos.

## Prueba HTTP preparada
scripts/f05_search_http_check.py y ops/f05/search-http-check.compose.yaml usan
tools:t006 sin Torch, OIDC fixture y HTTPS en red f02, sin credenciales SQL,
handoff, día, migrator o modelo. Fuente/scripts de revisión integrada en RO.
RAG_F04_QA_ROOT apunta al manifest API a75adb4c445c46d698abc558a8308112;
RAG_F05_EMBED_QA_ROOT a 1c70faf0282548499cd601f6ebe9859e;
RAG_F05_RECOVERY_QA_ROOT a b6e1cd49609c4f6e8b8de8f06ff2f268;
RAG_F05_HTTP_QA_ROOT a un nuevo journal0700. Ejecutar el servicio sin deps/pulls.
Cuatro búsquedas, rechazo sin identidad/repos ajenos/assistant/top_k inválido/
tokens excesivos, procedencia/uso y descarga SHA de atomic y recovery por tenant.
No modifica corpus ni guarda texto/vector. Contrastar trazas/uso contra el log
del trabajador: un cálculo por éxito y ninguno para denegaciones.

Cerrar el nuevo API antes de reemplazar entrega o volver a t006; conserva las
bases de datos. Detener trabajador si acaba la prueba o vence su entrega; no
renovar automáticamente. HTTP no acepta por sí solo ANN, calidad o F05.
