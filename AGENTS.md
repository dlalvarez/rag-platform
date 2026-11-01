# Instrucciones obligatorias para Codex — RAG Platform

Antes de tocar código o documentación, leer `docs/01-constitution.md`, `docs/02-architecture.md`, `docs/03-tenancy-security.md`, `docs/10-roadmap.md` y la spec de la fase asignada.

## Reglas de ejecución

- Trabajar en el roadmap original autorizado por Diego, en orden de dependencias.
  Su instrucción del 2026-11-01 autoriza continuidad entre tareas y fases, sin
  confirmaciones rutinarias. No anticipar fases cuya dependencia no esté aceptada.
- GitHub es la fuente de verdad; cada entrega en rama y PR, nunca desplegar en producción por iniciativa propia.
- No modificar ADR aprobado, constitución, contratos externos ni estructura de tenancy sin propuesta de cambio y aprobación explícita. `docs/01-constitution.md` es fuente canónica; `.specify/memory/constitution.md`, si existe, es una copia derivada que debe sincronizarse.
- Una BD por tenant. `rag_control` no almacena documentos, chunks, embeddings, prompts privados ni mensajes de conversación.
- No hacer joins entre bases de datos de distintos tenants ni agregarlos en consultas SQL compartidas.
- Nunca usar `tenant_id` enviado por un cliente sin autenticar/autorizar en el contexto servidor.
- Los servicios de datos usan conexión por tenant, credenciales propias y pools con límites; ningún usuario final recibe credenciales SQL.
- Probar *negative paths*: accesos cruzados, URLs de objetos, idempotencia, fallos parciales, límites, recuperación de errores y abstenciones RAG.
- Tests offline reproducibles, sin requerir servicios pagados ni API keys reales. Pruebas de integración online marcadas aparte.
- No incluir secretos, documentos reales sensibles ni credenciales en repositorio, logs, fixtures ni respuestas de LLM.
- Preferir diseño legible, tipado, modular y migraciones Alembic separadas para `control` y `tenant`.
- Toda funcionalidad debe tener evidencia de aceptación y manual mínimo; no afirmar que está completa sin pruebas.

## Al comenzar cada tarea

1. Resumir alcance, supuestos y archivos previstos.
2. Identificar los criterios de aceptación afectados (`AC-*`).
3. Detectar conflictos con la constitución/ADRs; si existen, no resolverlos unilateralmente.
4. Proponer cambios mínimos y pruebas necesarias.

## Al cerrar cada tarea

Entregar: resumen de cambios, archivos, migraciones, pruebas ejecutadas con resultados, pruebas no ejecutadas y motivo, riesgos remanentes, cambios de API/configuración, evidencia de no regresión y referencia a requisitos/AC. No marcar *done* si el flujo real falla.

## Alcance tecnológico

Python, FastAPI, PostgreSQL/pgvector, MinIO/S3, workers Python y frontend web; proveedor LLM sustituible. n8n es adaptador opcional y no parte obligatoria del core. Evitar microservicios prematuros, integración directa de secretos en configuración, SQL dinámico de identificadores no validado y dependencias no justificadas.


## Instrucción persistente de Diego — continuidad autónoma (2026-11-01)

Diego reiteró: «No puedes detenerte, debes continuar segun el plan» y pidió guardar
esta instrucción para no repetir paradas injustificadas. [ADR-0010](docs/adr/0010-roadmap-continuity.md)
registra su autorización; no es una ampliación inferida por Codex.

- Al completar una tarea, PR o fase, revisar evidencia/CI/postmerge y seguir con la
  siguiente actividad del roadmap original. El cierre de una fase es un punto de
  control, no un motivo para terminar el trabajo ni esperar otro «procede».
- Preparar plan/tareas de la siguiente fase antes de implementar. La autorización
  continuada cubre su alcance original; no pedir otra aprobación solo por cambiar
  el número de fase o porque su plantilla conserve «borrador».
- Implementar, probar, revisar e integrar hacia develop bajo ADR-0007. No atribuir
  aprobación personal nueva de Diego o revisión independiente al trabajo del agente.
- Consultar solo ante inconsistencia con los contratos/specs o decisión fuera del
  alcance original, stop condition de seguridad/datos, o bloqueo externo comprobado
  que requiera un dato, credencial o acción que el agente no puede resolver.
- Ante bloqueo parcial, seguir con el trabajo autorizado que sea independiente y
  preparar una solución concreta antes de pedir intervención.
- Una duda de implementación rutinaria dentro de las specs se resuelve con criterio
  técnico y evidencia. No convertirla en una aprobación de trámite.
- Toda ejecución manual de código/dependencias/servicios permanece en ragdev01.
  Reutilizar la sesión diaria válida; no pedir password por prueba ni extraer bearer.
  Mantener actualizados NEXT_CODEX_TASK y evidencia para continuar tras reinicios de chat.

La continuidad no permite saltar AC, ignorar CI, ampliar el roadmap, promover a main/tag,
desplegar producción, cambiar visibilidad, borrar datos ni alterar contratos/arquitectura
sin la decisión expresa que corresponda. Conservar sus controles; evitar pausas de trámite.

### Reiteración expresa de Diego — no cerrar el turno por completar un PR

Diego reiteró después de PR #32 que solo debe detenerse el trabajo si hace falta revisar
algo fuera del plan o tomar una decisión con él.
Cerrar una tarea, pasar CI, fusionar un PR o actualizar evidencia no autoriza terminar
el turno. Comunicar esos hitos como avances y empezar la siguiente actividad autorizada.
No pedir «procede» ni presentar una lista de próximos pasos como sustituto de ejecutarlos.
Al recuperar contexto, leer NEXT_CODEX_TASK y continuar desde la primera actividad
pendiente. Consultar solo cuando exista una decisión real con los criterios ya definidos;
ante bloqueo parcial, avanzar en lo independiente. Mantener los controles de seguridad,
specs, CI y revisión; la continuidad no permite omitirlos.
