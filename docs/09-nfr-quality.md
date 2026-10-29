# 09 — Requisitos no funcionales y estrategia de pruebas

## Objetivos iniciales

| ID | Requisito | Criterio verificable |
|---|---|---|
| NFR-01 | Aislamiento | 100% pruebas negativas de acceso cruzado exitosas; 0 lecturas no autorizadas |
| NFR-02 | Idempotencia | Reintentos de provisión, ingesta y publicación sin duplicación ni pérdida |
| NFR-03 | Seguridad | Secretos ausentes de git, control DB, logs y respuestas; APIs autenticadas |
| NFR-04 | Recuperación | Restaurar tenant + objetos en entorno de prueba y verificar integridad |
| NFR-05 | Observabilidad | Trazas IDs de request/job/tenant, errores y métricas medibles |
| NFR-06 | Búsqueda | Recall@10 >= 0.80 sobre dataset aprobado/baseline MVP; evidencias registradas |
| NFR-07 | Citación | 100% citas devueltas resuelven a chunks autorizados/versiones válidas en fixture |
| NFR-08 | Resiliencia | Simulación de timeout/fallo LLM/BD/objeto sin publicación parcial |
| NFR-09 | Reproducibilidad | Tests unitarios e integrados sin llamar APIs pagadas; entorno dev levantable |
| NFR-10 | Migrabilidad | Migraciones control/tenant separadas y repetibles en dos bases de tenants |

**Latencia:** establecer presupuesto p95 medido para recuperación y chat después del baseline F06–F07; el tiempo del proveedor LLM se mide por separado, sin prometer un número previo a pruebas reales.  
**Disponibilidad/RPO/RTO:** objetivos comerciales se fijarán en F10 tras probar ambiente real y recuperación; no anunciar SLA sin evidencia.

## Pirámide de pruebas

1. Unitarias: parsers, chunks, ACL, routers, quoting, providers mock, estados.
2. Integración: Postgres + pgvector + MinIO local, dos BD tenant/credenciales, migraciones y jobs.
3. Seguridad: lectura/escritura cruzadas API/SQL/objetos, injection, cache/context switching, IDs adivinados.
4. E2E: dos usuarios, dos tenants, carga, publicación, búsqueda, conversación con citas y baja.
5. RAG eval offline: corpus controlado, búsqueda y abstenciones; online opt-in con presupuesto y logs saneados.
6. Resiliencia: fallos de servicios, reintentos, timeouts, workers duplicados, crash entre publicación y eventos.
7. Operacionales: crear tenant, suspender, migrar, backup y restore de extremo a extremo.

## Entrega por PR

Debe adjuntarse matriz requisitos->AC->test, salida de tests con fecha/entorno, cambios de esquema, amenazas afectadas, rollback y riesgos no resueltos. Todo cambio de dependencia/proveedor indica versión probada y motivo.
