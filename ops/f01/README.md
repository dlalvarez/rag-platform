# F01 T001 — catálogo y bootstrap OpenBao

Planificación ratificada en [PR #8](https://github.com/dlalvarez/rag-platform/pull/8),
registro [6528543252](https://github.com/dlalvarez/rag-platform/pull/8#issuecomment-6528543252).
Diego confirmó preparados el gestor y el medio de copia fuera de línea el 2026-10-30.
T001 está en curso: no confundir estas confirmaciones con claves ya generadas o pruebas V03 completas.

Solo ragdev01, checkout /home/diego/proyectos/rag-platform. No ejecutar en el Mac.
Proyecto nuevo rag-f01-dev; datos /srv/rag-data/rag-platform/f01.
F00 conserva su proyecto/datos/servicios. Este incremento no aprovisiona tenants ni MinIO F01.

## Preparación reproducible

Desde el checkout del servidor, Python 3.12 y el uv 0.13.6 ya instalado:

    UV_PYTHON_DOWNLOADS=never /home/diego/.local/share/rag-f00-tools/bin/uv sync --frozen
    python3 scripts/f01_host.py prepare
    python3 scripts/f01_host.py config --quiet
    python3 scripts/f01_host.py build tools
    python3 scripts/f01_host.py up -d openbao postgres
    python3 scripts/f01_host.py run --rm -T tools python scripts/f01_operator.py status
    python3 scripts/f01_host.py run --rm -T control-check

Prepare se ejecuta una sola vez y rechaza datos/env preexistentes. Ya fue ejecutado
en ragdev01 para esta entrega: no repetirlo allí. Los demás comandos son repetibles.
El validador comprueba montaje ext4, rutas fijas sin symlinks, 20 GiB libres y 7 GiB
disponibles antes de iniciar recursos. No usar Compose directamente para saltar esas comprobaciones.

TLS: CA de desarrollo de 90 días, claves privadas fuera de Git con permisos 0600,
certificados públicos 0444; se requiere renovarlos antes de caducar. La CA privada
permanece como material de bootstrap protegido del host; nunca se monta en contenedores.
OpenBao usa Raft, TLS 1.3, usuario sin root, swap deshabilitado para el contenedor
y core dumps deshabilitados. Sin modo dev ni puertos publicados. Raft de un nodo no es HA.
PostgreSQL rechaza TCP sin TLS. La conexión del probe verifica CA/nombre y autentica SCRAM.

La cuenta f01_bootstrap es administrativa y solo se usa para preparar la cuenta del
migrador de control; no es runtime ni identidad tenant. f01_control_migrator tiene
LOGIN sin SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS y crea las tablas de control.
Los dos secretos SQL de bootstrap están en archivos protegidos externos; no son fallback
para credenciales tenant. No se crea aún un resolver ni provisionador tenant.

## Inicialización: solo Diego en su terminal

Abrir una terminal propia sin grabación de sesión, salida redirigida, capturas o
registro compartido. No ejecutar esta parte mediante herramientas de Codex.
Desde ese terminal:

    ssh diego@192.168.78.161
    cd /home/diego/proyectos/rag-platform
    python3 scripts/f01_host.py run --rm tools python scripts/f01_operator.py init

El programa requiere TTY y confirmación PREPARADOS antes de llamar sys/init.
Muestra la única clave de desbloqueo y el root temporal exclusivamente en ese terminal.
Guardar la clave en el gestor y en la copia fuera de línea. Guardar temporalmente el
root en el gestor para poder reanudar si falla el bootstrap. Confirmar GUARDADAS
solo después de guardar ambas copias de la clave y el root temporal.

El script desbloquea, configura KV v2 f01 con CAS obligatorio, userpass de infraestructura
para diego y AppRole f01-cli. Pide una contraseña de operador de al menos 16 caracteres,
la confirma y comprueba acceso sin root. Si es corta o no coincide, explica el motivo
y permite reintentar sin abortar ni mostrar el valor. Solo tras verificar operador/AppRole/CAS
revoca el root inicial y verifica que quedó inválido. Eliminar entonces su copia temporal.
No imprime passwords de operador, tokens AppRole/SecretID ni respuestas de bootstrap adicionales.
La clave mostrada sigue en el historial visual del terminal; cerrar esa sesión al terminar.
No pegar claves, tokens ni la salida de init en chat, Git, logs o evidence.

Si finaliza correctamente, informar únicamente «bootstrap completado».
Las pruebas reales de ese flujo aún no se ejecutaron por Codex: requieren este paso del operador.

## Interrupciones y reinicios

No repetir sys/init ni borrar Raft. Si está inicializado pero sellado:

    python3 scripts/f01_host.py run --rm tools python scripts/f01_operator.py unseal

La clave se introduce sin eco. Si quedó a mitad de bootstrap, con OpenBao desbloqueado
y conservando el root temporal:

    python3 scripts/f01_host.py run --rm tools python scripts/f01_operator.py resume

Resume vuelve a configurar solo el ámbito F01 y pide restablecer la contraseña.
No ejecutar resume después de completar el bootstrap y revocar el root.
Si el error ocurre justo tras revocarlo, comprobar primero check; no generar otro root automáticamente.
Si se pierde material antes de guardarlo, detenerse y revisar recuperación; no reinicializar.

Tras completar bootstrap, la prueba de recuperación de canary se ejecuta con:

    python3 scripts/f01_host.py run --rm tools python scripts/f01_operator.py check

Check pide únicamente la contraseña del operador y verifica el canary sintético
en UUID e2fc03f9-a253-4b02-8592-ff00409567b5, versionado/CAS y SecretID de un uso.
No es una cuenta SQL/S3 real ni contiene datos de negocio. Conserva ese canary para
la prueba posterior a reinicio. No se habilita listado/borrado general de secretos.

Para demostrar persistencia: check, restart solo openbao, status sellado, comprobar
rechazo de acceso sellado, unseal por Diego y check de nuevo. El restart y la prueba
de token expirado real se coordinarán después del bootstrap; no están acreditados todavía.

## Pruebas y trazabilidad

F01-R01/R03 → AC-F01-01/06 parciales → P1 → T001 → V01/V03.
Unitarias offline: tests/unit/f01; transportes HTTP simulados no acreditan OpenBao real.
Integración PostgreSQL: scripts/f01_control_check.py, con migraciones reales repetidas,
constraints, rol no-superuser, CA/password erróneas y TCP sin TLS rechazados.
No se demuestra todavía la existencia de dos bases tenant ni el resolver de AC-F01-06.

Errores del adaptador se limitan a códigos; no se devuelven cuerpos HTTP, DSN ni
excepciones del proveedor. UUID + versión exacta; CAS obligatorio; no fallback.
La sesión AppRole expira localmente y no reutiliza un SecretID consumido.
Un resultado de escritura de red incierto no se reintenta a ciegas: el futuro journal
T004 debe reconciliar versión/ownership antes de continuar.

## Reversión y pendientes

Detener solo F01 con python3 scripts/f01_host.py stop conserva PostgreSQL/Raft.
Down sin volúmenes también conserva los binds; el wrapper rechaza opciones de borrado.
La revisión control inicial rechaza downgrade destructivo: cualquier eliminación
requiere propuesta/migración específica y aprobación. No borrar datos como rollback.
Revertir el PR técnico no revierte por sí solo el esquema ya aplicado.

Pendientes: bootstrap humano, V03 real incluido reinicio y caducidad, backup externo
de Raft/restore y el resto T002–T007. TLS y SQL de este perfil son para datos sintéticos
de desarrollo. No hay HA, SLA, PITR independiente ni preparación de producción.
MinIO conserva el riesgo upstream archivado; no se instala ni modifica en T001.
