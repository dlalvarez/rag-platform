# Configuración inicial controlada del acceso diario

D001/D002 del [plan](DAY_ACCESS.md). Diego confirmó que custodia la clave unseal
original y la contraseña del operador. Se prepara un procedimiento interactivo,
no se ejecuta mantenimiento desde las herramientas de Codex.

## Operación que debe revisar el operador

1. Comprobar árbol/configuración esperados, paths privados y host de desarrollo.
2. Mostrar el efecto y exigir CONFIGURAR24H en su propia terminal.
3. Pedir unseal y contraseña con entrada oculta; conservar solo en memoria.
4. Añadir temporalmente al listener disable_unauthed_generate_root_endpoints=false.
   Reiniciar únicamente OpenBao; desbloquear con la clave proporcionada.
5. No adoptar ni cancelar una ceremonia ajena. Generar root mediante quorum 1/1,
   configurarlo sin imprimirlo/guardarlo, crear f01-dev-day y añadir las dos rutas de
   emisión a la política del operador. Comprobar que f01-cli no cambió.
6. Revocar el root temporal y comprobar lookup HTTP 403, incluso al fallar configuración.
7. Restaurar bytes originales de configuración en finally y reiniciar solo OpenBao.
   Desbloquearlo otra vez con la misma clave aún en memoria. Sin init, rekey o borrado.
8. Autenticar al operador, probar una sesión diaria de ensayo y revocarla; emitir
   el día operativo y guardar únicamente su token en tmpfs privado.
   El proceso termina sin retener contraseña, root o unseal.

Dos reinicios de OpenBao invalidan disponibilidad momentáneamente y requieren unseal.
No reiniciar otros servicios. Si falla la restauración, informar código cerrado y
no declarar éxito; conservar datos. Si hay cambios ajenos de config/política/rol,
detenerse antes de sobrescribirlos. La configuración administrativa requiere la
ejecución consciente de este comando por Diego; no se presume autorizada en background.

## Comprobación y límites

Tests de restauración/errores, quorum/nonce, políticas y TTL, cliente diario y archivos
privados antes de pedir ejecución. Después: TTL real, dos ejecuciones con el mismo
token, rol corto intacto, endpoint antiguo deshabilitado de nuevo, root rechazado,
regresión F00 y CI. No declarar transcurrido un día a partir de TTL o reloj simulado.
No existe aún una sesión diaria hasta que el procedimiento termine correctamente.
