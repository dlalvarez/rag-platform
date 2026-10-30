# 14 — Política de ramas, releases y cambios

- **Política propuesta para ratificación F00 mediante [ADR-0006](adr/0006-branch-policy.md):** `main` para releases aprobadas, `develop` para integración estable, `feat/Fxx-*` para PR de alcance acotado. A fecha de esta realineación solo existe el flujo de PR hacia `main`; no asumir que `develop` ni su protección están configurados. Aprobación formal y ajustes por ADR antes del desarrollo de F00.
- Todo PR exige checklist y evidencia; aprobación humana para merge. Codex no puede promover ambientes por iniciativa propia.
- Versionado semántico de APIs, eventos y migraciones; tags para hitos aprobados.
- Cambio incompatible de datos requiere plan expand/migrate/contract, estrategia backup y recuperación y prueba en dos tenants.
- No se considera "terminado" un módulo con interfaces ficticias, tests omitidos o simulaciones que el usuario no pueda ejecutar en entorno real.
- La propia documentación cambia mediante PR; si afecta decisiones rectoras, se crea ADR con plan de compatibilidad y autorización previa.

## Aplicación propuesta

1. Revisar y aprobar el PR documental F00 hacia main. La autorización de prepararlo no constituye ratificación.
2. Tras merge humano, crear develop desde ese main aprobado. No cambiar la rama predeterminada.
3. Abrir ramas feat/F00-* desde develop; PR de implementación hacia develop. Promover hitos a main mediante PR develop → main con pruebas y decisión humana.
4. Antes de ampliar CI, decidir y registrar protecciones para ambas ramas: PR obligatorio, checks exactos existentes, conversaciones resueltas, sin force-push ni borrado y política de permisos/excepciones.
5. Añadir lint/tests a los checks obligatorios cuando existan y se hayan verificado. No configurar nombres previstos que bloqueen todos los PR.

Debe acordarse quién revisa. Si hay un único responsable, documentar la revisión humana y el mecanismo viable; no presentar una aprobación propia como revisión independiente. Codex no hace merge ni configura bypass por su cuenta.

**Estado observado al 2026-10-30:** main predeterminada, repositorio público, develop ausente en el listado de ramas. Protecciones no verificadas ni modificadas; no afirmar que están activas. Ver [registro de ratificación](../specs/F00-fundacion-repositorio/ratification.md). La visibilidad pública se conserva.
