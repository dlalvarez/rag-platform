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
