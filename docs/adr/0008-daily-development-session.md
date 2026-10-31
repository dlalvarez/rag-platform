# ADR 0008 — Sesión diaria de pruebas en desarrollo

**Estado:** duración de 24 horas solicitada expresamente por Diego el 2026-10-31.
Propuesta técnica preparada; activación administrativa pendiente. No implementada.
Referencias: [ADR-0004](0004-secrets-storage.md), [ADR-0007](0007-delegated-development-review.md),
[contrato y plan](../../ops/f01/DAY_ACCESS.md).

## Problema y decisión propuesta

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

## Configuración inicial y decisión pendiente

Crear el rol y ajustar esas dos rutas de emisión requiere una identidad administrativa.
El root de inicialización fue revocado y la política f01-operator no concede esas
operaciones. No se puede afirmar que la contraseña del operador baste para configurarlo.

Determinar con Diego si dispone de otra identidad administrativa autorizada o si hay
que preparar recuperación controlada. No generar root, habilitar endpoints
deshabilitados, reiniciar OpenBao ni solicitar la clave de desbloqueo por iniciativa
propia. La API autenticada de generación root y las condiciones de acceso deben
verificarse antes de decidir un procedimiento; el endpoint antiguo está deshabilitado
por defecto en esta versión.

La configuración administrativa es una operación inicial. Tras ella, la rutina diaria
solo exige la contraseña del operador una vez para iniciar las 24 horas.
No dejar root disponible a Codex ni usarlo para ejecutar pruebas.

## Impacto, alternativas y reversión

Cambia la duración/custodia de un token de desarrollo respecto al límite de ADR-0004.
No cambia el roadmap, aislamiento, secretos tenant, políticas de datos, esquemas,
servicios de negocio, F01 aceptada ni la custodia de unseal. F02 no comienza.
Un token de desarrollo robado tendría una ventana mayor, hasta la revocación o las
24 horas; se acepta evaluar ese cambio explícito para la VM de desarrollo.

La alternativa de conservar la contraseña del operador en un agente o archivo para
reautenticar se descarta en esta propuesta: no es necesaria para el rol diario.
La alternativa ACC de un uso no satisface la petición y queda disponible como opción.

Reversión: revocar la sesión diaria y retirar la emisión del nuevo rol mediante
operación administrativa revisada. Conservar f01-cli y el flujo corto funcionando.
No borrar Raft, datos o credenciales tenant ni retirar TLS/protecciones.

## Fuentes y evidencia pendiente

[API AppRole](https://openbao.org/docs/api/auth/approle/),
[generación root autenticada](https://openbao.org/docs/api/system/generate-root-token/),
[endpoint antiguo](https://openbao.org/docs/api/system/generate-root/).
Documentos oficiales consultados el 2026-10-31; no sustituyen prueba del servidor.
DAY-01..06 y sus pruebas se definen en el plan. Esta entrega es documental;
no declara sesión activa, configuración aplicada ni ensayo de 24 horas completado.
