# D-05 — selección técnica para F04

Resolución de implementación dentro de los adaptadores de extracción ya previstos:
pypdf para PDF con texto y python-docx para DOCX; TXT/Markdown mediante lectura UTF-8
y estructura local acotada. Selección realizada por Codex bajo ADR-0010, no atribuida
a una nueva aprobación de Diego. No cambia arquitectura, tenancy, contratos externos
ni el límite explícito de F04 sin OCR. Versiones exactas se fijan con lock y se validan
antes de integrar código, exclusivamente en ragdev01.

pypdf permite extracción por página y modo layout, pero no reconstruye con certeza
la semántica de tablas ni texto en imágenes; la extracción de un stream PDF puede
consumir mucha memoria. Por ello el límite de bytes de entrada no basta: proceso
hijo acotado, tiempo/memoria/salida limitados y corpus de regresión.
[Documentación primaria](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

python-docx permite iterar párrafos/tablas en orden documental. Conservar títulos y
celdas en bloques con procedencia; sin prometer paginación renderizada de Word.
[API primaria](https://python-docx.readthedocs.io/en/latest/api/document.html).
Sus licencias permiten este uso con sus avisos correspondientes:
[pypdf BSD de tres cláusulas](https://raw.githubusercontent.com/py-pdf/pypdf/main/LICENSE)
y [python-docx MIT](https://raw.githubusercontent.com/python-openxml/python-docx/master/LICENSE).
Revisar también licencias y pins transitivos al fijar dependencias.

Se consideró Docling para estructura/tablas de PDF. Su pipeline añade artefactos de
modelos y opciones de OCR/servicios que habría que deshabilitar y medir. No hace falta
para acreditar PDF con texto, DOCX/MD/TXT y NEEDS_OCR de esta fase. No se instala ni
descarga en esta entrega. [Opciones oficiales](https://docling-project.github.io/docling/usage/advanced_options/).
No afirmar comparaciones de rendimiento o calidad no medidas en ragdev01.

PDF vacío/sin texto útil se distingue del PDF corrupto/cifrado o presupuesto excedido:
NEEDS_OCR para el primero; códigos terminales saneados para los otros. No usar OCR
externo ni contenido inventado. PDF con páginas de imagen intercaladas debe reportar
páginas sin texto, sin afirmar extracción completa; el gate de calidad debe bloquear
un resultado que omita silenciosamente contenido. Fijar la política exacta con fixtures.

Límites iniciales y estrategia de aislamiento en [plan](plan.md), aún sin medición.
Si el corpus revela que esta selección no satisface el requisito de estructura, registrar
el hallazgo y preparar alternativa antes de ampliar dependencias o alcance. Cambiar
un parser conserva originales/versiones y requiere nueva versión de procesamiento;
no reescribir resultados previos ni afirmar compatibilidad de offsets entre parsers.

Pins verificados en T004: pypdf 6.21.4, python-docx 1.2.0, lxml 6.1.3 (BSD-3-Clause).
Metadatos de distribución y lock comprobados en ragdev01; versiones anteriores
conservadas. Límites/procedencia e integración del componente en [contrato](extraction.md)
y [evidencia](evidence.md). No se garantiza interpretar texto en imágenes ni detectar
todo escaneo que tenga texto residual; las páginas sin texto extraíble sí se bloquean.
