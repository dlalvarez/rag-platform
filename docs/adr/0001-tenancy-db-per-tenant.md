# ADR 0001 — Aislamiento de datos mediante PostgreSQL por tenant

**Estado:** Aprobación arquitectónica del usuario recogida en conversación.

**Contexto:** se rechazó confiar en futura migración desde tablas compartidas y RLS.

**Decisión:** `rag_control` central y una BD PostgreSQL distinta por tenant. Roles, vectores, índices y almacenamiento separados; catálogo de ubicación para instancias compartidas o dedicadas.

**Alternativas descartadas:** tablas compartidas con `tenant_id`, esquema por tenant. Se consideran insuficientes frente a la prioridad explícita de aislamiento y alto riesgo de migración estructural futura.

**Consecuencias:** mayor costo de aprovisionar, migrar, monitorear y administrar conexiones. Múltiples bases en una instancia aún comparten recursos y WAL/PITR.

**Validación:** pruebas DB A != DB B; roles sin CONNECT cruzado; contenido/vector/objeto no filtrado; test de resolución de instancia diferente.
