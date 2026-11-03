# Corpus técnico F06 v1

Corpus sintético creado para evaluación, sin documentación privada ni promesas
sobre herramientas reales. Dieciséis manuales ficticios,40consultas:
20español/20inglés;16preguntas directas,8reformulaciones semánticas,
8comandos exactos,4ambiguas con dos fuentes y4negativas sin gold.
Hay32preguntas en lenguaje natural además de las8consultas técnicas literales.

SHA256 congelado antes de inferencia:
35976933e799d23ca87e4718dceedab0f8989b3204c881dc4972294d4b8b4bb7.
Una versión/chunk completo por documento con chunking512/64; comprobado offline.
No ajustar golds para mejorar resultados de un modelo. Cambios requieren nueva
versión y baseline, conservando el anterior y explicando el motivo.

Métrica document_recall_at_10: promedio de36consultas con gold no vacío;
las4negativas se informan aparte, sin contar como aciertos ni fingir abstención.
Un documento tiene exactamente un chunk, por lo que ambos golds coinciden.
Ambigüedad exige recuperar ambas fuentes, sin generar ni elegir una respuesta.
Reportar por idioma/tipo y baseline vectorial/híbrido; gate híbrido>=0.80.
Citas deben resolver100% de los resultados dentro del scope autorizado.
Latencias con nearest-rank p50/p95 y denominador/recursos/etapa explícitos.
No mide calidad generativa, producción, datasets privados o garantía general.

Corpus y evaluador revisados bajo delegación ADR0007; no se atribuye aprobación
personal nueva de Diego al contenido de las preguntas.
