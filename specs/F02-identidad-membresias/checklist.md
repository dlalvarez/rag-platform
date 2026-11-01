# Checklist F02 — aceptación técnica delegada

## Puertas

- [x] F01 aceptada previamente; base y requisitos rectores identificados.
- [x] Plan y tareas propuestos sin modificar requisitos de la spec.
- [x] D-04 resuelta por Diego; ejecución spec/plan autorizada dentro del roadmap.
- [x] PR #19 integrado y comprobado; CI del commit de merge correcto.
- [x] Identidad, membresías y contexto implementados con migraciones y permisos mínimos.
- [x] Evidencia real V01..V07 y todos los AC cumplidos.
- [x] F00/F01 y CI sin regresión; revisión y postmerge registrados.

## Matriz de aceptación

| Validación | Requisitos | Criterios | Prueba requerida |
|---|---|---|---|
| V01 firma/OIDC | R01 | AC-03/04 | Firma, issuer/audience, tiempos, tipo de token, kid, rotación, TLS y fallo IdP |
| V02 identidad/membresías | R02/R04 | AC-01/03 | issuer+sub estable, roles distintos A/B, unicidad y ninguna autoasignación |
| V03 contexto/IDOR | R03 | AC-02/03 | Ruta/cabecera/claim ajenos denegados antes de resolver secretos o conectar tenant |
| V04 administración | R04/R05 | AC-01/03/04 | Matriz roles, bootstrap separado y último owner protegido concurrentemente |
| V05 estados/aislamiento | R02/R03 | AC-01/02/03 | A→B→A, usuario/membresía/tenant suspendidos y dos topologías reales |
| V06 auditoría | R05 | AC-04 | Captura logs/respuestas sin JWT ni identidad sensible; códigos cerrados |
| V07 reproducibilidad | R01..05 | AC-01..04 | Migración real, IdP real TLS, tests offline/CI, F00/F01 y fuentes exactas |

Los IDs R/AC se refieren a F02 en [spec](spec.md). Pruebas simuladas no acreditan
integración real, ni se presume ausencia de conexión tenant porque HTTP devolvió 403.


## Resultado final de los criterios

- [x] AC-F02-01: Alice owner A/reader B y vuelta A, misma y distintas instancias; Carol
  solo A, Dave sin membresías. Registro estable sin autoasignación y roles en control.
- [x] AC-F02-02: UUID/ruta/cabecera/claim/contexto ajenos no autorizan; denegaciones
  conservan contadores de secretos/intentos SQL/queries/S3 con pools fríos/calientes.
- [x] AC-F02-03: firma/audiencia/tipo/tiempos, caducidad real y suspensión/revocación
  denegadas; esquema incompatible sin fallback y dependencia de identidad responde 503.
- [x] AC-F02-04: captura de logs y respuestas sin JWT, credenciales, subjects o tracebacks;
  auditoría con códigos cerrados y UUID, sin contenido ni claims sensibles.
- [x] Migración control aditiva repetida en PostgreSQL; FKs/CHECK/unicidad/concurrencia;
  ninguna migración nueva de contenido tenant, grants mínimos y F01 conservada.
- [x] Manual de preparación, operación, custodia y reversión conservadora; límites claros.
- [x] 297 tests offline, Ruff/formato/SDD y regresiones reales F00/F01 correctas.
- [x] Revisión de seguridad/compatibilidad del mismo agente y CI/postmerge de PR #20..#25.
- [x] T007 documenta la aceptación técnica y guía siguiente; revisión/CI/postmerge de su
  PR se registra al integrar, sin atribuir aprobación independiente o humana nueva.

La evidencia histórica de cada entrega conserva sus pendientes de aquel momento.
Estado actual y matriz final: [acceptance.md](acceptance.md).
La aceptación técnica usa la delegación explícita de Diego para las actividades de F02.
No habilita F03, promoción a main/tag ni producción. La sesión diaria no se revoca al cerrar.
