# Compatibilidad de publicación F05
Perfil embedding_publication acepta solo f05_tenant_0006. RAG_F05_PUBLICATION_ENABLED
por defecto0; valor1 exige RAG_F05_ENABLED/F04/F03 todos1. ContextoHMAC separado.
Worker INGEST usa misma bandera y conserva180s de lease. No activar unilateralmente
sobre tenants0004; preparar ventana de adopción y compatibilidad antes de recrear API.

El receptor sigue INSERT de original con trigger de ancla0005. Las vistas de original
y replay y la nueva ingesta consultan original_version_id bajo perfil nuevo, aunque
current_version_id sea PROCESSED/PUBLISHED. Estado de documento activo sigueRECEIVED;
tombstone/ACL permanecen. Worker INGEST trata PUBLISHED como resultado ya completado.

El runner controlado usa target0006 y fuentes0004/0005/0006 explícitas; error deja
FAILED/observedNULL, nunca READY falso ni fallback a otro perfil.0007control EMBED
es una migración separada y aún no está adoptada. No ejecutar Alembic head a ciegas.

SQL opt-in con publication.compose.yaml valida consultas de metadata y nueva solicitud
de ingesta tras publicación, con rollback4fixtures/2instancias. No acredita descarga
HTTP/S3 postpublicación ni reinicio real. Probar esos flujos en ventana revisada junto
a nuevo worker y las regresiones anteriores. No purgar ni hacer downgrade destructivo.
