# Perfil F03 de repositorios y ACL

T004 desarrolla R01/R02, V01/V02/V06 y parte de AC-01/02.
Componente probado con OIDC/OpenBao/PostgreSQL reales; rutas HTTP pendientes de T006.
Una membresía activa y tenant READY/f03_tenant_0002 son requisitos previos a la ACL.

| Operación | Techo de rol tenant | ACL explícita del repositorio |
|---|---|---|
| Crear repo | owner/admin | Se crea ACL owner del creador en la misma transacción |
| Ver/listar | owner/admin/editor/reader | owner/admin/editor/reader |
| Cargar (T005) | owner/admin/editor | owner/admin/editor |
| Editar/baja lógica | owner/admin | owner/admin |
| Ver/editar ACL | owner/admin | owner/admin, con restricciones siguientes |

No hay bypass por platform_operator/support ni por owner/admin del tenant.
Un usuario sin ACL no ve el repo ni aunque conozca el UUID. No listado global de
repositorios privados. Rol tenant reader/editor limita una ACL antigua más poderosa.

Owner del repo puede administrar roles. Admin del repo solo administra editor/reader;
no puede promoverse ni modificar owner/admin. Target debe ser usuario/membresía activa
del mismo tenant y su rol tenant debe admitir el rol de repo solicitado.
Owner de repo no convierte al target en owner del tenant: son ámbitos distintos.

ACL y cambios de repo se serializan bloqueando la fila del repositorio. No retirar
el último owner efectivo activo. Si se retira el owner principal y hay otros válidos,
owner_id pasa determinísticamente al siguiente, dentro de la misma transacción.
La ACL es la autoridad; owner_id no es un permiso alternativo. Transferencias explícitas
se auditan; si el actor queda sin ACL, pierde acceso incluso siendo operador/owner tenant.

Baja lógica fija DELETED; conserva filas, ACL e historial, sin borrar documentos u objetos.
Cambios se auditan dentro de la transacción tenant. Denegaciones usan auditoría control
de catálogo cerrado, sin nombre/config/cuerpo, secretos o claims de identidad.
Esta fase no añade recuperación implícita de contenido para soporte.

## Datos y límites

Nombre NFC, 1..120 caracteres, sin espacios exteriores ni controles. Config validada
language auto/etiqueta acotada; no URLs, credenciales ni claves arbitrarias.
UUID lógicos; serializers no exponen conexión, secreto, bucket o clave de objeto.

Listados de repos/ACL: 1..100 (default 50), keyset por UUID, cursor HMAC ligado a
principal/tenant/colección (y repo para ACL). Cursor ajeno/alterado/no canónico se
rechaza antes de abrir conexión tenant o resolver secreto. Cada request revalida
membresía/estado/perfil; cursores no conceden autorización.

Hasta 1000 ACL por repo; exceso se rechaza como cuota, sin inserción parcial.
Errores de vocabulario cerrado; sin excepción de proveedor/input rechazado en salida.
AppRole de datos solo lee las 12 refs de fixtures habilitadas, sin bearer infra.

## Evidencia y límites pendientes

scripts/f03_repository_check.py: OIDC real de las cuatro identidades existentes,
bootstrap/membresías explícitas solo en cuatro tenants F03, AppRole limitado para
todos los accesos tenant y contexto documents. Prueba ambas topologías, CRUD, roles,
operador sin ACL, escalado, cursor ajeno, cruce UUID, último owner/transferencia,
suspensión de membresía con cero lecturas de secretos y baja con auditoría/historial.
Hash de catálogo/membresías/usuarios/roles previos conservado.

ops/f03/repositories-fixture.json conserva solo UUID sintéticos para T005/T006.
Repetición reutiliza los tres repos semilla por fixture. Los repos temporales de
prueba quedan DELETED con su historial; no se oculta esa retención como limpieza física.
Regresión T003 adapta probes a un conteo de documentos previo y nombres únicos, para
conservar futuros documentos válidos; no cambia DDL ni privilegios.

No carga/descarga, objetos o HTTP documental acreditados aún. AC-01..04 y F03 siguen
abiertos hasta pruebas API + SQL + MinIO integradas de T005..T007.
