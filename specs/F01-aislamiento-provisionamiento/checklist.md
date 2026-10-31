# Checklist F01 — aceptación pendiente

**Estado:** T001 aceptada mediante PR #9; T002 aceptada mediante PR #10; T003 aceptada mediante PR #11; T004 en validación. Ningún AC F01 completo.

## Antes de implementar

- [x] Dependencia F00 aprobada y cerrada; PR #6 integrado y postmerge comprobado.
- [x] Spec/plan/tasks F01 y ADR-0004 ratificados por Diego en PR #8.
- [x] Esquema de custodia de unseal aprobado por Diego el 2026-10-30: gestor de contraseñas y copia fuera de línea, fuera de ragdev01, Shamir 1/1.
- [x] Diego confirmó preparados los destinos de custodia el 2026-10-30; bootstrap y custodia confirmados posteriormente por Diego.
- [x] Diego confirmó credenciales custodiadas y bootstrap con operador limitado y root inicial revocado; no se solicitaron ni leyeron valores.
- [ ] Perfil F01 separado, límites, TLS, bootstrap SQL y políticas de acceso revisados.
- [x] T001: SQLAlchemy 2.1.6/Alembic 1.20.1 fijados con hashes; psycopg/httpx conservados, sin upgrades ajenos. Las dependencias futuras se revisan en sus tareas.

## Pruebas obligatorias de F01

- [ ] AC-F01-01: rag_control y dos BD tenant distintas, catálogo/migraciones coherentes.
- [ ] AC-F01-02: SQL A↔B denegado con credenciales reales; sin superuser/roles cruzados.
- [ ] AC-F01-03: objetos get/put/list A↔B y anónimo denegados; acceso propio permitido.
- [ ] AC-F01-04: identidad/BD/bucket únicos tras reintentos y concurrencia.
- [ ] AC-F01-05: fallo de bucket no publica READY, recuperación y recursos ajenos intactos.
- [ ] AC-F01-06: dos endpoints PostgreSQL reales; pools/credenciales sin mezcla y con límites.
- [ ] AC-F01-07: locks, versión real, migración repetida/fallida/reversible sin alterar otro tenant.
- [x] T001: OpenBao conserva canary tras restart/unseal; token inválido y caducado rechazados HTTP 403; sellado rechaza HTTP 503. Ejecución sensible por Diego.
- [ ] Ningún secreto o contenido privado en Git, catálogo, argumentos, logs ni evidence.
- [ ] TLS verificado, montaje real ext4, permisos y persistencia probados.
- [ ] Pruebas offline/CI y regresión F00 exitosas; comandos, versiones y logs reales.
- [ ] Limitaciones de MinIO, backup externo/restore, HA/PITR declaradas.
- [ ] Revisión humana del PR técnico, decisión de merge y comprobación postmerge.

No marcar funcionalidades F02+ como probadas. Ver [matriz](plan.md) y [evidence](evidence.md).


## Evidencia técnica T003, aceptada

- [x] MinioAdmin 7.2.20 compatible con la receta fijada; calibración real.
- [x] Credenciales tenant versionadas en OpenBao y referencias en control.
- [x] Acceso propio y rechazos cruzados/anónimos reales A/B; sin administración IAM.
- [x] Repetición sin rotación y fixture ajena conservada; no READY.
- [x] CI del HEAD, revisión/aceptación humana y postmerge del PR T003.

Esto no cierra AC de fase ni acredita saga, pools, dos instancias o migraciones T006.


## Evidencia técnica T004, pendiente de aceptación

- [x] Journal, idempotencia, estado de compensación y pendientes con códigos cerrados.
- [x] Control 0004 aplicado y repetido; lock de sesión exclusivo sin transacción abierta.
- [x] Pruebas offline de fallos, reintento, propiedad y no READY parcial.
- [ ] Batería real con OpenBao: bucket, caída entre efecto/journal, concurrencia y conflicto.
- [ ] Evidencia vinculada a las fuentes exactas ejecutadas.
- [ ] CI del HEAD y revisión/aceptación humana del PR T004.

F01 sigue abierta. No anticipar resolver/pools T005 ni pruebas ampliadas T006.
