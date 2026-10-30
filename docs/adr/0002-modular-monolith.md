# ADR 0002 — Monolito modular con workers aislables

**Estado:** Aprobado por el responsable el 2026-10-30; registro en https://github.com/dlalvarez/rag-platform/pull/5#issuecomment-6526924875.

**Decisión:** Backend FastAPI modular, procesos de trabajo asíncronos desacoplados y adaptadores de proveedores; API pública versionada. Sin microservicios ni bus distribuido prematuros.

**Consecuencias:** simplifica entrega inicial, pero obliga a mantener límites de módulos e interfaces. Workers pueden operar separados sin cambiar modelo de datos.
