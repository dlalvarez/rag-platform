# ADR 0002 — Monolito modular con workers aislables

**Estado:** Propuesto para ratificar en F00.

**Decisión:** Backend FastAPI modular, procesos de trabajo asíncronos desacoplados y adaptadores de proveedores; API pública versionada. Sin microservicios ni bus distribuido prematuros.

**Consecuencias:** simplifica entrega inicial, pero obliga a mantener límites de módulos e interfaces. Workers pueden operar separados sin cambiar modelo de datos.
