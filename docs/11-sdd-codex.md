# 11 — Metodología SDD aplicada a Codex + GitHub

**SDD = Spec-Driven Development**, desarrollo guiado por especificaciones. **GitHub** almacena constitución, specs, decisiones, código y PRs. **Codex** implementa bajo restricciones, no redefine el producto.

## Variante principal: Codex Cloud + PR

1. Aprobar `docs/01-constitution.md` y la spec de fase; conservar ambas en repositorio.
2. Preparar `specs/Fxx/plan.md`: decisiones técnicas restringidas a la fase, modelo de cambios y plan de tests/rollback.
3. Preparar `tasks.md`: tareas ordenadas, con IDs, artefactos y `AC-xx` asociados. Revisar consistencia.
4. Abrir tarea para Codex Cloud apuntando explícitamente a `AGENTS.md`, spec, plan y tasks; pedir rama/PR, cambios mínimos y **no merge**.
5. Ejecutar tests en sandbox; Codex reporta resultados y vacíos; no usar archivos secretos ni credenciales reales.
6. Revisar PR, seguridad, migraciones y cambios colaterales. Corregir vía iteraciones pequeñas; la aprobación humana precede al merge.
7. Registrar evidencia en `evidence.md` y checklist; merge a `develop` solamente cuando puertas y tests pasen; promover a `main` bajo política de release.

## Variante opcional: Spec Kit + Codex CLI

Según documentación oficial vigente, integración `codex` de Spec Kit crea skills bajo `.agents/skills/` y se invocan como `$speckit-<command>` dentro de Codex. **No ejecutar `$speckit-*` como comando de shell.**

Ejemplo de bootstrap en repositorio **ya existente** (revisar `specify --help` ygit diff, evitar sobreescribir documentos):

```bash
uv tool install specify-cli
specify version
# Solo tras hacer commit/backup de este repositorio existente:
specify init --here --force --non-interactive --integration codex
# Revisar los cambios antes de confirmar a Git
git diff
```

Flujo de skills, aplicado a una sola fase:

```text
$speckit-constitution     # una sola vez, sincronizar con la constitución aprobada
$speckit-specify          # una fase/feature; no generar otro roadmap paralelo
$speckit-clarify
$speckit-plan
$speckit-checklist
$speckit-tasks
$speckit-analyze
$speckit-implement
$speckit-converge
```

Después de inicializar, sincronizar la copia derivada de la constitución con `python scripts/sync_speckit_constitution.py`, revisar el diff y conservar `docs/01-constitution.md` como fuente canónica. Si el scaffolding de Spec Kit genera archivos bajo `specs/` o `.specify/`, consolidar de forma explícita con nuestros contratos **sin crear dos constituciones contradictorias**. La constitución rectora y aprobada es `docs/01-constitution.md`. Las specs por fase de este paquete son insumo y límite, y no deben ser reescritas por la herramienta para justificar implementaciones diferentes.

## Puertas de aprobación (Gates)

- G0 alcance: objetivos, no-objetivos y dependencias de fase revisados.
- G1 spec: requisitos no ambiguos con criterios de aceptación observables.
- G2 plan: arquitectura concordante con P01–P14, ADRs y contrato API/DB.
- G3 tareas: trazabilidad AC -> implementación/test, riesgos y rollback.
- G4 PR: pruebas, integraciones y seguridad verificadas.
- G5 postmerge: ejecución sobre `develop`, evidencia y actualización de roadmap.

## Roles

**Usuario/arquitecto:** decide producto, constitución, ADRs y aceptación. **Codex:** propone detalles y desarrolla dentro de los límites. **CI:** verifica controles automatizables. **Revisor humano:** valida diseño, aislamiento, reportes, migraciones y merge.

## Reglas de PR

- Rama `feat/Fxx-descripcion`; PR pequeño, focalizado, vinculando requisitos.
- No mezclar refactors extensos, cambios de proveedor o decisiones fundamentales con desarrollo de una fase.
- CI requiere linters, tests, migraciones reproducibles y aislamiento cuando aplique.
- No borrar capacidades existentes ni reestructurar modelos sin decisión aprobada.

## Prompts reutilizables

Ver `ops/CODEX_PROMPTS.md`: prompt de preparación de fase, implementación, revisión de PR y corrección de defectos.
