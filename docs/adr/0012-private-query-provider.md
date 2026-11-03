# ADR 0012 — Proveedor privado de consultas en el trabajador Qwen

**Estado:** aprobado por Diego el 2026-11-02: «Sí, usar la conexión privada propuesta».
Decisión solicitada con sus efectos: una copia del modelo, conexión dentro de ragdev01,
sin puerto público ni textos enviados a terceros, CPU compartida con indexación,
error temporal si está ocupado y reautorización antes de devolver fragmentos.
Solo desarrollo; no cambia documentos, bases ni producción. Implementación pendiente.
Mantiene ADR0011 y el contrato HTTP de fragmentos ya aprobado.

## Decisión
La API obtiene el embedding de consulta del mismo proceso que ejecuta EMBED con Qwen.
No carga Torch, pesos ni otro modelo en la API. El proveedor se comunica por socket
Unix privado, montado solo en API (directorio RO) y trabajador (RW). Directorio0700
y socket0600 del UID de ejecución; sin puerto TCP, bearer ni credenciales SQL en el
mensaje. El trabajador conserva su entrega temporal y scope de cuatro fixtures.

Mensaje acotado JSON con versión, operación count/embed, contexto firmado, UUID de
repositorios/espacio y consulta. Contexto interno no aparece en HTTP, logs o repr.
Ningún mensaje puede elegir BD, tabla, endpoint, modelo, dimensión ni secreto.
Cada llamada renueva la autorización desde la autoridad de la API antes de enviar;
el trabajador verifica firma, vigencia, membresía, catálogo, todas las ACL y perfil.
Cuenta tokens incluyendo instrucción/especiales, sin truncar. Reautoriza después
del cálculo antes de devolver vector; la API vuelve a autorizar y recuperar contenido.

Una exclusión en el proceso protege tokenizador/modelo entre consultas e indexación.
La indexación tiene prioridad al esperar; mantiene heartbeat sin transacción tenant
durante la espera/inferencia. Una consulta espera como máximo2s por el modelo ocupado.
Hasta dos handlers y backlog1; no cola sin límite. Mensajes hasta64KiB, lectura2s,
cliente count5s/embed30s. Saturación429 o indisponibilidad503, errores cerrados.
No reintentar consultas automáticamente ni prometer latencia. Una inferencia ya
iniciada puede terminar después de que el cliente venza; su salida se descarta.

## Operación y reversión
Opt-in explícito, apagado por defecto. Comprobar esquemas/modelo/entrega antes de
aceptar solicitudes. El cierre deja de aceptar, termina handlers y cierra runtime;
no renueva día ni bearer. El socket efímero solo se retira si pertenece al proceso
o se verifica como socket privado inactivo con consumidor exclusivo. Nunca borrar
un archivo arbitrario o desplazar otro listener.

Reutilizar límites1.5CPU/6GiB y una sola copia del modelo por VM. Conservar imágenes,
contenedores, originales y journals; no cambiar servicios de datos ni políticas.
Desactivar la ruta/flag y detener el proceso permite volver al runtime compatible
anterior sin DDL/downgrade. No hacer fallback administrativo/comercial al fallar.

## Evidencia requerida
Pruebas offline de firma/UUID/perfil/límites, revocación, framing incompleto, timeout,
concurrencia/ocupación, prioridad y cierre privado; no descargar pesos en CI.
Prueba opt-in real Qwen por este transporte, aislamiento cuatro fixtures/ambas
topologías, originales y regresiones, CI/revisión propia/merge/postmerge.
Esta decisión no acredita ejecución, calidad, capacidad bajo concurrencia ni F05.
