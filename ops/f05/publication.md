# Ensayo físico de publicación F05
T004/T005 parcial, R02/R03; soporte AC01/03/04, sin aceptación completa.

En ragdev01, desde checkout con imagen rag-f05-tools:t003 existente:

```sh
docker compose --project-name rag-f05-qa --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f05/publication.compose.yaml run --rm -T --no-deps f05-publication-check
```

Solo cuatro fixtures del scope fijo, ambas instancias, mounts RO y rollback exterior.
No requiere modelo ni sesión diaria. Usa vectores sintéticos/uso ficticio, no inferencia.
Valida DDL/replay, negativos y publicación completa, ancla original y segundo perfil.
No ejecutarlo como adopción; tenants terminan0004 y control0006. No borrar recursos.

0006 permite PUBLISHED con payload de versión inmutable y puntero PROCESSED solo si
binding, vectores, todos los chunks, uso y auditoría se confirman juntos en tenant.
Lotes/vectores/publicaciones quedan retenidos. Intents tienen identidad inmutable;
dispatch pendiente puede finalizar tras COMPLETE, pero job fijado y resultado no cambian.
Registro administrativo de espacios usa wrapper exacto para0006; no fallback de head.

Uso guarda tokens/requests/duración de lotes persistidos; no promete contabilizar una
inferencia perdida antes del commit ni exactly-once entre control/tenant. El worker
todavía debe aportar fencing/reautorización/heartbeat durante inferencia y reconciliar.
No activar0005/0006 antes de compatibilidad API/worker/originales y ensayo controlado.
Sin downgrade destructivo; espacio/publicación fallidos no se activan ni se purgan.
