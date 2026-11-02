# F04 T005 — runtime limitado de desarrollo

Este perfil conecta los componentes de worker.md; no modifica la arquitectura ni
habilita F05. Toda ejecución en ragdev01. Dependencia: PR #40 integrado y comprobado.

## Identidad y despliegue

Worker Python separado de la API, un trabajo simultáneo, lease de 180 segundos,
parada con SIGTERM/SIGINT. Entrega propia en tmpfs privado rag-f04-worker, distinta
del consumer.lock de API. Reutiliza el AppRole de aplicación F03 de doce referencias
app/readonly/S3 para las cuatro fixtures del manifiesto existente; no amplía políticas,
no administra roles y no recupera root. Emisor de confianza con sesión diaria válida;
el contenedor worker recibe solo la entrega limitada de una hora, nunca el día.

Imagen runtime con src/dependencias fijadas y manifiesto público, sin scripts de
administración/migraciones/fixtures ni secretos de build. Raíz de solo lectura,
usuario no root, sin capacidades, no-new-privileges, tmpfs privado y recursos acotados.
Sin puertos; TLS control/tenant/Bao/S3 con CA existente. Archivo control app y clave de
autoridad limitados, sin migrator/bootstrap/IAM admin. Pool worker de un socket por
engine, hasta cuatro engines; conservar cotas de API y el registry del proyecto.

Solo cuatro tenants explícitos del manifiesto y catálogo READY con head F04 conocido.
La selección de destino se conserva en CatalogResolver; nada de host/db desde un job.
Relay de servicio lee solo intención/outcome por IDs y registra despacho, sin acceder
a texto como usuario. I/O de original y resultado requieren contexto original vigente.

## Ciclo

Relay reenvía intención pendiente y registra ack exacto incluso si hubo baja/ACL
revocada, sin conceder acceso. Claim revalida actor/membresía/ACL antes de I/O y usa
los guards aceptados para comienzo/finalización. Descargar original privado y verificar
hash/tamaño antes de pasar descriptor RO al parser aislado. Cerrar spool e hijo siempre.

Después del parseo, crear contexto fresco (el anterior expira a 30 s), renovar solo
el lease propio de cola y confirmar todos los chunks/metadata/auditoría en una
transacción tenant protegida. No renovar el token de aplicación ni la sesión diaria.
Resultado READY ya confirmado se reconcilia leyendo solo estado/IDs inmutables de
servicio; no ejecutar otra vez contenido por haber perdido el ack.

Fallo de parser/límites/cifrado/NEEDS_OCR es terminal y cerrado; dependencia se reintenta
con backoff/cota. Si revocación impide escribir un diagnóstico tenant, el estado
terminal del envelope inspeccionable sigue siendo la verdad operacional; no forzar
acceso como admin para cambiar metadata. Preservar el estado histórico y todos los datos.

## Activación y evidencia

Construir y probar sin activar contra head F03. Preparar API compatible F04 antes
de adoptar las migraciones persistentes, sin hacer que F03 acepte heads desconocidos.
Registrar grants de cola mínimos al control app y defaults de logs de roles tenant
mediante herramientas de instalación autorizadas; no llevarlas al runtime.

Batería real de S3/parser, cuatro formatos/NEEDS_OCR, duplicados, crash de proceso
tras commit tenant antes del ack, dos procesos/fencing, baja/ACL/membresía durante
trabajo, parada/reinicio y A→B→A. Comprobar rol/password separado de migrator,
TLS/logs/canary/temporales/capacidad y ausencia de día/admin en mounts. Regresiones
F00..F03, CI/revisión delegada del mismo agente/postmerge. Conservar fixtures.
No declarar estas pruebas por tests con dobles ni cerrar T005/F04 por instalar el contenedor.
