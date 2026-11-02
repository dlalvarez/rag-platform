# Evidencia F04

## Inicio 2026-11-01 — T001

Dependencia F03 aceptada en develop@4c5b8d3189b71dad6fbe6f2921cbd06b33754871:
[PR #34/postmerge](https://github.com/dlalvarez/rag-platform/pull/34#issuecomment-6565126139).
CI de head (cuatro checks) y merge (tres) correcto; 562 tests offline, regresiones
reales F00/F01/F02 y smoke F03 después del merge. Recursos conservados.
Los resultados de F03 no son pruebas de F04.

Plan/tareas/checklist preparados; D-05 resuelta como selección de adaptadores dentro
del alcance original, sin nueva aprobación atribuida a Diego. Fuentes y limitaciones
en parsers.md. Ningún parser instalado ni worker/esquema F04 activado en esta entrega.
Presupuestos propuestos aún no medidos. No hay AC-F04 acreditado todavía.
CI/revisión/postmerge de T001 pendientes al redactar; resultados se añadirán con
referencia exacta. No se han reiniciado servicios ni modificado datos o credenciales.

## T001 integrada

PR #35 head 49204356fc2eb2c4e9cba9e173d795cc3011fd91, merge
1a63634f54df2c7d7c8459a1427c1dcfa7616de7: cuatro checks del head y tres del merge
correctos, revisión delegada del mismo agente, ambos checkouts limpios/fast-forward y
check_docs correcto. Solo documentación.
[Postmerge](https://github.com/dlalvarez/rag-platform/pull/35#issuecomment-6565225898).

## T002 — núcleo durable, sin activación de ingesta

22 tests nuevos de invariantes; suite completa 584 correctos (advertencia previa
Starlette/httpx conocida). UUID estrictos, scope de consumidor, replay/conflicto,
lease, fencing por todos los identificadores, backoff, error cerrado y constraints.
SQLite acredita invariantes offline, no reemplaza la concurrencia PostgreSQL.

Batería real en ragdev01 con imagen propia rag-f04-tools:t002 y comparación SHA-256
de script/cola/esquema contra fuente actual. Migración f04_control_0006 aditiva:
repetir upgrade y llamar targets F01/F02 no degrada; DDL/revisión se revierten al
salir de la transacción de prueba. Huellas de todas las tablas públicas F01/F02
sin cambios, revisión física original restaurada, sin tabla pública nueva.

Esquema f04_queue_probe_0001 retenido, propiedad explícita del migrator y marker
verificado; contiene solo IDs sintéticos y envelopes de QA, nunca conocimiento tenant.
El bootstrap SQL existente prepara exclusivamente ese esquema y GRANT USAGE para
probar denegación del app; el migrator ejecuta las pruebas. No se instala un rol
nuevo ni se cambian contraseñas. Contenedor efímero: cuatro bind RO (tres credenciales
SQL de QA y CA), red control, sin día, Bao bearer, S3, IdP o autoridad API.
Esto no es el perfil del worker ni amplía permisos del runtime existente.

Resultados PostgreSQL reales:
- Dos procesos compiten por un job: un único claim; otro job progresa con SKIP LOCKED
  aunque se mantenga bloqueado el primero.
- Proceso sale sin ack: al caducar realmente el lease, otro intento recupera el
  mismo job; token/contador anterior no puede confirmar, renovar ni fallar el nuevo.
- Reintento usa backoff real; agotar intentos o leases termina FAILED sin bucle infinito.
- Ack y heartbeat esperan un lock mantenido hasta caducidad: ambos rechazados después
  de obtenerlo. El reloj de PostgreSQL se comprueba de nuevo tras el lock.
- App SQL no puede leer el esquema QA (42501); no se encoló ningún original F03.

Correcciones durante el ensayo: faltaba el montaje bootstrap para preparar el esquema
(el migrator carece de CREATE en la base); se aisló en un servicio QA con cuatro RO.
Una reconstrucción apuntaba al servicio anterior: objetivo corregido y hashes de
imagen/fuente añadidos. El ensayo de lock emitía lease antes de iniciar el proceso;
se corrigió con handshake READY previo y entrega del claim por IPC, sin relajar el
fencing. Se conservan también las fixtures de ensayos interrumpidos; no se purgan.

No hay worker activo, grants de cola al runtime, migración pública persistida,
extracción ni AC-F04 E2E completos. Parada segura y autorización de negocio se
comprueban con el worker T005, no se atribuyen a esta batería de cola.
CI/revisión/merge/postmerge del PR de este núcleo pendientes al redactar.
