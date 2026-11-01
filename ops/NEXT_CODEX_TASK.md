# Tarea activa Codex — F04 ingesta versionada

Leer AGENTS y ADR-0010. No detenerse por cerrar tareas/PR/fases; seguir alcance original.
Toda ejecución manual en ragdev01, sin entorno local. Revisión/merge a develop delegados,
CI exacto y postmerge; sin main/tag, producción, purge ni cambio de visibilidad.

F00..F03 aceptadas. F03 cierre PR #34, develop@4c5b8d3189b71dad6fbe6f2921cbd06b33754871.
Ver specs/F03-repositorios-documentos/evidence.md y comentario postmerge de #34.
562 tests y todas las baterías reales correctas; API normal F03 activa, candidato retirado.
Conservar fixtures, cuatro colisiones T005, repos DELETED y todos los originales/versiones.

## Continuar

Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-planning.
Checkout operativo /home/diego/proyectos/rag-platform en develop, limpio al comenzar.
T001: plan/tareas/checklist/evidencia F04 preparados; validar docs/diff y CI, revisar,
integrar y verificar postmerge. Continuar T002 cola durable y T004 extractores/corpus
según dependencias; no declarar implementación por planificación.

D-05 resuelta como elección técnica del adaptador ya previsto: pypdf/python-docx locales,
sin OCR/modelos ni cambio de arquitectura; no atribuir aprobación personal nueva.
Ver specs/F04-ingesta-versionada/parsers.md y plan.md. Fijar pins/lock, comprobar licencias
transitivas y medir límites en ragdev01 antes de aceptar. No cambiar el roadmap.

Cola control solo identificadores, jamás contenido; tenant guarda versiones/chunks.
Migraciones históricas intactas, evolución aditiva. READY_FOR_EMBEDDING no PUBLISHED.
No fingir atomicidad entre bases. Lease/fencing, autorización vigente y tombstone bloquean
commit tardío; corpus nuevo semántico no reescribe los positivos estructurales F03.

## Acceso y operación conservados

Sesión diaria hasta 2026-11-02T06:38:16-05:00; comprobar estado, no exportar bearer ni
pedir password por batería. No renovar/revocar día ni repetir root/configure automáticamente.
Linger conserva tmpfs tras logout; reboot sí lo elimina. Unseal y custodia con Diego.
API usa solo AppRole F03 de lectura (12 refs) y SQL/S3 tenant; sin día/migrator/IAM admin.
ops/f02/compose.yaml + ops/f03/handoff.compose.yaml; .env.f02 operativo y .env.f03 UID/GID.
En worktree scripts/f03_runtime_host.py requiere --f02-env /home/diego/proyectos/rag-platform/.env.f02.
ensure reutiliza; replace al reiniciar API cuyo token se revocó. No reiniciar infraestructura.
No ejecutar en paralelo baterías que toman el lock diario.

Pruebas: PYTHONPATH=src /home/diego/proyectos/rag-platform/.venv/bin/pytest -q,
ruff check/format, python3 scripts/check_docs.py, git diff --check. Dependencias solo servidor.
No imprimir logs/errores privados: capturar en servidor y devolver códigos/PASS saneados.
