# F01 — Base de datos y aislamiento por tenant (BORRADOR)

**Estado:** no aprobado. **No autoriza código ni despliegue.**

## Objetivo
Desplegar infraestructura PostgreSQL con extensión pgvector y resolver bases independientes por tenant, sin introducir atajos de tablas compartidas.

## Contratos mínimos
- Control plane `rag_control` separado de datos documentales de tenants.
- Base, usuario/rol y credenciales por tenant. Bases inicialmente pueden compartir instancia física, pero debe estar soportado enrutar un tenant hacia otra instancia.
- Registro consistente de ubicación/estado; alta, baja controlada, migraciones y restauración individual.
- No acceder a corpus de un tenant desde las credenciales de otro; pruebas de privilegios negativas.
- Índices vectoriales por base tenant; almacenamiento documental y permisos segregados.
- Datos y runtime persistentes en `/srv/rag-data` en desarrollo; Compose reproducible.
- PostgreSQL no expuesto públicamente; healthchecks, versiones fijadas, secretos externos.
- Backups consistentes y al menos una restauración de prueba antes de usar datos importantes.

## Requisitos de calidad y validación
Probar provisión de dos tenants, acceso autorizado, acceso cruzado denegado, almacenamiento independiente, reinicio con datos persistentes, indisponibilidad del disco y restauración de tenant. Medir CPU/RAM y fijar concurrencia adecuada.

## Decisiones abiertas que exigen ADR antes de implementar
Versión PostgreSQL/pgvector e imagen, diseño de control plane, pooling, gestión de secretos, formato de migrations, backup (RPO/RTO), objeto storage y eventual cola/Redis. Registrar criterios y alternativas.
