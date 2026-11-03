# Aceptación F06 — expediente de cierre

Estado: pruebas técnicas completas. Aceptación propuesta, efectiva tras CI del
HEAD exacto, revisión delegada, integración en develop y comprobación postmerge.
F05 aceptada en PR74; continuidad ADR0010 y revisión propia ADR0007.
AC-F06-03 aclarado expresamente por Diego el 2026-11-03, sin migración.

## Criterios comprobados

| Criterio | Resultado | Evidencia |
|---|---|---|
| AC-F06-01 | Recall@10 híbrido 1.0 en ES/EN, cuatro fixtures; supera 0.80 | Corpus congelado y baseline-v1.json; 36 consultas con gold por fixture |
| AC-F06-02 | 1600 citas del baseline resuelven; identidad y permisos actuales comprobados en servicio real | SQL de citas b5dcd20e...; calidad ac2b8e17...; servicio 7e04eee3... |
| AC-F06-03 | Solo versión procesada vigente publicada/completa y autorizada; bajas, ACL y referencias falsas denegadas | Conjunto permitido común, negativos SQL y de servicio en ambas instancias |
| AC-F06-04 | FTS parametrizada acredita los 8 comandos técnicos en cada fixture, junto a recuperación semántica | 32 comprobaciones FTS reales y corpus de 40 consultas |

[Baseline íntegro](baseline-v1.json), [evidencia y diagnósticos](evidence.md) y
[manual reproducible](../../ops/f06/README.md). Corpus de 16 documentos, un chunk
por documento, 40 consultas: 20 ES y 20 EN. Incluye 32 preguntas naturales y
8 comandos; 4 ambiguas tienen dos golds y 4 negativas no tienen gold.
Hash 35976933e799d23ca87e4718dceedab0f8989b3204c881dc4972294d4b8b4bb7.
Golds congelados antes de inferencia, sin ajustarlos tras medir.

## Integración real y compatibilidad

Calidad Qwen/SQL: journal ac2b8e1743994b4c9bed1aa5a0573126,
exit0 en 361.21s, 44 operaciones reales y 2281 tokens de entrada.
Vectores solo en memoria antes de SQL; uso separado de ledgers sintéticos.
Rollback conserva historial, control, heads y conteos vector/publicación.

Servicio con identidad real: journal 7e04eee3dac24d269d825a0fb37bde66,
exit0 en 56.42s. Cuatro consultas híbridas con citas, regresión exacta F05
con 12 resultados también resueltos; 8 operaciones reales y 184 tokens.
Repos ajenos y citas de otro tenant/inexistentes denegados sin inferencia extra.
Sin nuevos documentos o jobs.

Regresión final: journal 4fb9bbd4bda24235bb401a7c753051a2,
exit0 en 37.58s sobre fuente 54b4c9684044fc179d7766158e11bd3ae507b31f.
OIDC, SQL/TLS/roles/CONNECT/SET ROLE, S3 propio/ajeno, originales HTTP/SHA
e historial F03 correctos en cuatro tenants y dos instancias.

Un intento anterior se lanzó antes del listener API. Otro reprodujo un cierre
de conexión S3 sin respuesta. PR82 añade un único reintento GET/HEAD, sin
reenviar escrituras/status/TLS/conexión, errores de log cerrados y sin redirects
fuera del endpoint aprobado. No se aceptó un error de red como AccessDenied.
Fallos y diagnóstico conservados; la regresión final usa el código corregido.

105 módulos importados desde fuente RO, hashes coincidentes en API/herramientas,
sin red/credenciales/Torch; SHA de manifiesto
95f988c4f4db53938f19ceb0f40fc4f6a358a55d5f006cfc09a20bda9732d511.
Dependencias e imágenes anteriores conservadas. Suite local final 1295 passed
en 91.31s, una advertencia heredada; CI de PR82 y postmerge correctos.
Logs comprobados sin marcadores documentales ni patrones Bearer ensayados;
cuatro controles positivos PostgreSQL (3+1). No es detector universal de secretos.
API de prueba cerrada limpiamente; locks F03/F04/F05 libres y ningún Qwen activo.

## Límites conservados

Servicios internos híbridos y citation_resolver; API F05 mantiene contrato y
búsqueda exacta. Sin nuevo endpoint público, asistente/chat o generación.
RRF k=60 y hasta 50 candidatos por modalidad; score de rangos, sin significado
de coseno o confianza de respuesta. FTS simple sin GIN persistente.
Sin migración F06: control0007 y cuatro tenants0006 conservados.

Offsets de caracteres Unicode del texto normalizado, no posiciones binarias.
Una referencia no concede acceso histórico a versiones reemplazadas o eliminadas.
Una cita válida acredita procedencia y permiso, no fundamentación de una respuesta LLM.

Ambos modos alcanzaron recall 1.0; el corpus no distingue mejoras de ranking
entre ellos ni acredita calidad sobre documentos privados. Las cuatro negativas
devolvieron resultados autorizados y se informan aparte; no hay abstención semántica.
Inferencia de 40 consultas: p50 2358.87 ms y p95 3361.46 ms. El baseline SQL incluye
construcción/validación/consulta del componente, no solo servidor ni HTTP.
Una pasada, con un máximo vectorial de 8053.46 ms, no establece SLA o escala.

Toda ejecución en ragdev01, sin GPU/VMM, renovación diaria automática, root/
políticas Bao, producción o borrado de imágenes/contenedores/documentos/journals.
No revisión independiente ni aprobación personal nueva del corpus atribuidas.
