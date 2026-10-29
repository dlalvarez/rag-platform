# Instrucciones para Codex y otros agentes

Leer primero `CONSTITUTION.md`, `docs/architecture/overview.md`, ADR aplicables y la especificación de la fase. Si faltan, no inferir una arquitectura nueva ni implementar.

## Flujo SDD
1. Identificar spec, plan, tasks y aceptación en `specs/FXX-*/`.
2. Señalar contradicciones, decisiones abiertas y restricciones antes de editar.
3. Implementar **solo** tareas expresamente aprobadas, en rama aislada y PR.
4. Ejecutar pruebas relevantes y adjuntar evidencias; nunca inventar resultados.
5. Documentar migración, rollback, observabilidad, seguridad y riesgos para cambios operativos.

## Reglas de no desviación
- Una base PostgreSQL y un rol/credenciales independientes por tenant; base central de control separada.
- Soportar tenants distribuidos entre instancias PostgreSQL; no hardcodear conexión única.
- No utilizar tablas tenant compartidas/RLS como sustituto del aislamiento rector.
- No introducir contraseñas, tokens, datos reales, llaves privadas ni archivos `.env` reales.
- No desplegar a `ragdev01` ni publicar puertos sin autorización expresa y spec aprobada.
- No eliminar ni simplificar controles de acceso, backups o pruebas de restauración por conveniencia.
- No modificar directamente `main`, fusionar PR, ni activar auto-merge sin decisión humana.
- No implementar tecnologías pendientes de aprobación como si ya estuvieran elegidas.

## Formato de entrega de cada PR
Objetivo y issue; alcance y fuera de alcance; spec y ADR aplicables; archivos modificados; pruebas realizadas y no realizadas; riesgos y rollback; decisiones pendientes.
