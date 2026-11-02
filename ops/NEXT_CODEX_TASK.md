# Continuidad F05 — Qwen real medido, seguir T003

D-06 Qwen aprobado por Diego. PR45/46 integrados en develop9284e56, CI/postmerge.
T001 adaptador Qwen local CPU/1024/coseno/L2 y primera medición en
feat/F05-T001-qwen-local. Terminar CI/revisión/merge/postmerge, seguir T003
esquemas/índices por space sin modificar migraciones históricas F01..F04.
No cerrar turno al integrar PR, conservar todos los datos y fixtures.

Leer ADR0011, qwen-local.md y evidencia: corpus ficticio no calidad F06.
Recall@3=1.0 ES/EN, p50=2.154s/p95=3.95s, picoRSS3796.6MiB en2vCPU;
sin carga concurrente ni SQL/ANN/ACL en este benchmark. No cambiar4vCPU aún.
Pesos y entorno separados, rutas públicas en manual; no red durante inferencia.

Sesión diaria anterior venció11:38:16UTC; no renovar/exportar bearer/root/unseal.
Preparar T003 offline y pedir daily start solo al necesitar ensayos reales y
sin trabajo independiente. F04 API t006/worker t006 detenido; fixtures conservadas.
Sin main/prod/visibilidad/purge/nuevos tenants. Mantener AGENTS/ADR0010.
