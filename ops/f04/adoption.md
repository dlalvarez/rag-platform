# F04 T005 — adopción y validación en ragdev01

R01..06/AC01..05; [contrato runtime](../../specs/F04-ingesta-versionada/runtime.md).
Procedimiento manual de desarrollo, revisado contra el head del PR y CI correcto.
No hay promoción automática por merge. Las etapas se ejecutan secuencialmente;
conservar fuentes, snapshots y todos los recursos sintéticos. No main/tag/producción.

## Antes de adoptar

Verificar head/imagen/paquete instalado exactos, 675 tests y CI del PR operativo.
API actual F03 y worker sin activar. Sesión diaria vigente; no extraer bearer ni
pedir password por prueba. No ejecutar baterías que toman el día en paralelo.
Manifiesto de alcance: cuatro fixtures F03 existentes, no tenants adicionales.

activate.compose.yaml usa herramienta administrativa separada con día, dos
bootstrap SQL, control migrator/app y CA. No es runtime y no recibe S3 admin/IAM root.
Rechaza target suspendido/desconocido, destino ajeno y jobs RUNNING antes de mutar.

## Migración y recuperación

Registrar fingerprints de datos F03/identidades/tenants ajenos/jobs anteriores.
Validar head/propiedad antes de aplicar defaults de logs a roles propios.
Por fixture, aplicar migración dentro de un fallo DDL intencional: comprobar SQLSTATE
22012, rollback físico y catálogo FAILED sin observed_version falsa. Recuperar con
migración F04 real y repetir. Verificar logins app/readonly, TLS/grants/logs y datos
anteriores intactos. Instalar cola pública aditiva; control app solo SELECT/INSERT/UPDATE.
No downgrade, purge, reinicio de datos o recuperación root de OpenBao.

Desde el worktree revisado, con env F02 operativo:

    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/activate.compose.yaml build activate-f04
    docker compose --env-file /home/diego/proyectos/rag-platform/.env.f02 -f ops/f02/compose.yaml -f ops/f04/activate.compose.yaml run --rm -T --no-deps activate-f04

Capturar salida privada en servidor y devolver solo PASS/códigos cerrados.
Un fallo deja el estado honesto e impide promover hasta recuperar la misma operación.

## API compatible e identidad

Tras comprobar las cuatro migraciones, recrear solo API con f02 + handoff F03 +
api-compat F04, envfiles operativos F02/F03 e imagen revisada. No tocar datos/IdP/Bao.
Reemplazar su entrega limitada DESPUÉS del cierre/reinicio del consumidor previo;
su cierre puede revocar el token anterior. Verificar HTTPS/health y acceso real.

Preparar tmpfs separado del worker e emitir solo la identidad fija existente mediante
f04_runtime_host.py ensure/replace. No modificar AppRole/políticas. Un cierre normal
del consumidor revoca esa identidad; reemplazar antes de la siguiente batería.
No renovar el día ni reiniciar infraestructura.

## Fixtures y pruebas reales

seed.compose.yaml es QA de usuario, distinta del worker: añade TLS/OIDC fixture de
usuarios y directorio privado de resultados. No recibe día, bootstrap/migrator ni
admin SQL/S3. RAG_F04_QA_ROOT identifica un directorio nuevo 0700 propio de diego,
fuera del repositorio; registros 0600 solo con UUIDs/hashes sintéticos. No sobrescribir
runs anteriores ni sus originales.

El seed crea repos nuevos y originales HTTPS propios, repite uploads sin duplicar y
crea intenciones positivas explícitas para cuatro formatos. Mantiene originales
negativos sin ingesta indiscriminada. PDF malformado tiene primera página válida y
fallo en segunda, comprobado antes del alta. Conserva journal parcial y manifest final;
no contiene contraseñas/tokens/texto documental.

Completar con runtime limitado: S3/parser, offsets/páginas/hash/config, replay sin
duplicados, NEEDS_OCR/cifrado/fallo parcial, crash real después del commit antes de ack,
dependencia/reintento, parada/reinicio, baja/ACL/membresía durante procesamiento,
A→B→A y logs/temporales/permisos. Los controladores y sus resultados pasan por el PR.
No marcar T002/T003/T005 ni F04 completas por instalar imágenes o por checks offline.
