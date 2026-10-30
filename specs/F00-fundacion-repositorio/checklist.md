# Checklist F00 — fundación técnica del repositorio

**Estado:** pendiente. Este documento se prepara para las futuras pruebas de aceptación; las casillas no indican trabajo realizado.

- [ ] AC-F00-01: clon limpio instala entorno Python y ejecuta pytest/lint offline.
- [ ] AC-F00-02: Compose con versiones fijadas, PostgreSQL/pgvector, MinIO y API placeholder; pruebas de salud y datos sintéticos.
- [ ] AC-F00-03: CI valida docs, estilo, tests y falla si faltan fuentes rectoras.
- [ ] AC-F00-04: AGENTS, constitución P01–P14 y roadmap canónico localizables.
- [ ] No hay llaves, tokens, contraseñas reales ni documentos privados en git.
- [ ] Persistencia bajo ruta configurable de datos SSD; montaje validado, sin llenar el disco raíz.
- [ ] Registros reales de comandos, versiones, pruebas y resultados en `evidence.md`.
- [ ] PR F00 sometido a revisión, sin adelantar F01 y sin merge automático.

## Antes de implementar

- [ ] Decisión humana registrada sobre spec/plan/tareas y ADR-0006 en [ratificación](ratification.md).
- [ ] ADR-0002 revisado y ratificado antes de usarlo como aprobado.
- [ ] Develop creada desde main aprobado; protección/checks/revisión acordados y estado efectivo registrado.
- [ ] Versiones exactas compatibles seleccionadas y justificadas en T001/T002.
- [ ] Matriz F00-R01..05 → AC → P1..P6 → T001..T006 → V01..V05 mantenida; IDs previstos sustituidos o vinculados a tests reales al implementarlos.

## Al cerrar F00 técnica

- [ ] V01..V05 ejecutadas; fallos controlados y sus códigos de salida registrados.
- [ ] Integración Compose ejecutada aparte; no se confunde suite offline verde con AC-F00-02 aprobado.
- [ ] Clon limpio, commit y comandos exactos documentados; logs saneados.
- [ ] No hay F01, tenants, endpoints de negocio ni migraciones prematuras.
- [ ] Pruebas tenant/ACL no aplicables a F00 justificadas; permanecen pendientes para sus fases.
- [ ] Revisión y decisión humana de merge registradas; postmerge en develop verificado.
