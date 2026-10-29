# 14 — Política de ramas, releases y cambios

- `main`: releases aprobadas; `develop`: integración estable; `feat/Fxx-*`: PR de alcance acotado. Políticas modificables por ADR antes de F00.
- Todo PR exige checklist y evidencia; aprobación humana para merge. Codex no puede promover ambientes por iniciativa propia.
- Versionado semántico de APIs, eventos y migraciones; tags para hitos aprobados.
- Cambio incompatible de datos requiere plan expand/migrate/contract, estrategia backup y recuperación y prueba en dos tenants.
- No se considera "terminado" un módulo con interfaces ficticias, tests omitidos o simulaciones que el usuario no pueda ejecutar en entorno real.
- La propia documentación cambia mediante PR; si afecta decisiones rectoras, se crea ADR con plan de compatibilidad y autorización previa.
