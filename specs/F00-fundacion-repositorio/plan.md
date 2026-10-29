# Plan F00 — propuesta para revisión

1. Definir Python 3.12 (o compatible fijada), uv y estructura inicial mínima con `pyproject.toml`, paquete `src/`, tests y configuración tipada.
2. Definir `.env.example`, `.gitignore`, herramientas de estilo y seguridad; ninguna llave real.
3. Docker Compose de desarrollo con Postgres+pgvector, MinIO, **servicio API placeholder verificable (sin lógica de negocio)** y health checks. Evitar `latest` sin pin. En F00 no almacenar documentos ni credenciales reales.
4. GitHub Actions para docs check, lint y tests offline; scripts consistentes en Linux.
5. Documentar arranque, diagnóstico y troubleshooting; no implementar DB tenancy funcional antes F01.

**Aceptación:** AC-F00-01 a 04. **Riesgos:** versiones/arquitectura host, CI y extensiones. **Rollback:** revert de scaffold sin datos persistentes reales.
