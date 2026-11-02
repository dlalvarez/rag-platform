# Contrato F05 T002

R03/R05; apoyo AC01/03/04, sin acreditar aún SQL/índices/publicación.
Provider independiente del modelo; perfil inmutable con fingerprint de todos los
parámetros. Valida respuesta completa antes de persistir: dimensión/cantidad,
perfil incluso misma dimensión, finitos/float32/no booleanos/cero/norma y tokens.
Rechaza entradas o lotes excesivos y errores privados con códigos cerrados.
Prefijo admite salto de línea fijo para la instrucción Qwen, no otros controles.

Fixture SHA256 determinista offline identificada como fixture, no modelo real.
No red, pesos, API, secreto ni calidad semántica; no suplantar perfil Qwen.
Corpus ES/EN ficticio con gold previo a medición, no evaluación representativa F06.

Perfil aprobado en ADR0011: Qwen0.6B/1024/coseno; adaptador/pesos/benchmark siguen
en entrega separada T001. Este PR no cambia dependencias, runtime, DDL o datos.
