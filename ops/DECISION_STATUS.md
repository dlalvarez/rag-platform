# Estado de aprobación del paquete

Este paquete documenta decisiones expresadas en la conversación y propuestas de implementación técnica. No debe confundirse **propuesta** con **código aprobado/desplegado**.

## Confirmado en la conversación

- RAG SaaS multi-tenant con usuarios personales y empresariales.
- PostgreSQL + pgvector como fundamento del repositorio vectorial.
- Fuerte aislamiento **base PostgreSQL por tenant** y BD central de control.
- Infraestructura preparada para DB de tenants en distintas instancias.
- Codex + GitHub con desarrollo guiado por especificaciones (SDD).

## Propuestas técnicas sujetas a revisión de fase

- FastAPI/monolito modular/workers, MinIO/S3, OIDC, PostgreSQL job queue, modelos concretos, versiones de librerías, framework UI, cuotas y SLOs.
- Nombres de esquemas y endpoints: contrato de referencia que se consolida fase a fase.
- Flujo de ramas `main`/`develop` y política de protección: adoptar formalmente en F00. La validación documental en GitHub Actions ya existe, pero no sustituye la CI de lint/tests requerida por F00.

## Estado actualizado de ejecución (2026-10-28)

- Repositorio GitHub `dlalvarez/rag-platform` creado y PR #2 documental fusionado. El PR #2 **no completó la F00 técnica** del kit.
- Servidor dev `ragdev01` listo: Ubuntu 24.04.5, Docker Engine 29.9.2, Compose 5.6.1, SSD de 120 GiB montado en `/srv/rag-data` y snapshot VMM local. Ver `docs/operations/development-host.md`.
- **Pendiente:** F00-R01..05/AC-F00-01..04 (bootstrap Python/CI/Compose real); F01 y fases siguientes, backups externos y restauración verificada. No se ha desplegado PostgreSQL/pgvector ni MinIO para el producto.
- PR #3 de realineación integrado el 2026-10-29. Ninguna elección futura del stack queda aprobada por el solo hecho de haber restaurado archivos.
- GitHub está actualmente configurado como **repositorio público**; el kit inicial proponía privado. Decidir formalmente política de visibilidad antes de incorporar material sensible; nunca guardar secretos en Git.

## Jerarquía y conflicto resuelto

`docs/01-constitution.md` es la única constitución normativa y `docs/10-roadmap.md` el roadmap canónico. `CONSTITUTION.md` y `docs/roadmap.md` son enlaces de referencia. Documentos anteriores del PR #2 archivados en `docs/history/pr2/`.

**Pendiente de ratificar:** ADR 0002 (monolito modular) y ADR 0004 (gestión concreta de secretos/objetos) conservan su condición de propuesta. ADR 0001 y ADR 0003 reflejan decisiones ya acordadas.

## Propuesta de ratificación F00 (2026-10-30)

Preparación autorizada de planificación y gobierno; revisión y aprobación del contenido pendientes. Ver [registro F00](../specs/F00-fundacion-repositorio/ratification.md) y [ADR-0006](../docs/adr/0006-branch-policy.md).
Develop se propone crear desde main después del merge humano del PR documental. Protección no verificada ni modificada; deben decidirse checks, revisores y excepciones antes de ampliar CI. F00 técnica e Issue #4 siguen pendientes. Repositorio público sin cambio de visibilidad. No se ejecutó ningún servicio en ragdev01.

## Actualización F00 autorizada (2026-10-30)

PR #5 aprobado e integrado; ADR-0002 y ADR-0006 ratificados, develop creada y ruleset 26218280 activo. Diego es único revisor/responsable de merge. Desarrollo y pruebas F00 autorizados por SSH exclusivamente en ragdev01, con datos sintéticos. Checkout /home/diego/proyectos/rag-platform; datos /srv/rag-data/rag-platform/f00. Ver F00_RUNBOOK.md y evidence F00 para resultados. F00 no se declara cerrada hasta su revisión; ADR-0004/F01 y backups externos permanecen pendientes.

## Estado vigente tras cierre F00 y preparación F01 (2026-10-30)

F00 aceptada y cerrada en PR #6/Issue #4, con pruebas y CI postmerge exitosas; develop@85cd39f401b48e312c1e4fd61906543a4ff588fe. Las menciones anteriores de revisión pendiente corresponden al momento de entrega. F01 se planifica en Issue #7 y specs/F01-aislamiento-provisionamiento, sin implementación. Diego eligió incluir OpenBao en la propuesta; ADR-0004, spec/plan/tasks y custodia de unseal siguen pendientes de ratificación/preparación. No se crearon tenants ni cambió ningún servicio por el trabajo documental F01. Ver ops/NEXT_CODEX_TASK.md.


## Estado vigente F01 T001 (2026-10-30)

PR #8 ratificado por Diego e integrado en develop@f2c74400d2cafb5fce065b6eb0db23243731f8cf.
Spec/plan/tasks y ADR-0004 aprobados; destinos de custodia confirmados preparados.
T001 en curso en feat/F01-T001-control-secrets, exclusivamente en ragdev01.
Catálogo control con Alembic y prueba PostgreSQL/TLS real; OpenBao arrancado sin
inicializar. Ninguna clave de desbloqueo generada; ningún AC F01 completo.
Bootstrap solo en terminal de Diego, sin capturar secretos; ver [runbook](f01/README.md).
Las menciones anteriores de propuestas pendientes son históricas.


## Resultado técnico T001 (2026-10-30)

PR #9: catálogo/control Alembic y SecretStore implementados y ensayados en ragdev01.
Diego completó bootstrap, confirmó root inicial revocado, recuperación de canary tras
restart/unseal y token AppRole caducado rechazado HTTP 403 con nodo desbloqueado.
Token ficticio rechazado HTTP 403; F00 saludable e integración correcta. 53 tests offline.
Checks GitHub Actions recientes observados queued sin runner; no declararlos exitosos.
Revisión/aceptación/merge de PR #9 pendientes. No se inicia T002 ni se cierra F01/Issue #7.
Ver evidence F01 y NEXT_CODEX_TASK.md. Las notas anteriores son históricas.
