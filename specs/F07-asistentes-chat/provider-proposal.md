# F07: propuesta de modelo de respuesta y conservación del historial

Propuesta pendiente de decisión de Diego. No se ha descargado ni ejecutado este modelo.

F05 y F06 recuperan fragmentos. F07 debe redactar respuestas con esas fuentes y
conservar conversaciones privadas. D-07 del plan reserva la elección del modelo
y la política de historial a una decisión explícita.

Se propone probar Qwen3-1.7B, formato oficial GGUF Q8_0, mediante llama.cpp en
ragdev01. El modelo oficial es de generación de texto y tiene licencia Apache-2.0;
la documentación de llama.cpp contempla ejecución en CPU. Son datos de las
fuentes oficiales, no una medición en nuestra máquina:
[modelo Qwen](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF) y
[compilación CPU de llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).

Artefactos públicos comprobados el 2026-11-03, antes de cualquier descarga:

- Modelo: revisión 90862c4b9d2787eaed51d12237eafdfe7c5f6077.
- Archivo Qwen3-1.7B-Q8_0.gguf: 1.834.426.016 bytes (aprox. 1,83 GB).
- SHA256: 061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a.
- Runtime candidato llama.cpp: revisión 0f35d6d7b0f548993d4323eb1df8e7ca4cf039c5.

La autorización propuesta permite descargar esos artefactos públicos, construir
un contenedor aislado y medirlos con texto sintético. Presupuesto inicial:
1,5 CPU, 4 GiB de RAM, dos hilos, contexto máximo de 2048 tokens, salida máxima
de 256 tokens y una generación simultánea. Son límites de ensayo propuestos,
no requisitos de memoria o rendimiento ya demostrados. El primer ensayo se
hará con el trabajador de embeddings cerrado para no cargar ambos modelos a la vez.

No se contrataría una API de pago ni se enviarían textos a terceros. No se
cambiarían CPU/RAM de la VM ni se abrirían puertos públicos. El modelo de
embeddings actual y los documentos permanecerían conservados. Durante inferencia,
la red del ensayo estaría deshabilitada; los hashes se comprobarían antes de cargar.

El resultado debe acreditar respuestas con citas, abstención, contradicciones y
resistencia a instrucciones maliciosas en documentos sobre al menos 30 casos.
También se medirán memoria, velocidad y errores. Si no cumple los criterios, se
conservará el resultado y se planteará otra decisión; no se adoptará otro proveedor
ni se aumentarán recursos por iniciativa. La integración definitiva queda sujeta
al benchmark y a las puertas de F07.

Para el historial de desarrollo se propone guardar mensajes de usuario/asistente,
citas y uso en la base del tenant, con acceso del propietario de la conversación.
No guardar el contexto expandido o prompts privados en logs/control. No aplicar
borrado automático; cualquier eliminación seguirá el flujo explícito del proyecto.
No se pretende fijar todavía una política comercial de retención.

Alternativa: elegir un proveedor externo con presupuesto y autorización de envío
de contexto definidos antes de usarlo. Esa alternativa no está autorizada por
esta propuesta.
