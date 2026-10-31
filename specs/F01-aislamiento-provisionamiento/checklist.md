# Checklist F01 — aceptación pendiente

**Estado:** T001 aceptada mediante PR #9; T002 aceptada mediante PR #10; T003 aceptada mediante PR #11; T004 aceptada mediante PR #12; T005 aceptada mediante PR #13; T006 en validación. Ningún AC F01 completo.

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


## Evidencia técnica T004, aceptada

- [x] Journal, idempotencia, estado de compensación y pendientes con códigos cerrados.
- [x] Control 0004 aplicado y repetido; lock de sesión exclusivo sin transacción abierta.
- [x] Pruebas offline de fallos, reintento, propiedad y no READY parcial.
- [x] Batería real con OpenBao: bucket, caída entre efecto/journal, concurrencia y conflicto.
- [x] Evidencia vinculada a las fuentes exactas ejecutadas.
- [x] CI del HEAD, revisión/aceptación humana y postmerge del PR T004.

F01 sigue abierta. No anticipar resolver/pools T005 ni pruebas ampliadas T006.


## Evidencia técnica T005, aceptada

- [x] Resolver administrativo: READY/esquema compatible, destinos y refs sin password.
- [x] QueuePool 2/0, hasta 4 engines, drenado y cota por proceso implementados.
- [x] Pruebas offline de gates, saturación, ocho préstamos concurrentes, LRU y drenado.
- [x] Batería real: A→B→A, ocho conexiones, timeout/evicción, cambio de ref y token revocado.
- [x] Evidencia de fuentes ejecutadas y CI del HEAD T005.
- [x] Revisión/aceptación humana y postmerge T005.

Dos endpoints reales y batería ampliada de fase permanecen en T006.


## Evidencia técnica T006, pendiente de aceptación

- [x] Migración bajo lock en la misma conexión Alembic; versión/identidad comprobadas.
- [x] Control refleja MIGRATING/FAILED/READY según resultado, sin head falso.
- [x] Segunda instancia privada, mismo digest, datos/TLS separados y límites dentro de 5 GiB.
- [x] Calibración PostgreSQL real: reversibilidad, rollback DDL y lock/timeout entre procesos.
- [x] Dos baterías integrales con credenciales OpenBao y SQL/S3 en ambos sentidos.
- [x] Pools A2→B2→A2, destino erróneo sin fallback y canary del otro tenant intacto.
- [ ] Evidencia de fuentes y CI del HEAD T006.
- [ ] Revisión/aceptación humana y postmerge T006.

No se cierra F01; T007 y aceptación global permanecen pendientes.
