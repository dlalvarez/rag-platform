# F04 T004 — contrato de extracción y chunking

Implementa R02/R03/R06, acredita AC02/05 a nivel de parser/chunker; AC03 E2E se
demuestra con T005, no por este componente. Selección D-05 dentro del adaptador ya
previsto: pypdf 6.21.4, python-docx 1.2.0 y transitivas fijadas en uv.lock, sin OCR.

Entrada: descriptor privado regular de solo lectura y MIME de los cuatro tipos.
El worker verifica original/hash/autorización antes de entregarlo; el extractor no
recibe contexto de usuario, credenciales, rutas S3, conexiones SQL o instrucciones.
No usar filename como ruta. Revalidar los controles F03 de tipo/ZIP/bytes dentro
del presupuesto del proceso de extracción, evitando descompresión ilimitada en padre.

Salida tenant-local: bloques con ordinal, texto normalizado NFC/saltos LF, página
PDF real 1-based o null para formatos sin paginación, sección/título y tipo.
Offsets Unicode [inicio,fin) sobre una representación normalizada determinista,
con separador LF entre bloques. Chunks mantienen intervalo global, intervalo de
bloque, página/sección, ordinal y hash; conservar código/puntuación y cobertura.
Configuración inicial 1024 caracteres/128 de overlap; no confundir caracteres con
tokens. Cambiar parser/normalización/chunker/config crea otro fingerprint de proceso.

PDF sin texto útil, incluso una página con contenido no extraíble, bloquea
el documento completo con NEEDS_OCR; no publicar un subconjunto de páginas ni
fabricar texto. Páginas realmente vacías conservan un bloque blank_page y su número,
sin chunks inventados. Los LF sintéticos entre bloques no se indexan como contenido.
No reconstruir tablas PDF como si fueran estructura garantizada.
DOCX: párrafos/títulos/tablas en orden, sin inventar páginas Word. Reportar rasgos
no soportados que puedan ocultar texto (p.ej. revisiones, notas, cajas de texto);
no omitirlos silenciosamente. Markdown conserva bloques de código y headings.
La normalización no elimina puntuación SQL ni cambia espacios interiores de código.

Aislamiento Linux x86_64 de ragdev01: subprocess dedicado, solo FD 0 original RO,
1 salida privada acotada y 2 descarte. Preload de bibliotecas antes de leer archivo.
no_new_privs y filtro seccomp por allowlist tras preload: sin abrir archivos/red,
ejecutar otro programa o crear procesos. Sin variables de credenciales ni FD heredados.
Comprobar restricciones realmente; no afirmar que seccomp por sí solo elimina todo
riesgo de kernel/parser. [Referencia kernel](https://docs.kernel.org/userspace-api/seccomp_filter.html).

Presupuesto del hijo: 512 MiB address space, 30 s CPU, 45 s pared controlados también
en padre; entrada 10 MiB, 200 páginas, 2 millones de caracteres, 10 000 chunks,
16 MiB de IPC máximo con lectura incremental. Padre mata y espera al hijo si excede
tiempo/salida; sin resultado parcial. Sin fallback sin aislamiento si no se puede
instalar la política o la arquitectura no está soportada. Límites menores para ensayos
se identifican como perfil de prueba; no aumentar los máximos publicados.

Validar corpus sintético semántico nuevo (no sobrescribir originales F03), páginas/
Unicode/tablas/código, repetición, escaneado/malformado/cifrado, ZIP expansivo,
tiempo/memoria/salida y FD/red/archivos denegados. Errores solo códigos cerrados,
sin texto, nombres de archivo o excepciones de proveedor en logs/cola. Originales
y resultados no salen del servidor. Esta tarea no activa worker/API/esquema tenant.
