# Backup y recuperación — Diseño pendiente de aprobación

**Estado actual:** snapshot de VM VMM creado; sin evidencia de copia externa independiente ni prueba de restauración.

## Activos a proteger
1. Base de control `rag_control`.
2. Cada base tenant y sus roles/credenciales; registrar instancia y parámetros necesarios.
3. Documentos/objetos originales y metadatos para reconciliar chunks/embeddings.
4. Configuración versionada de despliegue y secretos en mecanismo protegido separado.
5. Inventario de tenants, permisos y trazabilidad de migraciones.

## Estrategia que debe concretar una spec
- Backups consistentes PostgreSQL por base y globales de roles; elegir dump lógico y/o PITR según RPO/RTO aprobados.
- Copias de objetos/documentos coordinadas con el punto consistente de metadatos; verificar checksum y restauración coherente.
- Copia local en HDD puede acelerar recuperación; **una copia adicional fuera del NAS** es obligatoria frente a pérdida del equipo.
- Cifrado en reposo y tránsito; retención, rotación, borrado seguro y monitoreo de fallos.
- Restauración granular de tenant, de base de control, de documentos y de infraestructura completa.
- Ensayos de pérdida del único SSD, credenciales invalidas, inconsistencia de objetos y aislamiento entre tenants restaurados.

## Criterios pendientes
Documentar y aprobar RPO, RTO, periodicidad, retención, destino externo, responsable y frecuencia de pruebas. No considerar la protección completada hasta restaurar desde un backup real en entorno aislado.
