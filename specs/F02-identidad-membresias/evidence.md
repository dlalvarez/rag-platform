# Evidencia F02

Estado: T001 implementada y comprobada; F02 no aceptada.
Las anotaciones de planificación siguientes conservan el estado histórico.

Base inspeccionada en ragdev01: develop@f66a38c8dbfe6d9244eef3cf390ed16f37998b41,
checkout limpio. Lectura de constitución, arquitectura, tenancy, modelo de datos,
contratos API, NFR, roadmap, amenazas, gobierno y spec F02.
F01 cerrada en PR #15; autorización diaria de pruebas integrada en PR #18.
Sesión verificada ACTIVE con vencimiento original 2026-11-01T21:34:19-05:00;
esa lectura no demuestra validez al ejecutar futuras pruebas.

## Resultados pendientes

V01..V07 pendientes. No se instaló/arrancó IdP, no migraciones, usuarios/membresías
o endpoints nuevos en esta entrega. No se ejecutaron pruebas de funcionalidad F02.
La validación documental y CI de este PR se registrarán en su conversación;
no equivalen a aceptación técnica de la fase.

## Registro por entrega

Anotar tarea/requisitos/AC, commit y hashes, fecha/entorno/comando, resultado observado,
negativos, cambios de esquema/config/dependencias, recursos conservados, límites
y resultado postmerge. Salidas saneadas; no bearer, claves, passwords ni claims
personales. Un fallo mantiene abierto el criterio afectado.

## Ratificación

Diego respondió «Keycloak solo para desarrollo (recomendado)» a la decisión
concreta de D-04 presentada en PR #19. Proveedor de producción no elegido.
Ejecución de F02 dentro del roadmap autorizada; revisión/merge delegados ADR-0007.
Esta ratificación no acredita implementación ni cierre de fase.

## T001 — entorno IdP real en ragdev01

Base 9d37b0a7790e1cfb40d9986b78d8229ee4db9d74; rama feat/F02-T001-oidc-dev.
F02-R01, preparación de AC-F02-03/04; V01/V07 parciales.
Keycloak 26.8.1 según release oficial; índice OCI por digest en Dockerfile.
Imagen local ejecutada:
sha256:4907e364c09d86badd8c3cc95655822382beb9313575689638561f0f68e029d0.
PostgreSQL independiente, rol f02_idp con flags de superusuario/CREATEDB/
CREATEROLE/REPLICATION/BYPASSRLS desactivados, comprobados en pg_roles.
No usuarios, administrador inicial, clientes OAuth ni membresías creados.

Comandos en servidor: f02_host.py prepare/config/build/up/check;
pytest -q, Ruff check/format y scripts/check_docs.py.
PASS T001: TLS real, discovery/JWKS, issuer exacto y claves públicas de firma.
PASS T001: conexión sin CA privada rechazada; red interna, sin puertos publicados.
221 tests correctos, 71 archivos formateados, sin errores Ruff/SDD.
11 tests nuevos: preservación de datos/enlaces, metadata no confiable,
claves privadas/tipos/límites, CA y redirecciones.
Regresión real F00 API/SQL/vector/S3 correcta; daily verify canary correcto,
autorización diaria conservada sin pedir password o ampliar vencimiento.

Muestreo posterior al arranque: IdP 442.5 MiB/1536 MiB y 0.23% CPU;
PostgreSQL 44.54 MiB/512 MiB y 0% CPU; sin OOM ni salidas.
Durante inicialización se observó IdP 390.6 MiB y 78.10% CPU (cota 0.75 CPU).
La primera comprobación completó dentro de su espera máxima de 180 segundos;
no se midió p95 ni capacidad bajo carga. F00/F01 no se detuvieron.
Sin migración de rag_control o bases tenant. Sin backup/restore acreditado.

Pendientes: access token firmado/emisión/rotación T002, usuarios/membresías T003,
administración T004, contexto/API T005 y aceptación integral T006/T007.
La evidencia de T001 no cierra AC-F02 ni autoriza F03.
Fuentes exactas: [manifiesto](../../docs/evidence/f02-t001-source-sha256.txt).
Manual: [IdP dev](../../ops/f02/README.md).
CI, revisión y comprobación postmerge se registran en la conversación del PR.
