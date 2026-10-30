# Checklist F00 — implementación en revisión

- [x] Planificación, ADR-0002/0006 y ejecución en ragdev01 autorizados; ver ratification.
- [x] Develop creada y protecciones aplicadas; Diego es único responsable de revisión/merge.
- [x] Paquete/configuración tipada/API placeholder, lockfile y pins preparados.
- [x] Tests unitarios offline, lint/formato y fallos controlados ejecutados en ragdev01.
- [x] Constitución, roadmap, AGENTS y ADRs canónicos localizables; validador pasa.
- [x] Secretos efímeros fuera de Git; revisión de archivos candidatos sin coincidencias.
- [ ] AC-F00-01: clon limpio instala entorno y ejecuta pytest/lint offline.
- [ ] AC-F00-02: build, salud y datos sintéticos PostgreSQL/pgvector, MinIO y API.
- [ ] Persistencia SQL/S3 comprobada tras recreación de contenedores.
- [ ] Fallo de dependencia y recuperación comprobados.
- [ ] AC-F00-03: CI del PR docs/lint/tests verde; checks obligatorios actualizados.
- [x] AC-F00-04: referencias canónicas y AGENTS comprobados por validador.
- [ ] Evidencia final con commit, entorno, comandos y resultados reales.
- [ ] PR revisado y aprobación humana para merge; postmerge en develop pendiente.
- [x] Sin F01, tenants, endpoints de negocio ni migraciones prematuras.
- [x] Pruebas tenant/ACL no aplicables a F00 justificadas, pendientes para sus fases.

Los artefactos existentes no sustituyen las casillas de aceptación pendientes.
Ver [evidence](evidence.md) y [runbook](../../ops/F00_RUNBOOK.md).
