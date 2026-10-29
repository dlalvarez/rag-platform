# 13 — Registro de decisiones abiertas y riesgos

## Decisiones confirmadas (ADRs vinculantes)

- ADR-0001: un PostgreSQL database por tenant + base control.
- ADR-0003: SDD, Codex, GitHub y aprobaciones por PR.

## Propuestas de ADR pendientes de ratificación

- ADR-0002: monolito modular + workers y proveedores desacoplados (propuesto F00).
- ADR-0004: secret manager y bucket por tenant (propuesto F01).

## Decisión operacional ya ejecutada

- ADR-0005: VM Synology VMM con Ubuntu y Docker como host de desarrollo. No supone que F00 del paquete haya terminado.

## Decisiones técnicas a confirmar antes de su fase (no bloquean la documentación)

| ID | Decisión | Límite temporal | Criterio de elección |
|---|---|---|---|
| D-01 | Nombre/branding y dominio | Antes de comercializar | Disponibilidad y marca |
| D-02 | Postgres/pgvector, Python y librerías versionadas | F00/F01 | Compatibilidad, seguridad y pruebas |
| D-03 | Secret manager para dev/prod | F01 | Referencias, rotación, mínimo privilegio |
| D-04 | IdP OIDC concreto | F02 | Seguridad, operación, coste |
| D-05 | Parser PDF/DOCX y límites | F04 | Calidad texto/tablas y resiliencia |
| D-06 | Modelo embedding inicial + dimensiones | F05 | Evaluación español/inglés, coste y pgvector |
| D-07 | Perfil LLM y política de retención chat | F07 | Privacidad, costo, groundedness |
| D-08 | UI framework y diseño visual | F08 | Simplicidad y soporte |
| D-09 | Adaptador Google Drive y permisos | F09 | Cambio/borrado seguro, cuotas |
| D-10 | Modelo comercial/planes, condiciones y datos | F11 | Validación de mercado/legal |

## Riesgos de proyecto

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Complejidad operativa de N bases y pools | Media | Alta | Provisionador, migrador, límites, observabilidad desde F01 |
| Backups/PITR de tenant en instancia compartida | Alta | Alta | Restore de prueba, perfil instancia dedicada para requisitos estrictos |
| Lectura cruzada por fallo de ACL/RAG | Media | Crítica | Gates negativos obligatorios automatizados |
| Corpus con PDFs escaneados/tablas | Alta | Media | Detección explícita y backlog de OCR; no prometer soporte pleno |
| Costos de embeddings/reindexación | Media | Alta | Hash, idempotencia, cuotas y medición |
| Calidad variable en español/términos técnicos | Media | Alta | Dataset evaluado, búsqueda híbrida, ajustes medidos |
| Proveedores LLM cambian términos/precios | Alta | Media | Adaptadores y versionado de perfiles |
| SDD se convierte en burocracia | Media | Media | Fases pequeñas, plantillas ligeras y gates basados en riesgo |

## Gestión de cambios

Abrir ADR para decisiones transversales; incluir alternativas, costes, datos afectados, seguridad, estrategia de migración/rollback y pruebas. No asumir que cambiar modelo de tenancy, embeddings o proveedor de almacenamiento es sencillo.
