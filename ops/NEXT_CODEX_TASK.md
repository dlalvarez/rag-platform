# Tarea activa Codex — F05 planificación y decisión D-06

Continuidad AGENTS/ADR0010: no cerrar turno por tarea/PR/fase. Solo decisión real,
desvío/stop condition/bloqueo externo; toda ejecución manual en ragdev01, nunca Mac.
Worktree /home/diego/proyectos/rag-platform-f03-schema, docs/F05-plan-embedding-profile.

## Punto actual y primera actividad

F04 ACEPTADA, develop45726ec6477370a3fb466a12dd77488b3b1228e9, PR44 postmerge:
tres checks/46 tests específicos, checkouts limpios y69 módulos exactos. Baseline702
tests/regresiones F00..F03, R01..06/AC01..05 reales. No volver a pedir aprobación F04.

F05 original autoriza continuidad de plan/implementación dentro de specs, pero R01
exige perfil por ADR. ADR0011 PROPUESTO para D-06: E5-small local de desarrollo,
revisión614241f622f53c4eeff9890bdc4f31cfecc418b3,384/cosine/L2/512 con prefijos,
safetensors/pins y gate ES/EN/recursos; sin texto externo ni producción. Diego debe
decidir arquitectura antes de aprobar ADR/esquema dimensional. No inferir por silencio.
Propuesta alternativa BGE-M3 local1024/8192 o proveedor externo con análisis propio.

Primera actividad: completar PR documental plan F05/ADR propuesto, CI/revisión y pedir
D-06 concreta conforme F05-R01/P10/ADR0007; seguir trabajo independiente T002 provider/
fake/validación offline si no depende del modelo, sin resolver D-06 unilateralmente.
Plan/checklist tareas T001..T008 antes del código; no nuevos pesos/deps/servicios/
migraciones/índices por este PR. Datos/políticas/secretos intactos.
No mezclar modelos aunque misma dimensión; preservar ancla original F03 mientras
pointer publicado y binding por versión+space cambian atómicamente en F05.
No anticipar híbrida/FTS/F06, asistente/chat/F07, UI o nuevas fuentes.

## Estado y evidencia retenidos

API rag-f04-api:t006 activa/siete RO; worker t006 detenido exit0/cuatro RO.
Cuatro tenants READY f04_tenant_0003, cola f04_control_0006. Sin PUBLISHED aún.
T006 a75adb4c-445c-46d6-98ab-c558a8308112:20 originales/4repos,12READY/4NEEDS_OCR/
4TOMBSTONED, cuatro positivos luego tombstoned con chunks retenidos; ACL restaurada.
Env /tmp/f04-api-qa-a75adb4c445c46d698abc558a8308112.env, dir del mismo hex bajo
/home/diego/proyectos/rag-platform-f04-api-runs. No reseed/repetir verify ni tocar checkpoints.
T00515bbc3e9/cfe3... retenidos;52 originales/historial/negativos y ACL/membresía restauradas.
F00 T007 UUID4b7e0b1d-7326-4c35-bbf8-5a7ccf5294ed tiene tabla/bucket/objeto retenidos.
Original f00_probe retirada por smoke clean histórico. Nada que purgar/restaurar.

## Acceso

Día hasta2026-11-02T06:38:16-05:00=11:38:16UTC. No renovar/exportar bearer/password/
root/unseal. Entregas app API/worker TTL1h separadas; ensure si caducó y replace después
de cierre normal, tras crash ensure conserva vigente. No emisores día en paralelo.
Host --f02-env /home/diego/proyectos/rag-platform/.env.f02. Venv externo f04-parser-venv,
PYTHONPATH=src. Logs brutos solo VM; PASS/códigos cerrados. Sin ejecución local.

Sin cambio de main/tag/prod/visibilidad, purge/downgrade ni nuevos permisos sin plan.
Mantener CI/revisión delegada honesta/PR/postmerge y toda evidencia. Solo parar por
decisión D-06 real u otro criterio definido; avanzar independiente mientras llega.
