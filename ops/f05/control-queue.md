# Ensayo control0007

F05-R02, T003 parcial; soporte para AC-F05-01/02/04, sin acreditarlos completos.
Ejecutar en ragdev01 desde el checkout con imagen rag-f05-tools:t003 existente:

```sh
docker compose --project-name rag-f05-qa --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f05/control-queue.compose.yaml run --rm -T --no-deps f05-control-queue-check
```

Solo migrador control y CA RO; no sesión diaria ni contenido tenant.
Transacción exterior con rollback incluso ante error; snapshots verifican preservación.
Control debe comenzar y terminar en f04_control_0006. No habilita runtime EMBED.
APP_GRANTS consulta privilegios del rol app en catálogo; no usa SET ROLE ni acredita
operaciones con conexión app. Un esquema no confirmado no es visible a otra conexión.
No conceder membresía para hacer pasar el ensayo. Sin downgrade destructivo.


## Consumidor EMBED
EmbeddingQueue exige UUID de espacio y fingerprint hexadecimal64; nunca interpreta
el envelope como permiso de acceso tenant. El fence incluye tenant/actor/documento/
versión/espacio/perfil/intento/token. Reintentos acotados con backoff para dependencias;
perfil/dimensión/vector inválidos, exceso de tokens, baja o revocación son terminales.
El guard conserva lock solo durante confirmación corta; no durante inferencia.
El futuro worker debe renovar lease durante inferencias largas y reautorizar después.
El ensayo incluye replay/reclaim/backoff pero usa una transacción exterior: no acredita
concurrencia entre consumidores con commits independientes. Ningún worker activado.
