# ADR 0006 — Formalización del flujo main/develop

**Estado:** propuesto para ratificación F00 (2026-10-30). No aplicado automáticamente.
**Referencias:** ADR-0003, [política](../14-release-and-governance.md), [ratificación F00](../../specs/F00-fundacion-repositorio/ratification.md).

## Contexto y decisión propuesta

El kit original prevé main para releases aprobadas, develop para integración estable y feat/Fxx-* para entregas acotadas. PR #3 restauró esa propuesta, pero develop aún no existía al revisar main. Se propone adoptar ese flujo sin cambiar la rama predeterminada main.

Este PR de planificación se dirige a main para resolver el arranque. Después de su aprobación y merge humano, crear develop desde el commit aprobado de main. Las tareas técnicas F00 parten de develop en feat/F00-* y abren PR hacia develop; los hitos aprobados se promueven mediante PR develop → main. Toda fusión requiere decisión humana explícita.

## Alternativa y consecuencias

Continuar solo con main simplificaría la operación, pero no materializaría el flujo original solicitado. Se prefiere develop; añade revisión de integración y promoción, y obliga a mantener CI en ambas ramas. No implica despliegue automático ni cambio de visibilidad.

Protecciones propuestas: PR obligatorio, sin force-push ni borrado, checks vigentes obligatorios y conversaciones resueltas. Deben decidirse revisores y excepciones administrativas antes de ampliar CI. Si solo hay un responsable, no afirmar que existe revisión independiente ni exigir una aprobación propia imposible de satisfacer; registrar la alternativa humana acordada y cualquier excepción.

## Aplicación, riesgos y reversión

No se crean reglas desde este PR. Registrar configuración efectiva, nombres exactos de checks y permisos tras aprobación; evitar exigir checks inexistentes. Mientras no estén aplicadas, la política documental no es enforcement de GitHub.

Sin migración de datos ni cambio de API. Si el flujo no resulta viable, proponer ajuste por ADR/PR con aprobación humana, preservando commits y PRs; no borrar ramas ni reescribir historia automáticamente. No se modifica ADR aprobado ni la constitución.
