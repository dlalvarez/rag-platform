# Checklist F01 — aceptación pendiente

**Estado:** preparación documental; sin pruebas técnicas F01 ejecutadas.

## Antes de implementar

- [x] Dependencia F00 aprobada y cerrada; PR #6 integrado y postmerge comprobado.
- [ ] Spec/plan/tasks F01 y ADR-0004 ratificados por Diego.
- [ ] Custodia externa de unseal/password de operador acordada antes de inicialización.
- [ ] Perfil F01 separado, límites, TLS, bootstrap SQL y políticas de acceso revisados.
- [ ] Versiones exactas nuevas fijadas y verificadas; no upgrades fuera de alcance.

## Pruebas obligatorias de F01

- [ ] AC-F01-01: rag_control y dos BD tenant distintas, catálogo/migraciones coherentes.
- [ ] AC-F01-02: SQL A↔B denegado con credenciales reales; sin superuser/roles cruzados.
- [ ] AC-F01-03: objetos get/put/list A↔B y anónimo denegados; acceso propio permitido.
- [ ] AC-F01-04: identidad/BD/bucket únicos tras reintentos y concurrencia.
- [ ] AC-F01-05: fallo de bucket no publica READY, recuperación y recursos ajenos intactos.
- [ ] AC-F01-06: dos endpoints PostgreSQL reales; pools/credenciales sin mezcla y con límites.
- [ ] AC-F01-07: locks, versión real, migración repetida/fallida/reversible sin alterar otro tenant.
- [ ] OpenBao conserva secretos tras restart y unseal; token inválido/caducado/denegado falla cerrado.
- [ ] Ningún secreto o contenido privado en Git, catálogo, argumentos, logs ni evidence.
- [ ] TLS verificado, montaje real ext4, permisos y persistencia probados.
- [ ] Pruebas offline/CI y regresión F00 exitosas; comandos, versiones y logs reales.
- [ ] Limitaciones de MinIO, backup externo/restore, HA/PITR declaradas.
- [ ] Revisión humana del PR técnico, decisión de merge y comprobación postmerge.

No marcar funcionalidades F02+ como probadas. Ver [matriz](plan.md) y [evidence](evidence.md).
