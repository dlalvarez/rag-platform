# F05 T003 — compatibilidad explícita antes de adoptar

Perfil embeddings=f05_tenant_0004, fuentes de migración solo F04/head propio.
No cambiar perfiles identity/documents/ingestion ni aceptar heads desconocidos.
Prueba de contexto F05 separada por propósito HMAC; proof F04 no sirve para F05.
Resolver exige desired=observed=head exacto, lifecycle/membresía/ACL vigentes.
Control de migración refleja FAILED y observed nulo ante error/runner incorrecto.

RAG_F05_ENABLED opt-in exige F03 y F04 habilitados en API; ausente conserva F04.
Runtime documental F05 mantiene upload, original, versiones, jobs INGEST y tombstone.
No endpoints de búsqueda/chat ni inferencia en API. Qwen sigue adaptador separado.
Worker de INGEST admite profile F05 con bandera explícita, no migra ni administra.
Su cola filtra INGEST en claim y fencing; no toma ni confirma futuros EMBED.
No ampliar claims de aceptación a workers EMBED aún inexistentes.

ops/f05/api.compose.yaml y worker-compat.compose.yaml sobre perfiles existentes,
imágenes nuevas rag-f05-api:t003/rag-f05-ingestion:t003; identidad AppRole limitada
y12 referencias existentes, sin cambio de políticas/root/TTL/contraseñas.
No recrear infraestructura. Worker anterior detenido, no arrancarlo con head F05.
Construir/verificar imágenes fuente exacta tras CI/revisión antes de adoptar datos.

Adopción persistente aún no ejecutada por este PR: preparar snapshot F04/control,
fallo DDL/recovery bajo migración controlada, repetir y verificar objetos/originales.
API compatible debe estar preparada; secuenciar parada/cierre, reemplazo de entrega
limitada tras cierre, migración de cuatro fixtures e inicio API F05. Sin fallback
a head viejo, downgrade/purge ni nuevos tenants. Si falla, estado honesto y recursos
retenidos; recuperar el mismo target antes de continuar. No declarar F05 completa.
