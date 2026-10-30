# Tareas F00 — propuestas para ratificación

**Estado:** ninguna tarea técnica ejecutada. Ver [plan y matriz V01–V05](plan.md) y [ratificación](ratification.md).
Se conservan los IDs T001–T006 originales; orden de ejecución: T001 → T003 → T002 → T004 → T005 → T006.

- [ ] T001 [F00-R01/R03; AC-F00-01; P1; V01/V03] Crear `pyproject.toml`, lock, paquete mínimo en `src/rag_platform/`, configuración tipada y tests unitarios/smoke. Fijar Python/uv/dependencias compatibles. Verificar instalación congelada, import y configuración inválida sin secretos.
- [ ] T002 [F00-R02/R03; AC-F00-02; P3; V02/V03] Crear Compose/Dockerfile y smoke PostgreSQL/pgvector, MinIO y API placeholder; imágenes fijadas y health checks. Probar SQL/vector, objeto sintético, salud API, dependencia caída y montaje faltante. Documentar comandos y limpieza aislada; sin lógica de negocio ni ejecución en ragdev01.
- [ ] T003 [F00-R03/R04; AC-F00-01/02/03; P2; V01/V03] Preparar `.env.example`, exclusiones Git, pytest y Ruff; sin secretos ni `latest`. Probar configuración faltante y revisar archivos rastreados/logs. Credenciales efímeras fuera de Git.
- [ ] T004 [F00-R04; AC-F00-03; P4; V04] Conservar CI documental y añadir lint/formato/tests offline. Probar fallos de docs/lint/test en copias temporales. CI de PR para main/develop sin secretos, servicios pagados ni deploy; nombres exactos de checks se registran para protección.
- [ ] T005 [F00-R05; AC-F00-04; P5; V05] Actualizar README/ops con bootstrap, diagnóstico, configuración, persistencia y rollback; conservar constitución/roadmap canónicos y AGENTS descubribles. Ejecutar validador documental y comprobar enlaces.
- [ ] T006 [F00-R01..05; AC-F00-01..04; P6; V01..V05] Ejecutar desde clon limpio las pruebas offline y la integración Compose aparte en entorno autorizado. Registrar commit/entorno/versiones/comandos/resultados/logs saneados por AC en evidence, actualizar checklist, abrir PR de implementación hacia develop y solicitar revisión. No cerrar Issue #4 ni F00 por un PR documental; no merge ni despliegue automático.

Cada resultado debe enlazar requisito, AC, tarea y test real. Los tests de aislamiento tenant/ACL se mantienen para F01+ y no se simulan como aprobados en F00.
