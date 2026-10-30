# Evidencias F00 — pendiente de ejecución

**Estado:** ninguna prueba de aceptación técnica F00 está declarada como completada. La validación documental de la realineación no sustituye las pruebas F00.

| Criterio | Prueba prevista | Resultado | Evidencia |
|---|---|---|---|
| AC-F00-01 | Clon limpio, pytest, lint | Pendiente | — |
| AC-F00-02 | Compose PostgreSQL/pgvector, MinIO, API placeholder | Pendiente | — |
| AC-F00-03 | CI de docs, lint y tests mínimos | Parcial: docs CI; resto pendiente | — |
| AC-F00-04 | Referencias canónicas y AGENTS desde raíz | Revisión documental preliminar | — |

Completar con fecha, versión, comandos reproducibles, salidas reales, entorno, hallazgos, regresiones, límites y aprobación humana cuando Codex implemente F00.

## Registro de planificación (2026-10-30)

Revisados main@1532ee74f0b1b41f06cc1d0d369e2eac386cdef0, PR #3 integrado e Issue #4 abierto. Este registro es documental; no acredita pytest, lint, Compose, salud de servicios ni ejecución en ragdev01. Ver [matriz de pruebas previstas V01–V05](plan.md) y [decisiones pendientes](ratification.md).

Para cada ejecución técnica registrar: requisito/AC/tarea/ID de test y ruta real, commit, fecha, ambiente, versiones, comando exacto, código de salida, resultado esperado/obtenido y enlace a log saneado o ejecución CI. Registrar también fallos, pruebas omitidas y motivo, regresiones, rollback y revisor humano. No copiar secretos a las evidencias.

La revisión preliminar AC-F00-04 no cierra ese criterio; volver a validarlo en el clon limpio del PR técnico. No se han acreditado pruebas de aislamiento ni backup/restore.

### Validación documental de esta propuesta

Ejecutada el 2026-10-30 en copia local de los 73 archivos de main recuperados por API, con los diez archivos propuestos aplicados: `python3 scripts/check_docs.py`, salida 0: `OK: SDD baseline, 12 phases, P01-P14, canonical references, ADRs and links.`
No es una instalación desde clon limpio ni una prueba técnica F00. La CI del commit publicado debe consultarse por separado en el PR.
