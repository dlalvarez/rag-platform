# Plan técnico de Fxx — completar antes de implementar

**Estado:** DRAFT / APPROVED. **Spec:** `specs/Fxx-*/spec.md`.

## Decisiones técnicas de la fase

- Alternativas revisadas y motivo, sin contradecir constitución/ADRs.
- Módulos y archivos a crear/modificar; diagrama de interacciones si es necesario.
- Contratos de API, BD, eventos y migraciones (up/down/compatibilidad).
- Autorización tenant/repositorio y aislamiento SQL/S3.
- Configuración, secretos y observabilidad requeridos.

## Pruebas

Requisito -> AC -> test (unit, integración, seguridad, E2E). Fixtures sintéticos; comandos reproducibles; cobertura de fallos.

## Operación y rollback

Implementación, despliegue gradual, backups, rollback de código/datos y migraciones. Riesgos y mitigaciones.

## Revisión

Aprobación explícita humana antes de `tasks` y código.
