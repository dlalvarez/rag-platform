# Auditoría integral del paquete rector SDD — PR #3

**Fecha de referencia:** 2026-10-28 (Colombia).
**Objeto:** ZIP `Proyecto_RAG_SaaS_SDD_Kit(1).zip`, documento `Documento_Rector_RAG_SaaS_SDD(1).md` y rama `docs/realign-original-sdd` de `dlalvarez/rag-platform`.
**Alcance:** integridad documental, consistencia de autoridad/fases, rutas, scripts, plantillas, seguridad y flujo SDD; no se ejecutan pruebas funcionales de RAG/DB.

## Inventario y preservación

- El ZIP aporta exactamente **53 archivos** con 29 documentos canónicos reproducidos en el Markdown consolidado (la compilación no es autoridad independiente).
- Se recuperaron los 53 archivos, incluyendo README, AGENTS, workflow GitHub, scripts, 4 ADR, 12 specs, planes/tareas F00/F01, prompts de Codex y 13 escenarios SEC.
- Se verificó inicialmente correspondencia exacta de 53 blobs Git con el ZIP, antes de introducir ajustes editoriales de conciliación. Todas las modificaciones posteriores están en commits de este PR; no se suprimen entregables originales.
- Conservada documentación posterior del PR #2 para Synology/Ubuntu y backups; documentos incompatibles del PR #2 archivados en `docs/history/pr2`.
- Fuente constitucional única: `docs/01-constitution.md` P01–P14. Fuente roadmap única: `docs/10-roadmap.md` F00–F11. `CONSTITUTION.md` y `docs/roadmap.md` son índices, no segundas autoridades.
- ADR 0001–0004 del paquete recuperados; entorno Synology como ADR 0005.

## Revisión temática (archivos del paquete)

| Grupo | Archivos / contenido verificado | Resultado |
|---|---|---|
| Producto | `README.md`, `docs/00-vision.md` | Alcance, MVP, límites, modelo personal/empresarial |
| Gobierno | `docs/01-constitution.md`, `docs/10-roadmap.md`, `docs/11-sdd-codex.md`, `docs/14-release-and-governance.md`, `AGENTS.md` | P01–P14, 12 fases, puertas de calidad, no desviación; política `develop` marcada como propuesta |
| Arquitectura | `docs/02-architecture.md`, `docs/03-tenancy-security.md`, `docs/04-data-model.md`, ADR 0001–0004 | BD por tenant, control central, instancias múltiples, secretos, ACL, índices |
| RAG | `docs/05-ingestion.md`, `docs/06-retrieval.md`, `docs/07-api-contracts.md` | Versiones, publicación segura, búsqueda híbrida, citas y contratos API |
| Calidad | `docs/09-nfr-quality.md`, `docs/12-threat-model.md`, `tests/acceptance/tenant-isolation.md` | Métricas, pruebas negativas SEC-01..13, mitigaciones |
| Operación | `docs/08-operations.md`, `docs/13-decisions-risks.md`, `ops/DECISION_STATUS.md`, `ops/BOOTSTRAP.md`, `ops/REFERENCES.md` | Aprovisionamiento, migraciones, backup/restore, propuestas vs acuerdos |
| Fases | `specs/F00-*/` … `specs/F11-*/` y `specs/_template/` | Una spec por fase y criterios AC trazables; planes y tareas para F00/F01 |
| Automatización | `.github/workflows/docs.yml`, `.github/pull_request_template.md`, `.gitignore`, `scripts/`, `ops/CODEX_PROMPTS.md`, `ops/FIRST_CODEX_TASK.md`, `ops/CHANGE_REQUEST_TEMPLATE.md` | Control documental, protocolo Codex y anti-secretos |

## Ajustes de consistencia documentados en este PR

1. Política de `develop` aún no ratificada: se distingue propuesta de flujo actualmente operativo hacia `main`.
2. F00-R02 exige **API placeholder** además de PostgreSQL/pgvector y MinIO: se refleja en plan, tareas y checklist.
3. F01-R07 (migraciones) obtiene AC-F01-07 explícito y tarea de verificación de locks, versionado y errores.
4. Se corrige errata de referencia a `git diff` en docs SDD.
5. Se prepara checklist/evidencia de F00 **sin marcar como completada** ninguna prueba técnica.
6. El validador comprueba 12 fases, P01–P14, autoridad canónica, ADRs sin conflicto y enlaces Markdown; en errores de archivos faltantes falla con diagnóstico en lugar de excepción.

## Comprobaciones ejecutadas

- Integridad ZIP: 53 rutas fuente presentes en la rama; comparación inicial de blobs SHA-1 Git.
- Documento rector consolidado: 29 secciones cotejadas con sus archivos. Separador final editorial en F11, sin diferencia normativa.
- Scripts originales: sintaxis Python y validador SDD probados offline. El validador reforzado se probó con ausencia simulada de constitución y F08; rechaza ambas.
- Markdown: rutas locales verificadas (las copias archivadas se excluyen de enlaces activos).
- GitHub Actions `Validate SDD documents`: verificar conclusión sobre el **último commit** del PR, no asumirla de corridas previas.
- Revisión de contenidos: ninguna clave privada/token real hallada en el paquete; esto no reemplaza secret scanning de producción.

## Pendientes explícitos (no bloquear la realineación documental)

- F00 técnica: `pyproject.toml`, Python tests/lint, Docker Compose con pgvector y MinIO/API placeholder, CI ampliada y ejecución reproducible. **No está implementada.**
- F01: aprovisionamiento `rag_control` y dos bases tenant, credenciales separadas, buckets/policies y pruebas negativas. **No está implementada.**
- Decidir y proteger flujo `main`/`develop`, estrategia de secreto, opciones ADR 0002/0004, política de repo público vs privado y versiones de componentes.
- Backup externo independiente del NAS y ensayos de restauración.
- Criterios de calidad operativa y límites/recursos para un NAS de 2 vCPU y un SSD sin redundancia.

## Dictamen documental

**Apto para revisión y eventual merge** si el CI documental del último commit pasa y la inspección final del PR no detecta conflictos. La aprobación de este documento no acredita F00/F01 técnica ni constituye autorización automática de despliegue o decisión de opciones pendientes.
