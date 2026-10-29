# Constitución de RAG Platform

**Estado:** propuesta para aprobación en PR F00. **Autoridad:** los ADR y specs aprobados rigen la implementación.

## Propósito
Desarrollar una plataforma SaaS comercializable de recuperación documental (RAG) con múltiples tenants, usuarios, repositorios y asistentes, mediante entregas incrementales orientadas a evidencia.

## Principios obligatorios
1. **Aislamiento fuerte por tenant:** cada tenant posee una base PostgreSQL independiente y credenciales propias; existe una base central de control. No sustituir esta decisión con tablas compartidas o RLS como aislamiento primario.
2. **Distribución multi-instancia desde el diseño:** la resolución de conexión y el provisionamiento no presumen que todas las bases estén en un único host PostgreSQL.
3. **Separación documental y vectorial:** documentos, índices, credenciales y permisos por tenant; ninguna consulta debe cruzar límites de autorización.
4. **SDD estricto:** constitution → spec → plan → tasks → implementación → pruebas → revisión. Una spec aprobada precede al código.
5. **GitHub como fuente de verdad:** cambios en ramas y PRs, no commits directos a main después de la inicialización fundacional.
6. **Codex como implementador:** no inventa decisiones arquitectónicas; devuelve propuestas de cambio para aprobación.
7. **Seguridad y privacidad:** secretos fuera del repositorio, permisos mínimos, auditoría; datos reales de clientes no deben entrar al sandbox de desarrollo.
8. **Portabilidad:** las dependencias de Synology, Ubuntu y Docker son de despliegue, no del core funcional.
9. **Incrementalidad:** construir MVP con el mínimo de complejidad, sin comprometer aislamiento ni recuperabilidad.
10. **No desviaciones silenciosas:** toda alternativa que contradiga un principio debe documentarse como propuesta y requerir aprobación expresa previa.

## Jerarquía y cambios
Constitución aprobada → ADR aprobados → especificaciones por fase → planes y tareas → código y configuración. Las propuestas sin aprobar no habilitan despliegues. Registrar desviaciones y riesgos en PR; no borrar decisiones sin trazabilidad.

## Definición de terminado
Una fase necesita criterios de aceptación medibles, evidencias de pruebas (incluido aislamiento negativo cuando aplique), documentación operacional, validación de seguridad y PR revisado antes del merge.

## Límites iniciales
La VM Synology es solo desarrollo/integración. No ofrecer garantías comerciales de disponibilidad, recuperación o seguridad de producción antes de pruebas y arquitectura operativa aprobadas.
