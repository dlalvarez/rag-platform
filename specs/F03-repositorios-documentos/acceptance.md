# Aceptación técnica F03 — repositorios, ACL y documentos privados

Implementación y criterios verificados en ragdev01 el 2026-11-01. La aceptación
delegada se hace efectiva al completar CI, revisión del mismo agente, merge y
postmerge del PR de cierre T007, conforme ADR-0007/0010. No es revisión independiente
ni una aprobación personal nueva de Diego. Sin promoción a main/tag o producción.

F02 aceptada en PR #26; planificación F03 en #27, bootstrap/lock en #28/#29,
esquema en #30, CRUD/ACL en #31, recepción en #32 y handoff/API/proxy en #33.
La API F03 ya está promovida en desarrollo desde #33, con postmerge real correcto
en be7643847f6e472ae9b1b5d3011d83d3f75b3260.
Este cierre añade pruebas/evidencia, sin cambios funcionales del runtime ni DDL.

## Requisitos y criterios

| Criterio | Resultado real | Trazabilidad |
|---|---|---|
| AC-F03-01 | Sin ACL no listar/cargar/descargar aun con IDs; tampoco por rol global/owner tenant. Roles y techo de membresía aplicados, último owner protegido. | R01/R02/R05; T004/T006/T007; V01/V05/V06 |
| AC-F03-02 | UUID repo/doc ajeno rechazado; app/readonly sin CONNECT/SET ROLE cruzado; S3 AccessDenied 403. A→B→A con IDs/versiones/originales propios en ambas topologías. | R01/R02/R05; T003/T006/T007; V02/V05 |
| AC-F03-03 | MIME/UTF-8/magic/tamaño/ZIP rechazados sin altas SQL ni objetos nuevos. Chunked real >10 MiB y DOCX estructural completo con expansión peligrosa denegados. Temporales cerrados. | R03/R04; T005/T006/T007; V03/V06 |
| AC-F03-04 | Replay estable; cuerpo distinto con igual clave 409. Dos POST simultáneos producen una fuente/documento/versión/recibo/auditoría. Caídas y SQL parcial recuperan los mismos IDs. | R03/R04; T003/T005/T006/T007; V04/V07 |

R01: CRUD validado dentro de la DB tenant, cursores ligados a actor/tenant/colección,
cambios auditados. Baja lógica con contenido probada: API pierde acceso pero conserva
documento, versión, fuente, recibo COMMITTED, objeto privado, ACL y auditoría.
R02: owner/admin/editor/reader por capacidad y techo de membresía, sin bypass de
operador o tenant owner. R03/R04: original privado validado y metadata RECEIVED,
sin publicar ni procesar. R05: proxy autorizado por repo/documento, rol readonly,
bytes/hash verificados antes de HTTP 200 y cabeceras seguras.

## Evidencia V01..V07

- V01: HTTPS CRUD/ACL con Alice/Bob/Carol/Dave; retirada y techo de ACL, último owner,
  ausencia de enumeración por rol. Observadores reales en cuatro fixtures:
  JWT/tenant/reader/cursor inválidos con cero lecturas de secretos, S3 o spool.
  La ACL necesita SQL tenant para comprobarse; las denegaciones de ACL/doc cruzado
  no abren S3 ni spool, también con pool caliente. Positivos instrumentados prueban
  que los contadores sí detectan acceso.
- V02: SQL app/readonly propios con TLS, base/rol correctos y flags privilegiados
  false; CONNECT cruzado denegado por causa exacta, SET ROLE 42501 en instancia
  compartida y S3 cruzado AccessDenied 403. Ambas direcciones en las dos topologías.
- V03: cuatro formatos válidos; tamaño/hash de bytes reales; inválidos y límite
  comparados contra filas y objetos previos. ZIP bomb con partes DOCX válidas:
  rechazo antes del diario/S3. No confiar en Content-Length. Dos cargas y dos
  descargas máximas, sin cola ilimitada ni buffer completo de aplicación.
