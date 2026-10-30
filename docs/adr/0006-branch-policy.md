# ADR 0006 — Formalización del flujo main/develop

**Estado:** Aprobado por el responsable el 2026-10-30; registro en https://github.com/dlalvarez/rag-platform/pull/5#issuecomment-6526924875.
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

## Aplicación verificada (2026-10-30)

Develop creada desde 53004ec218074b0fbf36359e437f22bee3f3924a. Ruleset activo 26218280, targets main/develop, PR obligatorio, conversaciones resueltas, docs (GitHub Actions), bloqueo de borrado y force-push. Sin bypass; 0 aprobaciones externas requeridas al existir un único responsable. Diego revisa y autoriza cada merge. Registro: https://github.com/dlalvarez/rag-platform/issues/4#issuecomment-6527049209. Los párrafos anteriores describen la propuesta histórica; la política efectiva es este registro y docs/14-release-and-governance.md.
