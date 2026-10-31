# Acceso temporal de pruebas F01 — plan autorizado

Solicitud: agilizar las pruebas delegadas en ragdev01 sin compartir contraseña en chat.
ADR-0004 permite SecretID de un uso/10 minutos y token AppRole de 15 minutos.
ADR-0007 autoriza esta mejora dentro de F01; F02 no comienza.

## Contrato y tareas

ACC-01: el operador autentica una vez en su terminal y emite un SecretID del AppRole
existente; se guarda exclusivamente en un directorio 0700, archivo 0600, del usuario
sobre /run/user (tmpfs), fuera del repositorio. Nunca se almacena su contraseña.
ACC-02: una ejecución no interactiva consume/elimina el archivo antes de autenticar,
comprueba caducidad y propósito y falla sin fallback. Rechazar symlinks, permisos
amplios, propietario ajeno, archivo grande o esquema distinto. No sobrescribir grants.
ACC-03: las pruebas usan f01-provisioner, nunca operador/root. CLI-check comparte
una sesión con la batería aprobada. Revocar el token al salir, incluso ante fallo.
No cambiar políticas, TTL de roles, servicios existentes ni custodia de unseal.
ACC-04: verify comprueba lectura del canary original, rechazo real del SecretID
reutilizado y token revocado. cli-check conserva las comprobaciones T007 aprobadas.
No borrar fixtures ni rotar credenciales existentes. discard elimina la copia local;
no revoca un SecretID copiado: se agota al usarlo o caduca a los diez minutos.
ACC-05: registrar fuentes, tests offline y evidencia real sin valores de secretos;
PR y checks obligatorios antes de integración delegada.

## Pruebas previstas

Permisos/symlinks/propietario, consumo único entre procesos, expiración, propósito,
JSON malformado, emisión rechazada/no sobreescritura, revocación en éxito y fallo;
HTTP simulado sin credenciales reales, no fallback ni valores en excepciones.
Mantener tests T001–T007; probar Compose e imagen nueva sin reiniciar servicios.
La prueba positiva real necesita que Diego emita una autorización desde su terminal.
No declarar PASS real antes de ejecutar verify/cli-check contra OpenBao.

## Fuentes

[AppRole](https://openbao.org/api-docs/auth/approle/),
[token](https://openbao.org/api-docs/auth/token/),
[ADR-0004](../../docs/adr/0004-secrets-storage.md).


## Uso comprobado

Preparación, solo tras reiniciar la sesión del host si el directorio runtime desaparece:

    python3 scripts/f01_host.py prepare-access

Desde la terminal del operador (no desde automatización ni con contraseña en argumentos):

    python3 scripts/f01_host.py run --rm access issue --purpose cli-check

Tras el PASS ISSUE, Codex ejecuta por SSH antes de diez minutos:

    python3 scripts/f01_host.py run --rm -T access-cli

Una autorización sirve para una batería completa. No es un acceso permanente:
cada batería posterior necesita otro SecretID emitido por el operador. El token de esa
batería dura hasta el TTL aprobado de 15 minutos y se revoca al terminar; no hay renovación
automática. Si caduca, falla cerrado y no lee contraseña ni usa una sesión anterior.

access monta solo CA y directorio temporal; no recibe bootstrap SQL/MinIO.
access-cli añade control e IAM de aprovisionamiento ya aprobados, sin bootstrap SQL
de ningún nodo. Usa actor de auditoría distinto del operador. La CLI interactiva
actual sigue disponible; las demás baterías no se convierten automáticamente.

Prueba no mutante opcional: issue --purpose verify seguido de run --rm -T access verify.
Comprueba el canary preexistente, rechazo de SecretID reutilizado y token revocado.
No ejecutada en este ensayo: la autorización se dedicó a la batería CLI completa.

Para cancelar la copia pendiente:

    python3 scripts/f01_host.py run --rm -T access discard

Si el grant falla o caduca, no reintentar indefinidamente ni reinicializar OpenBao.
Corregir el código/diagnóstico cerrado, eliminar solo la copia local si es necesario
y emitir otra autorización. No solicitar root, unseal ni contraseña por chat.

## Resultado y límites

180 pruebas offline correctas, Ruff/formato, documentación y negativos F00 correctos.
Diego emitió una autorización desde su terminal. Codex ejecutó access-cli sin TTY
ni contraseña: tres PASS T007 y PASS ACCESS CLI, incluyendo rechazo HTTP 403 tras
revocar el token. Archivo consumido y ausente; hashes de scripts y paquete instalado
comprobados. Regresión F00 posterior correcta. Ver [log](../../docs/evidence/f01-access-2026-10-31.txt)
y [fuentes](../../docs/evidence/f01-access-source-sha256.txt).
No nuevos servicios persistentes, políticas, privilegios, migraciones ni dependencias.
F01 sigue cerrada; no inicia F02. El riesgo de revisión por el mismo agente sigue
declarado en ADR-0007. Backup/restore/HA/PITR siguen pendientes.
