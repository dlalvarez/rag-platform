# 13 — Registro de decisiones abiertas y riesgos

## Decisiones confirmadas (ADRs vinculantes)

- ADR-0001: un PostgreSQL database por tenant + base control.
- ADR-0003: SDD, Codex, GitHub y aprobaciones por PR.
- ADR-0002: monolito modular, ratificado en PR #5.
- ADR-0006: main/develop y PRs; protecciones aplicadas, verificadas en F00.

- ADR-0004: OpenBao de desarrollo y bucket por tenant, aprobado por Diego en PR #8;
  custodia preparada fuera del host, bootstrap y root revocado acreditados en F01.
  El ADR histórico se conserva.
- ADR-0007/0010: revisión/integración delegada y continuidad del roadmap original.

## Decisión operacional ya ejecutada

- ADR-0005: VM Synology VMM con Ubuntu y Docker como host de desarrollo. F00 técnica fue aprobada y verificada posteriormente en PR #6/Issue #4, sin iniciar F01.

## Decisiones técnicas a confirmar antes de su fase (no bloquean la documentación)

| ID | Decisión | Límite temporal | Criterio de elección |
|---|---|---|---|
| D-01 | Nombre/branding y dominio | Antes de comercializar | Disponibilidad y marca |
| D-02 | F00 fija PG 17/pgvector 0.8.7, Python/uv y dependencias; F01 fijará nuevas bibliotecas compatibles | Antes de implementar F01 | Conservar pins y probar compatibilidad, sin upgrade de clúster |
| D-03 | OpenBao 2.7.2 dev aprobado/instalado, custodia gestor y copia fuera de línea confirmada por Diego; producción/HA sin decidir | Ratificar F01; custodiar antes de inicializar | Refs opacas, políticas, TLS y recuperación sin secretos en Git/control |
| D-04 | Keycloak solo dev aprobado por Diego en PR #19/ADR-0009; producción sin decidir | F02 dev; producción antes de promover | Seguridad, operación, coste |
| D-05 | pypdf/python-docx locales seleccionados dentro del adaptador previsto; [límites y alternativas](../specs/F04-ingesta-versionada/parsers.md) | F04, validar con corpus antes de cierre | Texto/tablas y resiliencia; sin OCR ni garantías de layout complejo |
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
| MinIO upstream archivado | Alta | Alta | Mantener receta F00 solo con datos sintéticos; revisar mantenimiento/proveedor antes de promover, sin cambio unilateral |
| Pérdida de unseal en un único host/operador | Media | Alta | Custodia protegida fuera del host antes de inicializar; no prometer HA/backup externo por tener Raft |

## Gestión de cambios

Abrir ADR para decisiones transversales; incluir alternativas, costes, datos afectados, seguridad, estrategia de migración/rollback y pruebas. No asumir que cambiar modelo de tenancy, embeddings o proveedor de almacenamiento es sencillo.
