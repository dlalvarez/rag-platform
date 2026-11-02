# Ensayo del ancla original
F05 T005 parcial, R02/R03, soporte AC01/03/04; no aceptación de publicación.

En ragdev01, desde checkout con imagen rag-f05-tools:t003 existente:

```sh
docker compose --project-name rag-f05-qa --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f05/anchor.compose.yaml run --rm -T --no-deps f05-anchor-check
```

Usa credenciales de QA ya existentes y mounts RO; no sesión diaria ni exportaciones.
Solo cuatro fixtures del scope fijo, en ambas instancias, con transacción exterior y
rollback. Snapshots históricos y catálogo iguales antes/después. Tenants empiezan y
terminan0004; no actualizar desired/observed ni aceptar0005 en runtime antes de preparar
compatibilidad. No activar la migración por ejecutar Alembic head indiscriminadamente.

0005 agrega ancla inmutable, pero current_version_kind sigue ORIGINAL por constraint
F04. INSERT de receptor anterior omite el ancla y el trigger la completa; FK diferida
permite la secuencia documento/versión original en una transacción. App no recibe
UPDATE del ancla. Owner prueba su guard; no se amplían grants para pasar negativos.
Sin downgrade destructivo. Todavía no hay publicación/usage ni cambio de descarga.