- V04: dos procesos y fencing reales en T005; muerte real tras PUT y COMMIT; rollback
  SQL real y recuperación. Dos solicitudes HTTPS simultáneas por fixture en T007,
  con SQL/auditoría únicos; replay y conflictos verificados.
- V05: reader descarga TXT/MD/PDF/DOCX originales por HTTPS, SHA/bytes y longitud
  correctos, attachment/no-store/nosniff y filename* UTF-8; anónimo/ACL/cruces denegados.
  El readonly no recibe SELECT de ops. Corrupción/truncado, pérdida de permiso,
  deadline y desconexión cubiertos offline con el adaptador real.
- V06: API con siete bind mounts read-only, sin día/root/migrator/IAM admin/secretos IdP.
  AppRole exacto, refs versionadas, ausencia/revocación con pool caliente sin fallback;
  reemplazo revoca identidad anterior y recupera sin contraseña. Inspección interna
  de logs sin JWT, credenciales, subjects, token, referencias físicas ni contenido.
  /tmp 0700, 64 MiB y cero temporales abiertos al terminar.
- V07: 562 tests offline y controles estáticos/documentales correctos. Regresiones
  reales F00 gates, F01 CLI diaria y F02 aislamiento/OIDC en ambas topologías.
  F03 T003 repetida con documentos presentes: DDL histórico fresco revertido,
  constraints/grants, FAILED sin versión falsa, recuperación y lock real correctos.
  Catálogo/identidades ajenos conservados en las baterías F03.

Las fixtures SAME_A/SAME_B usan instancia compartida; TWO_A/TWO_B usan dos instancias.
Todos los datos son sintéticos. Herramientas serializadas por el presupuesto de
ragdev01; no servicios pagados, claves externas ni ejecución manual fuera del servidor.
[Detalle cronológico, fallos y resultados](evidence.md).

## Reproducibilidad y recursos conservados

- scripts/f03_http_check.py: HTTPS integrado, negativos, invariancia de objetos/filas
  y A→B→A sobre api; admite solo api o candidato efímero como destino de prueba.
- scripts/f03_observer_check.py: OIDC/SQL/S3 reales con observadores en proceso aparte;
  sin endpoint de debug en la API y sin alterar su identidad operativa.
- scripts/f03_provider_check.py: privilegios/cruces y baja lógica con contenido.
- scripts/f03_acceptance_check.py: concurrencia HTTP y ZIP expansivo.
- scripts/f03_schema_check.py y scripts/f03_log_check.py: esquema y logs/temporales.

Usar las herramientas construidas desde el checkout y la sesión diaria vigente;
composición ops/f02/compose.yaml + ops/f03/handoff.compose.yaml, .env.f02 operativo y
.env.f03 local. Reconstruir application-issue para actualizar también isolation-check
(rag-f03-tools:t006). Ejecutar scripts de red dentro de isolation-check; log_check
es de host. Ver [manual HTTP/handoff](api.md).

Artefactos públicos: repositories-fixture.json y conditional-fixture.json mantienen
semillas; http-fixture.json conserva 16 documentos de formatos; http-race-fixture.json
cuatro recepciones concurrentes y lifecycle-fixture.json cuatro repos DELETED con
contenido intacto. receipt-fixture.json identifica la batería T005. Los intentos y
probes válidos anteriores también se conservan; no afirmar limpieza física.
La regresión CLI F01 crea sus fixtures sintéticas propias y las retiene.

## Límites vigentes

PDF solo tiene validación estructural de entrada; la extracción pertenece a F04.
El SDK MinIO está fijado y su extensión privada condicional exige repetir pruebas
al actualizarlo. Intentos inciertos y colisiones conservan cuota y reserva durable;
no hay adopción de recurso ajeno, purge o restauración silenciosa.
El bearer de runtime dura como máximo una hora; el agente emite reemplazos con el
día vigente de 24 h, que la API nunca recibe ni renueva.

Este ambiente acredita desarrollo, no HA, backup/restore de producción o beta comercial.
F04 mantiene su alcance original y comienza tras el cierre formal de esta entrega;
las decisiones de arquitectura reservadas se presentan al responsable antes del código
que dependa de ellas. No detenerse por el mero cierre de este PR.
