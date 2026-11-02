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

## T004 — extracción/chunking y aislamiento real (2026-11-01)

Dependencia técnica: núcleo T002 integrado en PR #36, head
7b3e66307e67b61b1300614c79ab68991d6ed69e, merge
590d4fe385ed3efa4c3743a1a129a3e5692b3beb. Cuatro checks de head/tres de merge correctos;
revisión delegada, dos checkouts limpios/check_docs, 22 tests postmerge y hashes de imagen
correctos. [Postmerge #36](https://github.com/dlalvarez/rag-platform/pull/36#issuecomment-6567725630).
T002 sigue abierta para activación/grants/parada con T005.

pypdf 6.21.4, python-docx 1.2.0 y lxml 6.1.3 fijados en uv.lock. Comparación del lock
anterior: todas las versiones existentes conservadas. Metadatos de las distribuciones
verificados: BSD-3-Clause/MIT/BSD-3-Clause respectivamente. Instalación solo en venv
separado /home/diego/proyectos/rag-platform-f04-parser-venv, Python existente; entorno
operativo sin modificar. Sin OCR, modelos ni proveedor externo.

Corpus semántico nuevo y determinista: PDF con dos páginas de texto, DOCX con títulos/
tabla, MD con SQL y TXT Unicode. Generador scripts/f04_corpus.py y manifiesto SHA-256
ops/f04/corpus-manifest.json. Cuatro originales conservados fuera del checkout en
/home/diego/proyectos/rag-platform-f04-corpus, directorio 0700/archivos 0600; si existe
un archivo diferente, se conserva y falla el guard, no se sobrescribe. No son los
PDF/DOCX estructurales de recepción F03, ni se reutilizan sus claves idempotentes.

618 tests offline correctos, incluidos 34 nuevos. Advertencia Starlette/httpx anterior
sin cambios. Lint/formato/docs/diff correctos. Casos nuevos:
- Cuatro formatos, bytes del corpus estables, repetición y chunks iguales.
- Offsets Unicode NFC/LF, páginas PDF reales, títulos/tablas DOCX en orden, MD/código/
  puntuación SQL conservados; hash de cada chunk y cobertura/overlap exactos.
- Escaneado y documento mixto con página de imagen → NEEDS_OCR, sin resultado parcial.
  Página realmente vacía conserva blank_page y número; no se inventan chunks.
- PDF inválido/cifrado/más de 200 páginas; DOCX ZIP expansivo, header no soportado y
  DOCTYPE/entidad externa; UTF-8/controles inválidos, texto vacío y más de 2M caracteres.
- Configuración válida/inválida y fingerprint, límite 10 000 chunks sin tupla parcial,
  hash/tamaño privado de entrada, timeout con cierre y siguiente trabajo correcto.
- Kernel real: open, sockets IPv4/Unix, fork y exec denegados; descriptor original RO
  y legible; asignación sobre límite rechazada, CPU y salida excesivas detenidas.

Los guardas ZIP F03 se extrajeron sin alterar sus reglas a funciones sobre reader
para reutilizarlos dentro del hijo aislado; todos los tests F03 previos siguen correctos.
No se valida un archivo hostil antes del aislamiento para eludir sus límites.
Se corrigió un import de una prueba nueva y su literal de bytes inválidos durante el
ensayo; la suite final completa pasó. No se atribuye ese fallo a las librerías.

Imagen rag-f04-tools:t004 construida en ragdev01, diez hashes de módulos/scripts/
manifiesto comparados con fuente final. Perfil efectivo extraction-check: cero montajes,
secretos, puertos o red; rootfs RO, usuario sin privilegios, cap_drop ALL,
no_new_privs y tmpfs 0700 de 64 MiB. Seccomp adicional en el hijo, Linux x86_64/kernel
6.8 del servidor; no fallback sin política. Solo original RO/stdout privado/stderr
descartado; entorno limpio y sin FD heredados. El padre limita lectura IPC a 16 MiB,
mata y espera al hijo si excede tiempo/salida, y libera su única plaza de extracción.

Batería dentro de ese contenedor: cuatro formatos/repetición/procedencia, NEEDS_OCR/
blank_page, restricciones de kernel, memoria/CPU/salida correctos. Pico RSS observado
por hijo: 83 820 KiB, con este corpus sintético; no es una promesa de capacidad para
PDF complejos. Contenedor 0.5 CPU/768 MiB; hijos con máximo 512 MiB de address space,
30 s CPU/45 s pared, 10 MiB de original, 2M caracteres, 200 páginas. Cero hijos sin
recolectar y cero descriptores temporales propios abiertos al terminar.

Límites: PDF layout/tablas complejos no garantizados; texto dentro de imágenes no se
interpreta, y una capa residual de texto puede requerir revisión del original. La
detección acreditada es de páginas sin texto extraíble, no un detector universal de
escaneos. DOCX no inventa páginas; rasgos conocidos que ocultarían texto se rechazan
con código cerrado. Offsets refieren representación normalizada, no bytes originales
ni posiciones de render. Los LF sintéticos entre bloques no son chunks de contenido.

R02/R03/R06, AC02/05 a nivel del componente. No se ejecutaron SQL/S3/HTTP de negocio
en esta batería porque no activa worker/esquema tenant/API. Integración/reintentos/
tombstone y regresión online completa pendientes de T003/T005/T006/T007. F04 sigue
abierta; READY_FOR_EMBEDDING no es publicación con embeddings. CI/revisión/merge/
postmerge del PR T004 pendientes al redactar.

## Cierre componente T004 postmerge

PR #37 merge f1a7a3ddc077302b4c1bdebaeef3ba60b3489716, cuatro checks de head/tres
del merge correctos; checkouts limpios, check_docs y 34 tests desde develop correctos,
imagen conserva diez hashes. Revisión delegada del mismo agente; F04 sigue abierta.
[Postmerge #37](https://github.com/dlalvarez/rag-platform/pull/37#issuecomment-6568391206).
Continúa T003 según schema.md; no aprobación rutinaria pendiente.

## T003 — núcleo de esquema y publicación, sin activación persistente

Contrato previo en schema.md, R04/R05/R06; AC01/03/04/05 a nivel de datos. Evolución
f03_tenant_0002 → f04_tenant_0003 conserva factoría F03 y valores originales. Amplía
document_versions con ORIGINAL inmutable/PROCESSED enlazado al original, sin copiar
objetos. FK directa chunks→document_versions, FK de bloques/identidad, hash SQL,
offsets NFC y configuración única por documento/original. Intención durable local,
tokens/lease de intento y baja lógica sin purge. READY_FOR_EMBEDDING no PUBLISHED.

Checks y triggers invoker con search_path fijo verifican estado, cobertura/contenido/
hash/orden/páginas/contadores y ACL/documento/repositorio vigentes. Auditoría READY
obligatoria mediante constraint trigger diferible dentro del commit. No añadir bloques/
chunks a un resultado final, cambiar procedencia ni actualizar originales. Roles app
sin DDL/DELETE de contenido ni UPDATE de atributos originales/configuración;
readonly sin escritura ni ops. Helper comprueba identidad/owner, head físico,
funciones, constraints, índices y triggers antes de reflejar éxito.

Perfil ingestion exacto, admisión de origen F03/F04; F01/futuro rechazados antes de
leer secretos o ejecutar runner. Un test detectó que el nuevo perfil heredaba el
dominio HMAC F03: se añadió dominio F04 explícito conservando bytes F02/F03.
Prueba de contexto cruzado correcta. Se corrigió también el máximo usado por el
lector privado de QA (argumento max_size), que rechazó el arranque antes de tocar
tenant; no se cambió ninguna contraseña ni se solicitó al operador.

631 tests offline correctos (13 nuevos de admisión/firma/versionado y no mutación
de DDL histórico); lint/formato/docs/diff correctos, advertencia Starlette/httpx previa.
36 pruebas enfocadas F01/F03/F04 correctas antes de la suite completa.

Batería PostgreSQL real en las cuatro fixtures F03/ambas instancias, con imagen
rag-f04-tools:t003 y diez hashes de fuente comparados. QA dedicado con cuatro RO
(dos bootstrap SQL, control migrator y CA), red control, rootfs RO, sin día/Bao bearer,
S3/IdP o despliegue de API/worker. La sesión administrativa asume roles propios para
probar sus permisos; esto no sustituye pruebas de login del runtime tras activación.

Cada transacción tenant prueba migración/repetición, huellas de todas las columnas
F03 intactas, constraints/FKs/grants y:
- Original no actualizable; procedencia/configuración y actor de intención protegidos.
- Chunk incorrecto por texto/hash/página/sección/repositorio rechazado.
- Resultado parcial o hash/contadores incorrectos no alcanzan READY_FOR_EMBEDDING.
- Resultado completo pasa con su auditoría; falta de auditoría falla al forzar
  constraints diferibles, como ocurriría antes de commit.
- Resultado final inmutable; readonly no escribe ni accede a ops/identidad técnica.
- Tombstone o ACL retirada impiden finalizar; sin afirmar todavía carrera de procesos.

Las fixtures SQL nuevas son temporales y no representan una extracción S3: no se
guardó ningún original ficticio ni versión procesada. Se revierten datos, DDL/head y
defaults de roles en todas las pruebas; fingerprints de tablas F03, catálogo público
y configuraciones de roles iguales antes/después. No se movió el catálogo a F04 ni
se dejó esquema F04 persistido. Las pruebas de catálogo FAILED/recuperación, runtime
real y carreras entre procesos quedan para activación T005/T006/T007.

Privacidad SQL probada sin suprimir errores operativos: defaults por rol evitan
statements, parámetros y detalles con filas privadas; no se altera logging global ni
se elimina la clase ERROR. En ambas instancias se observaron marcador positivo y
errores provocados, con canary de cuerpo ausente; inspección local sin logs brutos
en chat. Defaults solo probados con rollback; instalar/abrir conexiones de runtime
con este perfil antes de persistir chunks en la activación.

T003 sigue abierta hasta migración/operación persistente y gates de integración.
CI/revisión/merge/postmerge del PR de núcleo pendientes al redactar. Continuar T005
tras esa puerta; no esperar aprobación de trámite ni declarar cierre F04.

## T003 núcleo integrado — PR #38

Head 04c7de3afac4c27ad0d3b9cd8893e8ca6e1e6d32, merge
e69a3af31433291e42158854fca8123675368e47. Cuatro checks de head y tres de merge
correctos. Revisión delegada del mismo agente registrada, sin atribuir independencia
o aprobación personal nueva. Ambos checkouts limpios/exactos, docs válidas,
13 tests postmerge y diez hashes de imagen correctos.
[Postmerge](https://github.com/dlalvarez/rag-platform/pull/38#issuecomment-6569343145).
T003 permanece abierta para activación y validaciones del runtime.

## T005 componente de intención y reconciliación

Contrato previo: [worker.md](worker.md), R01/R04/R05/R06; AC01/03/04.
journal.py crea versión PROCESSED e intención con IDs estables por original/config
y auditoría en la transacción tenant del llamador. Repetir identidad conserva el
actor y recupera la misma versión; distinta configuración crea otra sin cambiar
originales. Lock de repositorio/documento serializa con ACL/baja existentes.
El componente exige autorización global verificada del llamador: su chequeo local
de ACL no es una autoridad de usuario ni un endpoint HTTP.

El dispatcher transmite exclusivamente UUIDs a DurableQueue y confirma localmente
después. El UUID de intención es la clave idempotente. Repetir tras perder el ack
recupera el mismo job; cambio de actor/documento/identidad no adopta el envelope.

Pruebas en ragdev01:

- 14 tests nuevos offline: ack perdido, actor/documento/identidad, límites/IDs
  antes de SQL, representación privada y errores cerrados.
- QA PostgreSQL real en cuatro fixtures SAME_A/SAME_B/TWO_A/TWO_B, dos instancias.
  Versión/intención/auditoría atómicas, tres repeticiones sin duplicados, config
  distinta y actor distinto rechazado. Baja impide nueva petición.
- En esquema QA control propio f04_intent_probe_0001, commit real del enqueue y
  reenvío sin registrar su primer ack: un solo job. Despacho local repetido no
  modifica identidad; otro job o versión se rechazan. Job QA termina STOP_REQUESTED.
  Conservadas las tablas/envelopes de QA, solo IDs sintéticos; no trabajos públicos.
- Se repite toda la batería de esquema T003: FK, procedencia, duplicados,
  completitud, auditoría, roles, tombstone/ACL. Cada transacción tenant revertida;
  fingerprint de control/datos originales, head/tablas y defaults de roles intactos.
- Imagen rag-f04-tools:t005-intent con doce hashes exactos; cuatro montajes SQL/TLS
  RO, sin Bao/sesión diaria/S3/IdP/puertos. Logs de ambas instancias: controles
  positivos y errores observados, sin canary de texto. Nunca se copiaron logs brutos.

Estas pruebas ejercen componentes con contexto administrativo QA. No acreditan un
worker de aplicación ni autorización global de runtime, extracción S3 asíncrona,
crash real del worker tras commit, fencing de finalización, parada, migración
persistente o API F04. T002/T003/T005 siguen abiertas hasta completar esas puertas.
No originales/chunks persistidos, rotación, reinicio de infraestructura ni F05.

Regresión completa del componente en ragdev01: 645 tests correctos (631 previos +14),
ruff check/format, check_docs y diff --check correctos. Solo advertencia ya conocida
de Starlette/httpx, sin cambios de dependencias en este componente.

## T005 intención integrada — PR #39

Head 6c41a126f9c0226b601b825959665a9ff22e035e, merge
78c4653c40b2645bbc6b31854394a8e7f7910f92. Cuatro checks del head y tres del merge;
revisión delegada del mismo agente y postmerge correctos. Ambos checkouts limpios,
docs válidas, 14 tests postmerge y doce hashes exactos.
[Postmerge](https://github.com/dlalvarez/rag-platform/pull/39#issuecomment-6569466967).
T005 continúa; esto no acepta el worker completo.

## T005 componente de fencing y resultado transaccional

claims.py toma el lock del envelope y verifica reloj/token/intento/identidad después
de adquirirlo. CommitGuard deja de ser válido al salir del contexto. El llamador
mantiene el fence corto durante el commit tenant; el ack se hace después. No hay
ACID distribuido ni ack anticipado. Timeout SQL/lock de control 15/5 segundos.

processing.py registra intento local y resultado mediante transacción del llamador:
original/config/actor verificados, todos los bloques/chunks con UUID estable,
hash/contadores/READY_FOR_EMBEDDING y auditoría antes de confirmar. Resultado READY
repetido no inserta nada. Error durante completitud revierte todas las inserciones;
no limpiar resultados sospechosos con DELETE. Fallo recuperable pasa a
FAILED_RETRYABLE y otro claim válido puede recuperarlo; terminales permanecen.

worker_policy.py valida contexto firmado vigente y rol de escritura. Toma locks
compartidos de los protocolos existentes global/membresía F02 y saga F01, sin
conceder UPDATE de catálogo. Esto coordina con IdentityAdministration y migraciones
controladas; SQL directo que ignore esos locks no es una interfaz soportada de
revocación concurrente. El repositorio/documento se serializa con el flujo F03 de ACL
y la baja F04. Parada, lease/contexto vencido o tombstone impiden el commit.

Ajuste de reconciliación: el ack local exacto de un enqueue ya confirmado puede
registrarse tras baja/revocación, solo sobre IDs y sin autorizar contenido. Evita una
intención perpetuamente PENDING; el worker sigue obligado a autorizar antes de I/O
y resultado. El contrato worker.md documenta esta frontera antes de su uso runtime.

Pruebas ejecutadas únicamente en ragdev01:

- 656 tests completos (645 anteriores +11 nuevos), lint/formato/docs/diff correctos.
  Tests nuevos de guard válido/forjado/caducado, rollback del ack, parada, frontera
  del contexto y revalidación real de usuario/membresía/referencias/head/reader
  mediante TenantAuthorizer offline. Advertencia Starlette/httpx ya conocida.
- PostgreSQL real, cuatro fixtures en ambas instancias: fallo de hash al finalizar
  después de insertar bloques/chunks -> rollback completo y estado EXTRACTING;
  resultado correcto + repetición -> mismo número de chunks. Reintento de fallo
  de dependencia -> claim nuevo recupera; claim viejo rechazado.
- Dos procesos reales: con fence retenido y lease caducado, un segundo proceso no
  puede tomar el mismo job. Al liberar el lock, el nuevo claim cambia intento/token
  y completa. Guard viejo/caducado no confirma.
- Parada inmediatamente antes del commit revierte todos los chunks del savepoint.
  Baja posterior al inicio impide finalizar; ack de despacho tras baja/ACL revocada
  registra IDs sin conceder otra petición ni acceso.
- Los locks compartidos reales bloquean los métodos exclusivos de
  IdentityAdministration (global/membresía) con SQLSTATE55P03; el lock de saga
  rechaza la migración concurrente y vuelve a estar disponible después.
- Se repitieron las baterías T003 y journal/relay: datos/control/roles/head intactos
  tras rollback. Imagen rag-f04-tools:t005-fence con dieciséis hashes correctos.
  Composición QA con cuatro RO SQL/TLS, sin día/Bao/S3/IdP ni puertos.
- Logs de ambas instancias con control positivo y ERROR observado; canary de texto
  ausente. Salida privada capturada solo en servidor, sin copiar registros brutos.

Límite explícito: son componentes SQL probados con transacciones tenant revertidas
y control QA sintético retenido, no el worker completo. Pendientes: runtime limitado,
logins reales/autoridad F04 en vivo, S3+parser, crash del proceso después de un commit
tenant persistente y antes del ack, carreras HTTP, parada/reinicio completos,
migración persistente y recuperación del catálogo. T002/T003/T005 siguen abiertas;
no aceptar F04 ni anticipar F05 por estas pruebas.

## T005 fencing integrado — PR #40

Head 4b36706abdce2ffdb5a1d4175e297d20dd424d4b, merge
3ec113a6a60ee3c20bdb178c6ba8f93e949f96c7. Cuatro checks de head y tres del merge,
revisión delegada del mismo agente, ambos checkouts limpios y docs válidas.
25 tests postmerge de guard/journal y dieciséis hashes de imagen correctos.
[Postmerge](https://github.com/dlalvarez/rag-platform/pull/40#issuecomment-6569726151).

## T005 runtime limitado preparado, todavía sin activación

Contrato [runtime.md](runtime.md) previo al código; alcance R01..06/AC01..05.
worker.py implementa relay y consumo secuencial con autorización original antes de
I/O, descarga verificada, parser aislado y contexto nuevo antes del commit protegido.
Reconcilia resultado READY ya confirmado mediante metadata/IDs, sin volver a leer
contenido. Caducidad/parada/revocación no generan fallback administrativo.
Dependencia temporal se reintenta; parser inválido/NEEDS_OCR permanece cerrado.
Si no es posible escribir diagnóstico tenant tras revocación, el envelope terminal
inspeccionable conserva el resultado operacional; no forzar acceso privilegiado.

Runtime con AppRole F03 ya existente, entrega propia rag-f04-worker y cuatro tenants
explícitos. Un socket por engine, hasta cuatro engines; registry/destino por catálogo.
Worker recibe solo control app, clave de autoridad, CA y entrega limitada, todos RO.
Emisor separado con día vigente publica una identidad de aplicación de una hora;
el worker no renueva ni recibe el día. Sin root/roles nuevos/contraseñas nuevas.
Imagen runtime no contiene scripts administrativos ni archivos de migración.

La API puede seleccionar explícitamente el perfil ingestion para adoptar el head F04
sin relajar el rechazo de heads desconocidos. RAG_F04_ENABLED requiere F03_ENABLED;
default F02/F03 intacto y mismas rutas F03. El perfil no habilita endpoints T006.
Helper DocumentStateService prepara baja lógica con permisos manage y auditoría,
sin eliminar objetos/versiones/chunks; su carrera real se prueba en la entrega operativa.

Pruebas ejecutadas solo en ragdev01:

- 675 tests correctos (656 anteriores +19), lint/formato/docs/diff. Treinta tests
  focalizados de runtime/guard correctos. Advertencia Starlette/httpx ya conocida.
- Fixtures offline: scope fijo/duplicados/malformación, expansión del pool rechazada,
  un socket sin overflow, stop antes del claim, autoridad revocada/suspendida sin I/O,
  dependencia de catálogo en RETRY, reconciliación solo por outcome y spool cerrado
  ante fallo de parser o excepción privada. Son dobles para la orquestación: no
  acreditan integración S3/runtime/worker.
- Worker/emisor/API compatible construidos sin sustituir servicios. Composición
  worker: cuatro RO, non-root, cap_drop ALL, sin puertos/privileged/día/admin.
  Emisor separado: solo tres montajes de día/entrega/CA.
- Las tres imágenes rag-f04-worker:t005, rag-f04-api:t005 y
  rag-f04-tools:t005-runtime contienen exactamente los 66 módulos Python de
  fuentes actuales, comprobados tanto en src como en el paquete instalado ejecutado.
  Worker con manifiesto correcto; imágenes API/worker sin scripts/admin/migraciones.

Pendientes antes de aceptar T005: adopción persistente y rollback/recovery real del
catálogo, autoridad/logins F04 en vivo, S3+parser completo, crash tras commit persistente
antes del ack, revocación/baja/parada reales y regresiones. Preparación operativa en
PR separado para mantener revisión acotada. API actual F03 y recursos intactos;
no hay worker/esquema F04 activados ni aceptación de fase o avance a F05.

Revalidación SQL adicional con rag-f04-tools:t005-runtime (paquete instalado actual):
toda la batería de esquema/journal/fencing pasó otra vez en las cuatro fixtures,
incluidos dos procesos/locks administrativos, rollback de chunks, parada y baja.
Logs con controles positivos/ERROR y canary ausente en ambas instancias. Sin activar
esquemas/perfiles/worker F04; esta prueba no sustituye la integración S3 pendiente.

## T005 runtime integrado — PR #41

Head 56fc143d54ad3498ac0716be0227e485bb3575f9, merge
e0b73e7f36fa1d73474df36f3e09deed64b9196c. Cuatro checks de head/tres de merge,
revisión delegada del mismo agente; checkouts limpios y documentación válida.
43 tests postmerge de runtime/guard/perfil; tres imágenes con 66 módulos src e
instalados exactos. [Postmerge](https://github.com/dlalvarez/rag-platform/pull/41#issuecomment-6570349821).
No se aceptó T005/F04 ni se activaron servicios por integrar estos componentes.

## Entrega operativa T005 — preparación

[Procedimiento](../../ops/f04/adoption.md): alcance exclusivo de cuatro fixtures,
adopción aditiva con fallo DDL intencional/FAILED honesto/recovery, roles/logs/TLS y
datos anteriores conservados. Control app recibe solo SELECT/INSERT/UPDATE de cola;
la herramienta administrativa se mantiene fuera del worker.

Seed separado con usuario OIDC/identidad de aplicación limitados, sin día/admin SQL/
migrator/S3 admin. Repos nuevos y originales HTTPS; journal privado de UUIDs/hashes
sintéticos con cada recurso conservado. No sobrescribir runs anteriores.
El PDF de fallo parcial se comprobó en ragdev01: primera página legible y segundo
stream inválido -> extractor real devuelve PARSER_INVALID, sin resultado parcial.

Aún no se han ejecutado adopción persistente, promoción API/worker ni seeding.
Primero publicar/revisar el head del PR operativo y sus checks, luego ejecutar la
validación manual de desarrollo prevista. No atribuir evidencia real a esta preparación.

Composición operativa validada en ragdev01: adopción con seis montajes y solo día RW;
seed con siete montajes, solo resultados RW, sin día/admin/migrator. Imagen construida
y tres hashes exactos de adopt/seed/emisor. Ruff/formato/docs/diff correctos.
No se han ejecutado todavía migraciones ni seeding por estos checks de preparación.

## Adopción persistente y API compatible ejecutadas

Desde PR42 head4df769eb41cb94cec1f101981b2da2267e3b4ccb, cuatro checks correctos,
revisión delegada previa y scripts de imagen exactos. En SAME_A/SAME_B/TWO_A/TWO_B
pasaron fallo DDL22012 con rollback físico, FAILED honesto sin observed_version falsa,
recuperación/repetición F04, datos anteriores conservados y logins app/readonly reales
con TLS/defaults de logs/grants mínimos. Cola pública instalada aditiva/repetida,
control app solo SELECT/INSERT/UPDATE. Snapshots de identidades/tenants ajenos/jobs
conservados y día intacto. Sin downgrade ni reinicios de datos.
[Registro](https://github.com/dlalvarez/rag-platform/pull/42#issuecomment-6570881602).

Solo API se recreó con rag-f04-api:t005, imagen exacta y siete RO; datos/IdP/Bao no
se reiniciaron. Identidad limitada reemplazada DESPUÉS del cierre anterior, sin
password/renovación del día. HTTPS health F04 correcto. La superficie sigue F03;
endpoints T006 aún pendientes. Health no acredita acceso documental.

Primer seed del run cfe3a53d-09e7-4626-993c-641df19f8ca7 detenido en START:
el helper Humans requiere /run/f02-auth, ausente en ese perfil. El run conserva solo
started.json; no creó repos/documentos/objetos. Se añade tmpfs privado de 1 MiB
0700 propio, sin montar autenticación del host ni añadir día/admin. Inicialización
y limpieza del helper real en el contenedor corregido pasaron sin crear recursos.
Run anterior conservado; el reintento usará un directorio nuevo, sin sobrescribirlo.

Controlador f04_worker_check.py y overlay RO preparados para pruebas reales con la
imagen worker, sin día/admin/migrator/OIDC passwords. Modos positivos/replay,
solicitud explícita, parser cerrado, dependencia, crash/ack y pausa para cambios de
autorización/parada. Todavía no se atribuyen estos resultados como ejecutados.

## Worker real — positivos y fallos, run 15bbc3e9-06dd-4cdb-ad15-1c9ab055d8d3

Seed corregido desde df2df77a83ce57deb19917892dad7a2f17fbe9df con CI/revisión:
52 originales HTTPS nuevos en cuatro repos propios, replay sin duplicados y 16
intenciones positivas explícitas. Manifest/journal retenidos; primer run fallido
cfe3... conservado sin recursos. Identidad del seed revocada al cerrar y reemplazada
antes del consumidor siguiente. Sin contraseñas ni renovación del día.

Worker real rag-f04-worker:t005, paquete de 66 módulos exactos. Inspección real de
contenedor: non-root/rootfs RO, seis montajes RO (cuatro runtime + script/manifest),
sin día/admin/migrator/OIDC passwords. En SAME_A/SAME_B/TWO_A/TWO_B pasaron S3 y
PDF/DOCX/MD/TXT: hash/tamaño del original retenidos, normalized_hash/config,
bloques/chunks/offsets/páginas/secciones, rol/destino/TLS propios y replay sin nueva
versión/envelope/chunks. Hasta cuatro engines y cero préstamos pendientes.
Dieciséis resultados READY_FOR_EMBEDDING, no PUBLISHED.
[Registro](https://github.com/dlalvarez/rag-platform/pull/42#issuecomment-6571654156).

Negativos reales en same-a (instancia compartida) y two-b (segunda instancia):
scan -> NEEDS_OCR; PDF con fallo después de página válida -> FAILED_TERMINAL/
PARSER_INVALID; cifrado -> FAILED_TERMINAL/PARSER_ENCRYPTED. Todos sin chunks;
originales retenidos. No se simula OCR ni se inventa texto.

Crash real en ambas topologías: os._exit(85) en RESULT_COMMITTED, después del commit
tenant y antes del ack control. Nuevo proceso observa resultado íntegro persistente,
espera caducidad real y recupera el mismo envelope con intento 2; extractor configurado
para fallar si se invocara de nuevo, no se llamó. Chunks/conteos/versiones sin duplicar.
Tras el crash se reutilizó la identidad de aplicación aún válida (ensure); su cierre
normal posterior la revocó, evitando dejar una copia activa perdida.

Dependencia de etapa inyectada tras descargar original, en ambas topologías:
FAILED_RETRYABLE + RETRY, cero chunks; backoff real y segundo intento con extractor
real recuperan la misma versión/job/original, sin rotación ni duplicados.

Aún pendientes: secuencia A→B→A explícita, SIGTERM/parada y bajas/revocaciones durante
PARSED, logs/canary/temporales finales y revisión/CI/postmerge. Controladores adicionales
de operador restringen tenant, repo/run, owner y usuarios sintéticos antes de cambiar
ACL/membresía o tombstone; no son el worker y no reciben bootstrap/migrator/S3 admin.
Regresión de preparación: 675 tests correctos y ruff/formato/docs/diff.
F04/T005 siguen abiertas hasta completar esas puertas y T006/T007.

## T002/T003/T005 — puertas reales completadas en PR #42

Run 15bbc3e9-06dd-4cdb-ad15-1c9ab055d8d3 retenido. Desde d21571f pasaron
ocho pausas en same-a/two-b: SIGTERM en PARSED -> RETRY/STOP_REQUESTED sin chunks,
parada limpia y recuperación; tombstone/ACL/membresía durante PARSED -> resultado
tardío bloqueado, sin chunks. Tombstones/originales conservados; ACL y membresía
restauradas en finally. El operador separado limita tenant/run/repo/owner/actores,
sin trasladar sus credenciales al worker.

Desde 9983b45358e05a61940de78fc8eb2cf46654d455, con cuatro checks y revisión
delegada previa, se repitió A→B→A en el mismo proceso en ambas topologías con
configuraciones nuevas 896/64, 1152/64, 1536/64 sobre originales existentes. El
observador STARTED verificó el orden exacto; cada resultado verificó rol/BD/TLS,
hash/config/offsets/chunks/original y cero préstamos pendientes. Historial retenido.
La primera secuencia 384/64..768/64 se conserva; no se usa su salida perdida como
evidencia de esta aceptación.

Privacidad real en same-a/two-b: login app limitado con siete GUC privados verificados,
canario presente en chunk real, LOG fijo positivo y error SQL23514 provocado por
INSERT tardío dentro de savepoint revertido. En logs reales de ambas instancias
aparecen LOG y ERROR; el texto F04_WORKER_PRIVATE_CANARY está ausente. También
ausente en logs API/MinIO/Bao desde inicio del run. Registros brutos solo en memoria
del servidor, sin publicarlos ni atribuir a esta prueba una garantía universal.

Worker de entrada normal, sin controlador montado: dos trabajos nuevos sobre los
mismos originales dependency con configuración 2048/128, uno en cada instancia.
Inspección: usuario1000, rootfs RO, exactamente cuatro mounts RO, sin día/admin/
migrator/OIDC passwords. Dos eventos ingestion_job con código NONE, canario ausente.
Al quedar inactivo: /tmp sin archivos, sin FD de spool/borrados ni hijos pendientes.
SIGTERM y exit0; verificación posterior desde consumidor nuevo confirmó ambos
resultados íntegros/SUCCEEDED, hashes/offsets/procedencia/originales conservados.
Servicio normal quedó detenido limpiamente; contenedor/fixtures/historial retenidos.

Regresión final: 675 tests, ruff/formato/docs/diff correctos. Solo warning conocido
Starlette/httpx. Sin nueva dependencia, migración, política Bao, password, root,
reinicio de datos o activación F05. No backup/restore acreditado por estas pruebas.
Aceptación técnica de T002/T003/T005; CI/revisión del head final y postmerge deben
quedar registrados en la conversación de PR42 antes de empezar implementación T006.
F04 sigue abierta: API T006 y regresiones/aceptación T007 pendientes.

## T006 en preparación — posterior a aceptación de PR42

PR42 integrado en develop@4405f848546ebccd2203f902e9032ab88a770ea9:
cuatro checks de head/tres de merge, ambos checkouts limpios, docs correctos y
19 tests de runtime postmerge.
[Registro](https://github.com/dlalvarez/rag-platform/pull/42#issuecomment-6572748022).

Contrato api.md formalizado antes del código. Perfil ingestion añade recepción con
intención/candidato dentro del mismo commit tenant, sin control I/O en la recepción,
y rutas de versiones/jobs/tombstone. Perfil documents y superficies F03 conservados.
Versiones/progreso exponen solo metadata explícita, con vínculo de tenant/doc/actor/
intención y ACL; reader mantiene readonly sin grants ops. Nueva ruta DELETE conserva
originales/chunks/historial e idempotencia del servicio ya probado.

702 tests correctos en ragdev01, incluidos 27 nuevos de HTTP, vínculos de envelope,
minimización y cursor; 67 junto a recepción/API F03. Ruff/formato/docs/diff correctos,
solo warning conocido Starlette/httpx. Sin nueva dependencia/migración/política Bao.
Imágenes T006 y batería real HTTP/rollback preparadas; no atribuir aún despliegue ni
aceptación real T006. La batería conserva un run exclusivo y checkpoints antes/después
de baja de resultados para poder recuperar un ensayo interrumpido sin repetir cambios.

## T006 — activación e ingreso reales

Desde PR43 head26b92958ae2288e0e74dfec5c048767d54611bf7, cuatro checks y
revisión delegada previa: solo API promovida a rag-f04-api:t006, siete RO/usuario1000,
TLS/health F04 y entrega limitada reemplazada después del cierre anterior.
IDs PostgreSQL/MinIO/Bao/IdP iguales antes/después; sin reiniciar esos servicios.
Historial T005 consultado por HTTPS con reader en cuatro fixtures, versiones/jobs
correctos sin grants ops. Un primer smoke auxiliar no encontró sus módulos al invocarse
con -c; se corrigió sys.path del lanzamiento. Consultas posteriores503 se resolvieron
con ensure de la entrega app caducada (TTL una hora), sin password/renovar el día ni
cambio de código/permisos. No atribuir a esos intentos un fallo de datos.

Run nuevo a75adb4c-445c-46d6-98ab-c558a8308112 conservado, directorio privado
/home/diego/proyectos/rag-platform-f04-api-runs/a75adb4c445c46d698abc558a8308112.
Seed pasó en SAME_A/SAME_B/TWO_A/TWO_B: cuatro repos nuevos, veinte originales,
recepción HTTPS/replay sin duplicados y candidato/intención automáticos. Alice/Bob/
Carol consultan versiones (reader sin ops); Dave403/sin JWT401, originales exactos.
Baja HTTP repetida antes de worker -> versiones/original404; editor/reader no pueden
borrar. Manifest solo UUID/hash/tamaño/actor sintéticos, sin texto/credenciales.

Por fixture, fallo inyectado después de INSERT candidato/intención dentro del commit:
recepción conserva OBJECT_STORED pero documento/versiones/intención no existen,
objeto retenido. Tras caducidad real del lease, recuperación confirma mismo original,
dos versiones/una intención; replay no duplica. Esto prueba rollback SQL real y
recuperación hacia adelante, no backup/restore ni atomicidad entre bases.
Worker/verify final aún pendientes; no declarar T006 aceptada por este seed.
