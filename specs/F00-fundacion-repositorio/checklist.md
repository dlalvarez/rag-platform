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
