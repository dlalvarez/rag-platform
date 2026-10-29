# 12 — Modelo inicial de amenazas (STRIDE simplificado)

| Riesgo | Impacto | Control obligatorio | Test |
|---|---|---|---|
| IDOR: usuario manipula tenant/repo/document ID | Exfiltración | Contexto autenticado, membership y ACL antes de resolver recurso | SEC-01 |
| Fuga por pool/worker/caché cross-tenant | Exfiltración | TenantContext inmutable, pools aislados, límites y limpieza | SEC-02 |
| Roles PostgreSQL con CONNECT indebido | Acceso directo entre DBs | Roles por tenant, revocar PUBLIC y prueba credencial A vs DB B | SEC-03 |
| Bucket o URL firmada cruzada | Filtración de originales | Buckets/policies/credenciales por tenant, URLs expirables | SEC-04 |
| Prompt injection dentro de documentos | Manipulación de respuesta/acciones | Contexto no confiable, tools deshabilitadas en MVP, citas verificadas | SEC-05 |
| Inyección SQL/nombre físico embebido | Manipulación/escalada | Parámetros tipados e identificadores generados/allowlist | SEC-06 |
| Archivos maliciosos / zip bombs | DoS / RCE parser | Validación MIME, límites, parsers aislados, timeouts | SEC-07 |
| Falla tras escribir vectores | Índice parcial/inconsistente | Versionado y publicación atómica | SEC-08 |
| Error de conector = borrado masivo | Pérdida datos | Sincronización con confirmación y checkpoint | SEC-09 |
| Contenido en logs o control plane | Filtración lateral | Redacción, telemetría agregada, secretos en store | SEC-10 |
| Consumo LLM sin cuotas | Costos fuera de control | Cuotas, límites, metering y timeout | SEC-11 |
| Restaura BD sin objetos | Citas rotas / pérdida contexto | Backup/restore coordinado con almacenamiento | SEC-12 |
| Tenant suspendido sigue operando jobs | Acceso no autorizado | Revalidar estado antes de ejecución/publicación | SEC-13 |

## Principios

Denegar por defecto, defensa en profundidad, trazabilidad, mínimo privilegio, datos sensibles solo donde corresponden. Las amenazas con impacto de filtración/aislamiento bloquean el merge, aunque los tests funcionales pasen.
