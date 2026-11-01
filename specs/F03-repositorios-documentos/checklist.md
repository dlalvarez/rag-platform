# Checklist F03

- [x] F02 aceptada técnicamente y postmerge verificado en PR #26.
- [x] Continuidad del roadmap original autorizada expresamente por Diego (ADR-0010).
- [x] T001 integrado con CI/revisión/postmerge, sin alterar requisitos/roadmap.
- [ ] T002..T006 implementadas, permisos mínimos y servicios/datos previos conservados.
- [ ] AC y V reales acreditados, regresión F00/F01/F02, CI y revisión/postmerge correctos.

| Validación | Requisitos | Criterios | Evidencia exigida |
|---|---|---|---|
| V01 ACL | R01/R02/R05 | AC-01 | Sin ACL no listar/cargar/descargar aun con IDs; matriz roles/capacidades |
| V02 tenant/objetos | R01/R02/R05 | AC-02 | Cruces API/SQL/S3 denegados en ambas topologías y permisos propios correctos |
| V03 archivo | R03/R04 | AC-03 | MIME/tamaño/hash/streaming, rechazo real, sin huérfano persistente |
| V04 idempotencia | R03/R04 | AC-04 | Mismo key/contenido no duplica; distinto conflicto; concurrencia/fallo/reintento |
| V05 original | R05 | AC-01/02 | Proxy autorizado, bytes/hash y cabeceras correctos; anónimo/cruces denegados |
| V06 secretos/auditoría | R01..05 | AC-01..04 | App sin infra/migrator; denegación previa; logs/respuestas sin secretos/JWT |
| V07 reproducibilidad | R01..05 | AC-01..04 | Migraciones reales/repetidas, hashes, CI y regresiones F00/F01/F02 |

Los documentos o mocks no acreditan integración real; un AC esencial pendiente bloquea cierre.

## Entrega de componente T005

- [x] T004 integrada en PR #31 con CI/revisión/postmerge.
- [x] Validación y secretos mínimos: 512 tests offline correctos.
- [x] Recepción real/idempotencia/fallos/concurrencia/cuotas en cuatro fixtures.
- [x] Objetos y reservas conservados, colisión ajena sin adopción/borrado.
- [x] CI/revisión/integración/postmerge de T005 en PR #32.
- [ ] T002 handoff/runtime, T006 API/proxy y aceptación final T007.

T005 marcada como componente verificado; no equivale a aceptar AC-F03 por HTTP.


## Entrega T002/T006

- [x] Identidad limitada por tmpfs, consumidor único, reemplazo y revocación reales.
- [x] Candidato HTTPS sin infra/admin/puertos; límite API y tmpfs comprobados.
- [x] Dos baterías completas: CRUD/ACL, cuatro formatos, idempotencia/proxy y negativas.
- [x] 562 tests offline; temporales cerrados y logs sin token/JWT/contenido/trazas.
- [ ] CI/revisión/integración y promoción controlada al servicio API existente.
- [ ] T007: aceptación final, observadores y regresiones sobre el servicio promovido.
