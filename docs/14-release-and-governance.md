# 14 — Política de ramas, releases y cambios

- **Política propuesta, pendiente de ratificación en F00:** `main` para releases aprobadas, `develop` para integración estable, `feat/Fxx-*` para PR de alcance acotado. A fecha de esta realineación solo existe el flujo de PR hacia `main`; no asumir que `develop` ni su protección están configurados. Aprobación formal y ajustes por ADR antes del desarrollo de F00.
- Todo PR exige checklist y evidencia; aprobación humana para merge. Codex no puede promover ambientes por iniciativa propia.
- Versionado semántico de APIs, eventos y migraciones; tags para hitos aprobados.
- Cambio incompatible de datos requiere plan expand/migrate/contract, estrategia backup y recuperación y prueba en dos tenants.
- No se considera "terminado" un módulo con interfaces ficticias, tests omitidos o simulaciones que el usuario no pueda ejecutar en entorno real.
- La propia documentación cambia mediante PR; si afecta decisiones rectoras, se crea ADR con plan de compatibilidad y autorización previa.
