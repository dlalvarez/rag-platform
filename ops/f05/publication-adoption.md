# Adopción de publicación F05 en desarrollo

Este controlador prepara el paso de los cuatro fixtures existentes de tenant0004
(o tenant0005) a tenant0006 y de control0006 a control0007.
No sirve para tenants nuevos, otros espacios ni una instalación que ya haya
empezado a generar embeddings. No cambia políticas Bao, día, modelo ni tenancy.

## Preflight

Usar un directorio nuevo0700 fuera del repositorio, distinto del journal de la
adopción de espacios. Exportar su ruta como RAG_F05_PUBLICATION_QA_ROOT.
Con las variables F02 existentes y los archivos ops/f02/compose.yaml y
ops/f05/publication-adoption.compose.yaml, ejecutar solo
publication-adopt-f05 preflight mediante compose run --rm --no-deps --pull never.
La imagen de herramientas debe existir; no reconstruirla implícitamente.
La composición monta código/migraciones/script revisados RO y journal privado.

Antes de usar la sesión diaria, comprobar su status con la herramienta existente.
Preflight abre el día vigente sin renovarlo, valida cuatro nombres/UUID distintos,
targets postgres/postgres2:5432 con verify-full, catálogo conocido, logins reales
app/readonly y hashes F04/espacios/vectores. Exige un único espacio Qwen aprobado
y vacío, sin jobs PENDING/RETRY/RUNNING en el scope. No ejecuta DDL.
Checkpoints0600 conservan hashes/IDs; no textos, vectores ni credenciales.
Repetición idéntica permitida; conflicto o symlink rechazado sin sobrescribir.

## Ventana de cambio

Solo después de CI y revisión del HEAD exacto, preflight correcto e imágenes
API/INGEST/EMBED compatibles preparadas con sus perfiles explícitos.
Detener solo los consumidores autorizados, conservar contenedores/imágenes/datos
anteriores y verificar cierre de sus conexiones/locks. El aviso de orphan de
Compose no autoriza remove-orphans ni borrar el worker F04 conservado.

Ejecutar publication-adopt-f05 adopt. Requiere preflight previo y lo repite en
todos los fixtures antes del primer DDL. La sesión diaria serializa el ciclo.
Control se actualiza a0007 y se repite; el login real f02_identity_app comprueba
shape de cola y SELECT/INSERT/UPDATE, sin DELETE/TRUNCATE/REFERENCES/TRIGGER/CREATE.
No se otorga lectura del catálogo Alembic al runtime.

Cada tenant exige cero conexiones app/readonly antes de migrar. Se inyecta un
fallo22012 tras DDL: catálogo FAILED/MIGRATION_FAILED/observed NULL y versión física
original, sin marcador de prueba ni cambios F04. Recuperar y repetir runner
controlado hasta0006; verificar espacio Qwen existente sin cambiarlo, logins y
privilegios reales, originales/espacios/vectores conservados. Perfiles anteriores
de resolver deben rechazar el nuevo head. Se conservan identidades, jobs y otros
tenants de control. Un fallo detiene el ciclo; no hay downgrade ni compensación
que borre datos. Conservar journal para resolverlo y repetir, sin iniciar runtime
sobre un tenant incompatible.

## Después

Reemplazar entregas limitadas solo tras lock libre, usando los emisores existentes
y el wrapper EMBED nuevo. No configure, root, nuevas políticas ni renovación.
Iniciar únicamente servicios/imágenes revisados, con publicación habilitada y sin
recrear dependencias. El controlador no inicia servicios ni emite sus tokens.
Comprobar originales HTTP/S3 y ejecutar worker/Qwen, fallos entre commits y
búsqueda antes de aceptar F05.

Evidencia inicial: preflight real de cuatro fixtures/dos instancias correcto,
sin migraciones. Las pruebas de fallo/recuperación de este controlador completo
y la ventana persistente todavía no se han ejecutado. Las pruebas SQL previas de
los helpers, con rollback, no sustituyen esa evidencia.
