# Evidencia F07

F06 aceptada en PR83, merge80b29f2adfae2f985a6414a236dc19807e8d8050,
cuatro checks HEAD y tres postmerge correctos. Revisión propia delegada ADR0007.
Plan/tareas preparados antes de código. No implementación, modelo nuevo,
migración persistente o calidad F07 acreditados todavía.
D-07 propuesto para ensayo local/historial, pendiente de decisión expresa.
No interpretar aprobación anterior de Qwen embeddings como aprobación de generación.

## T002 — contrato y proveedor determinista offline

Nuevo perfil inmutable con artefacto/runtime/tokenizer/template, muestreo/seed/
límites y hash de política del servidor. Request acota pregunta/historial/
evidencia y evita mezclar tenant/space; la autorización sigue siendo del servicio,
no de estos dataclasses. Renderer separa política fija y datos JSON, preserva
Unicode válido y escapa delimitadores de chat sin cambiar la semántica JSON.

Respuesta estructurada: estado/answer/etiquetas conocidas de evidencia/uso.
Rechaza citas inventadas o duplicadas, falta de citas en respuesta, contradicción
sin dos fuentes, perfil/tokens incompatibles y texto no serializable.
Presupuesto reserva salida y no trunca pregunta; render UTF8<=128KiB.

Mock determinista solo para CI, respuestas predefinidas y contador sin payload.
Su tokenizer es sintético; abstención por defecto no acredita abstención semántica.
Separación estructural del prompt no prueba obediencia de un LLM ante inyección.
79pruebas offline PASS0.22s; sin sockets, modelo, SQL, credenciales o API.
Ruff/formato290/docs/diff correctos. No cambio del runtime previo; suite local
core1295PASS permanece como base y CI ejecutará1374. D07 sigue pendiente.

## T003 parcial — configuración privada y metadata

76pruebas offline PASS0.70s: límites, Unicode, perfil, conjuntos canónicos,
propiedad/roles por defecto, revisión CAS acotada y metadata aditiva. Comparación
DDL confirma todas las tablas F05 anteriores idénticas; FK solo locales y
auditoría sin payload privado. Ruff/formato correctos. No modelo, sockets, SQL
real, migración aplicada o nueva ruta. T003 sigue pendiente de CRUD/migración/
roles/compatibilidad y pruebas PostgreSQL. Ver assistant-design.md.
