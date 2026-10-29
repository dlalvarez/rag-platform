# Bootstrap operativo del repositorio (sin ejecutar automáticamente)

## Preparación

1. **Ya realizado:** repositorio `dlalvarez/rag-platform` inicializado en GitHub. Actualmente público, aunque el kit original sugería privado: revisar política de visibilidad. Esta realineación se propone mediante rama/PR; no copiar encima de `main`.
2. Revisar/ratificar constitución y ADRs propuestos. La adopción de rama `develop`, protecciones GitHub y CI sigue pendiente de decisión formal F00; no asumir que ya está configurada.
3. **Infraestructura dev actual:** Ubuntu 24.04.5 y Docker/Compose operativos en `ragdev01`; Python/uv, PostgreSQL cliente y Codex según modalidad se validarán para F00, sin presuponer instalados.
4. F00 define versiones exactas y archivos de dependencias; evitar imágenes `latest` y secretos en `.env` versionados.
5. Configurar GitHub Actions con jobs de documentación y más tarde tests/seguridad; secretos solo en GitHub Secrets o store autorizado.
6. Iniciar F00 con `ops/CODEX_PROMPTS.md` A y posteriormente B.

## Spec Kit + Codex CLI (opcional)

Referencias oficiales al final de `docs/11-sdd-codex.md`. Para repos ya existentes, seguir proceso de adopción de Spec Kit antes de `specify init` y revisar diff: el scaffolding puede generar archivos que deben reconciliarse con la constitución canónica. Ejemplo a confirmar con la versión instalada: `specify init --here --force --non-interactive --integration codex` (solo tras commit/backup). Después ejecutar `python scripts/sync_speckit_constitution.py` y revisar el diff. Los skills de Codex tienen la forma `$speckit-specify` y se invocan **dentro de la conversación con Codex**, no en bash.

## Prueba local después de F01 (objetivo, no disponible aún)

- Levantar stack dev local con Docker Compose.
- Provisionar `rag_control` y tenants A y B mediante CLI admin.
- Ejecutar migraciones de control + tenant.
- Probar roles A/B, buckets A/B, aislamiento y rollback/compensación de provisión.

**No presentar estos pasos como ejecutables antes de que F00/F01 hayan creado su código.**
