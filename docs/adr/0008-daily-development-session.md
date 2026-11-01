# ADR 0008 — Sesión diaria de pruebas en desarrollo

**Estado:** duración de 24 horas solicitada expresamente por Diego el 2026-10-31.
Decisión aplicada por Diego mediante CONFIGURAR24H y verificada en ragdev01.
Referencias: [ADR-0004](0004-secrets-storage.md), [ADR-0007](0007-delegated-development-review.md),
[contrato y plan](../../ops/f01/DAY_ACCESS.md).

## Problema y decisión aprobada

La entrega ACC-01..05 de PR #17 autoriza una batería, pero Diego solicita trabajar
durante al menos un día completo sin reautorizaciones. El AppRole f01-cli vigente
tiene token de 15 minutos y máximos de 60 minutos; el archivo de entrega dura diez.
Alargar únicamente el archivo no amplía la sesión del servidor.

Crear f01-dev-day, exclusivamente para ragdev01, con los mismos permisos de datos
f01-provisioner y política default. SecretID de diez minutos/un uso para iniciar
la sesión, intercambio inmediato por token reutilizable de 86400 segundos.
token_ttl, token_max_ttl y token_explicit_max_ttl: 86400. Sin renovación automática
que permita superar el final original; un nuevo día requiere nueva autorización.
El rol f01-cli y las pruebas originales de expiración se conservan.

El token diario vive en tmpfs privado (directorio 0700, archivo 0600, propietario
validado), fuera del repositorio. Se reutiliza entre baterías; cerrar una conexión
local no revoca la autorización diaria. Revocación explícita cancela todo el día,
y OpenBao impone la caducidad aunque no se ejecute la limpieza local.
No guardar contraseña del operador, root ni clave de desbloqueo.

El operador mantiene únicamente su capacidad de emitir credenciales de la CLI:
añadir read al role-id y update al secret-id de f01-dev-day, sin permiso de editar
roles, políticas, métodos de autenticación o configuración. Sus permisos de datos
no aumentan. El provisionador diario no recibe privilegios administrativos de OpenBao.

## Configuración inicial autorizada

Crear el rol y ajustar esas dos rutas de emisión requiere una identidad administrativa.
El root de inicialización fue revocado y la política f01-operator no concede esas
operaciones. No se puede afirmar que la contraseña del operador baste para configurarlo.

Diego confirmó la custodia de unseal y contraseña del operador. La política default
de la versión 2.7.2 tampoco concede acceso a la generación root autenticada.
La comprobación sin autenticar devolvió 403 en esa ruta y 405 en la antigua,
deshabilitada. La configuración vigente no contiene una excepción.

Se aplicó [recuperación controlada](../../ops/f01/DAILY_RECOVERY.md): habilitar
temporalmente la ruta antigua, dos reinicios de OpenBao/unseal, root solo en memoria
del proceso interactivo, configuración del rol, revocación comprobada y restauración
exacta del listener. Solo se activa cuando Diego ejecuta el comando en su terminal
y confirma CONFIGURAR24H. No ejecutarlo unilateralmente desde herramientas de Codex.
No se pide ni registra unseal o contraseña en chat.

La configuración administrativa es una operación inicial. Tras ella, la rutina diaria
solo exige la contraseña del operador una vez para iniciar las 24 horas.
No dejar root disponible a Codex ni usarlo para ejecutar pruebas.

## Impacto, alternativas y reversión

Cambia la duración/custodia de un token de desarrollo respecto al límite de ADR-0004.
No cambia el roadmap, aislamiento, secretos tenant, políticas de datos, esquemas,
servicios de negocio, F01 aceptada ni la custodia de unseal. F02 no comienza.
Un token de desarrollo robado tendría una ventana mayor, hasta la revocación o las
24 horas; Diego acepta ese cambio explícito para la VM de desarrollo.

La alternativa de conservar la contraseña del operador en un agente o archivo para
reautenticar se descarta en esta propuesta: no es necesaria para el rol diario.
La alternativa ACC de un uso no satisface la petición y queda disponible como opción.

Reversión: revocar la sesión diaria y retirar la emisión del nuevo rol mediante
operación administrativa revisada. Conservar f01-cli y el flujo corto funcionando.
No borrar Raft, datos o credenciales tenant ni retirar TLS/protecciones.

## Fuentes y evidencia

[API AppRole](https://openbao.org/docs/api/auth/approle/),
[generación root autenticada](https://openbao.org/docs/api/system/generate-root-token/),
[endpoint antiguo](https://openbao.org/docs/api/system/generate-root/).
Documentos oficiales consultados el 2026-10-31; no sustituyen prueba del servidor.
DAY-01..06 y sus pruebas se definen en el plan. La activación real y las ejecuciones
independientes se registran abajo.

## Acreditación real

Diego completó la ventana autorizada: root temporal y sesión de ensayo revocados,
configuración original restaurada. Codex ejecutó daily verify y daily-cli en procesos
independientes sin nueva contraseña; aislamiento SQL/S3 en ambas instancias correcto.
La sesión operativa vence el 2026-11-01 a las 21:34:19 de Bogotá, sin extensión.
Se verificó TTL de 86400 segundos y vencimiento del servidor; no transcurrieron
24 horas durante la validación. Evidencia: [DAY](../evidence/f01-day-2026-10-31.txt).
