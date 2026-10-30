# Evidencia F01 — T001 parcial

**Estado:** planificación ratificada en PR #8; T001 en curso con V01/V03 parciales.
Ningún AC-F01-01..07 ni tarea T001..T007 se declara completado.
[Runbook](../../ops/f01/README.md). Log actual:
[validación T001](../../docs/evidence/f01-t001-2026-10-30.txt).

Resultados T001 en ragdev01: migración control real repetida con PostgreSQL/TLS y
migrador no-superuser; constraints y rechazos de contraseña/CA/TLS comprobados.
Adaptador OpenBao con referencias UUID/versiones, CAS y errores saneados probado offline.
OpenBao arrancado con TLS, sellado, initialized=false: aún no hay claves de desbloqueo.
Bootstrap humano, root revocado real, restart/unseal y token caducado real pendientes.
Las notas siguientes describen preparación histórica del PR #8, no el estado runtime actual.

Base revisada: develop@85cd39f401b48e312c1e4fd61906543a4ff588fe; PR #6 integrado,
Issue #4 cerrado. Trabajo documental en ragdev01, rama docs/F01-planning.
Fecha de revisión: 2026-10-30. [Issue F01 #7](https://github.com/dlalvarez/rag-platform/issues/7).

| Criterio | Prueba prevista | Resultado | Evidencia técnica |
|---|---|---|---|
| AC-F01-01 | V01 catálogo, migraciones y tres BD | Pendiente | — |
| AC-F01-02 | V02 SQL cruzado/privilegios | Pendiente | — |
| AC-F01-03 | V04 S3 cruzado | Pendiente | — |
| AC-F01-04 | V05 idempotencia/concurrencia | Pendiente | — |
| AC-F01-05 | V05 fallo/reintento/compensación segura | Pendiente | — |
| AC-F01-06 | V03/V06 refs y pools en dos instancias | Pendiente | — |
| AC-F01-07 | V07 locks/versionado/error de migración | Pendiente | — |

## Hechos de preparación

Leídos constitución, arquitectura, tenancy, modelo de datos, operación, NFR, roadmap,
gobierno, ADRs aplicables y documentos F01 originales. Requisitos/AC originales se
mantienen; el plan desarrolla su ejecución, no crea un roadmap.

Diego prefirió proponer OpenBao; su instalación/ratificación no está aprobada por esa
preferencia. Consulta real desde ragdev01:
docker buildx imagetools inspect ghcr.io/openbao/openbao:2.7.2 --format '{{json .Manifest.Digest}}'
→ sha256:5046911075e137e154ce49ab051502f4ec7cf367d484ae4a4dce665d9b90561f, salida 0.
Esto verifica el manifiesto, no el arranque, cifrado ni policies. No se descargaron capas
de OpenBao ni se inició el servicio o generaron sus credenciales.

Los tres servicios F00 se observaron saludables al comenzar. En este PR no se crean
tenants, BD, roles, buckets, certificados ni políticas, ni se cambian servicios.

## Decisión de custodia registrada el 2026-10-30

Diego respondió «Ok, estoy deacuerdo con tu propuesta» a la recomendación de Shamir
1/1 con clave en gestor de contraseñas y copia fuera de línea, ambas fuera de
ragdev01. Se registra aprobación del esquema, no prueba de que las copias existan
ni de recuperación. La preparación de destinos, inicialización, generación/entrega
de claves, backup Raft y restauración siguen pendientes. No se generan secretos ni
se ejecutan servicios como parte de este cambio documental.

## Cómo completar la evidencia técnica

Por prueba: requisito → AC → tarea → V-ID → ruta/test real, commit, ambiente/fecha,
versiones, comando exacto, código de salida, esperado/obtenido y log saneado.
Incluir ambas direcciones SQL/S3, los dos perfiles de instancias, recursos/ownership,
locks, errores/reintentos y regresión. Registrar pruebas omitidas y motivo sin
sustituir integración real por mocks.

No incluir unseal, passwords, tokens, SecretID, DSN, respuestas de bootstrap ni URLs
firmadas. Revisor, aprobación de merge, estado postmerge y cierre: pendientes.

Se inspeccionaron firmas del módulo minio.minioadmin.MinioAdmin ya instalado en
minio==7.2.20: user_add, policy_add y attach_policy disponibles. No hubo llamadas
a la API administrativa; compatibilidad con el servicio y aislamiento siguen pendientes.

## Validación documental ejecutada

Validador SDD: salida 0. Conservadas exactamente las líneas originales de requisitos/AC F00 y F01; cubiertos R01..07, AC01..07, T001..007 y V01..07. Constitución/roadmap/ADR-0001 y hashes de fuentes F00 sin cambios. Tres servicios F00 observados saludables.
[Log documental](../../docs/evidence/f01-planning-2026-10-30.txt). Ninguna prueba técnica F01 se ejecutó; CI del PR documental se consulta por separado.
