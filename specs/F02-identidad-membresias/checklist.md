# Checklist F02

## Puertas

- [x] F01 aceptada previamente; base y requisitos rectores identificados.
- [x] Plan y tareas propuestos sin modificar requisitos de la spec.
- [ ] D-04 resuelta y spec/plan ratificados para implementación.
- [ ] PR de planificación revisado y CI correcto.
- [ ] Identidad, membresías y contexto implementados con migraciones y permisos mínimos.
- [ ] Evidencia real V01..V07 y todos los AC cumplidos.
- [ ] F00/F01 y CI sin regresión; revisión y postmerge registrados.

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
