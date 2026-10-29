# ADR 0004 — Separación de secretos y almacenamiento de objetos

**Estado:** Propuesto para ratificar en F01.

**Decisión:** Credenciales por tenant en secret manager, catálogo con referencias; bucket privado por tenant para MVP y política de acceso propia. No persistir secretos en `rag_control` o Git.

**Consecuencias:** complejidad de rotación/provisión; necesidad de probar políticas y gestionar cuotas de buckets en proveedores.
