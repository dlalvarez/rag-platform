# F03 — acceso de aplicación de desarrollo

R/AC: F03-R01/R02/R03/R05; AC-01/02, validación parcial V01/V02/V06.
No acredita todavía la API documental ni el cierre de T002/F03.

La sesión diaria de infraestructura no administra policies/AppRoles (capabilities-self
real: deny en ambos paths). Desbloquear OpenBao no concede esos permisos.
El root inicial fue revocado. No entregar a la API el bearer diario como alternativa.

## Identidad y alcance

`application-scope.json` contiene solo IDs/referencias opacas de cuatro fixtures propias
F03 (namespace idempotente 67646a24-d263-4474-a722-71393ceda772). No contiene credenciales.
Doce refs: SQL app/readonly y S3 por fixture. No migrator, admin de instancia, MinIO admin,
canary, wildcard, listado KV ni metadata. La policy JSON se genera con paths UUID exactos,
solo read y lookup-self/revoke-self. Lectura siempre de versión exacta.

AppRole f03-application: SecretID 600 s/un uso; token service 3600 s, máximo explícito
3600 s, sin default policy, sin período/renovación automática. El adaptador verifica
policies, rol/origen y límites; rechaza root, provisioner, permisos extra, caducidad y
revocación sin fallback. No expone write/attach_day. Las credenciales de aplicación
siguen sujetas a membresía/contexto/ACL en la API, no autentican usuarios.

La policy de f01-provisioner conserva sus permisos previos y añade exclusivamente
read role-id/update secret-id del nuevo AppRole. No permite editar su rol/policy.
La sesión diaria vigente puede emitir esa identidad limitada después del bootstrap,
sin otra contraseña por batería. f01-cli, f01-dev-day y f01-operator se verifican
sin cambios. No cambia contraseñas, referencias ni versiones existentes.

Alcance de desarrollo fijo: añadir otros tenants exige una ampliación explícita y
revisada de esta allowlist, nunca wildcard. No se afirma onboarding de producción.

## Bootstrap administrativo único

Solo después de revisar/integrar el PR y con checkout limpio en ragdev01:

```text
cd /home/diego/proyectos/rag-platform
python3 scripts/f03_application_host.py configure
```

El agente prepara/verifica antes la imagen mediante build-isolation. La herramienta
comprueba el hash de fuentes/scope embebidos; IMAGE_SOURCE_MISMATCH exige reconstruir
la imagen, no saltar el control. El operador confirma CONFIGURARF03 e introduce
únicamente la clave de desbloqueo original en su terminal (getpass). No copiarla
al chat, argumentos, variables de entorno, archivos ni repositorio. No pide password
del operador ni crea una nueva sesión diaria.

La ventana toma el mismo lock de directorio que las baterías diarias. DAY_BUSY
rechaza el mantenimiento antes de pedir claves/reiniciar si hay una batería activa;
con la ventana abierta, las baterías esperan hasta su salida. No borrar locks ni tokens.

Ventana concreta: dos reinicios SOLO OpenBao. Recuperación habilitada temporalmente,
ceremonia 1/1 existente, root en memoria para la configuración fija, revocación
verificada en finally, restauración atómica de la configuración/TLS original,
segundo reinicio/unseal y comprobación de endpoint de recuperación deshabilitado.
No init/rekey, borrado, reinicio PostgreSQL/MinIO ni cambio de visibilidad/puertos.
El archivo day.json no se abre, modifica ni elimina; su token sigue vigente tras reinicios.

Preflight rechaza policies/roles existentes distintos antes de escribir. Un fallo
parcial de instalación conserva lo ya creado para reintento idempotente, sin borrar
datos ni ampliar permisos. Una configuración concurrente ajena provoca stop condition.
Si falla, informar solo F03-APP-SETUP y su código; revisar estado/config antes de repetir.
No ejecutar init/resume/rekey ni generar/guardar un root manual para sortear el fallo.

Salida esperada: dos líneas PASS F03 APP SETUP. Después, el agente verifica con la
sesión diaria la emisión/read/denegaciones y entrega privada de aplicación.
El runtime documental aún no está desplegado; no declarar T002/AC completos por setup.

## Prueba reproducible sin claves del operador

`python3 scripts/f03_application_proof_host.py` crea red Docker interna exclusiva,
OpenBao 2.7.2 vacío en memoria y cliente limitado, sin puertos publicados ni acceso a
redes F01/F02. Usa solamente leaf TLS/CA existentes de desarrollo; no monta CA privada,
credenciales de SQL/MinIO/IdP ni sesión diaria. Rechaza nodo ya inicializado.
Prueba init sintético, revocación root inicial, dos recuperaciones reales/bootstrap
idempotente y revocación de sus roots, doce refs/versiones, SecretID de un uso,
denegaciones infra/list/write/delete/admin/create-token y revocación de aplicación.
Retira solo sus contenedores/red aleatorios en finally; no lee logs de servicios reales.

Límites: esta reproducción no acredita todavía los dos reinicios del OpenBao existente,
el handoff runtime, los pools con la nueva versión ni las operaciones documentales.
Se conservan esas puertas para T002/T003..T007.
