# Continuidad F05 — Qwen aprobado y T002

D-06: Diego eligió «ok, adoptemos qwen». PR45 integrado develop58e4a40 con CI y
postmerge correctos. Qwen0.6B/1024/coseno/L2, revisión fijada ADR0011; no volver
a preguntar modelo ni confundir selección con benchmark. 2vCPU siguen intactas.

T002 contrato/fake/corpus congelado en feat/F05-T002-provider-contract. Completar
CI/revisión/merge/postmerge y continuar T001 adaptador local/benchmark, luego T003
esquemas preservando F04. Pesos10 archivos públicos verificados en
/srv/rag-data/rag-platform/models/qwen3-embedding-0.6b/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3.
Inferencia separada /home/diego/proyectos/rag-platform-f05-inference-venv, torchCPU
2.7.1/transformers4.51.3/safetensors0.5.3; freeze completo /tmp/f05-inference-installed.txt.
No tocar lock/runtime existentes ni descargar en inferencia. Corpus ficticio no F06.

Sesión diaria anterior venció11:38:16UTC; no renovarla/exportar bearer/root/unseal.
Seguir modelo/offline sin Bao; pedir acción solo al necesitar live y sin trabajo
independiente. F04 aceptada PR44, API t006/worker t006 detenido, fixtures conservadas.
Sin main/prod/visibilidad/purge/nuevos tenants. AGENTS/ADR0010: continuar entre PR/fases.
