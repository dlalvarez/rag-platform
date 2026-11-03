# Plan F07 — asistentes y conversaciones con evidencia

Alcance original autorizado por ADR0010. Dependencia F06 aceptada en PR83,
merge80b29f2adfae2f985a6414a236dc19807e8d8050, cuatro checks HEAD y tres
postmerge correctos. [Aceptación F06](https://github.com/dlalvarez/rag-platform/pull/83#issuecomment-6608799838).
D-07 sigue pendiente: propuesta concreta de ensayo local y retención preparada,
sin descargar/ejecutar otro modelo ni atribuir aprobación a Diego.

## Alcance y archivos previstos

Módulos assistants y conversations, interfaz sustituible de generación en providers,
adaptador/mock y pipeline sobre HybridService/citation_resolver F06.
Migraciones tenant nuevas y congeladas, pruebas unitarias/integración, perfil API
concreto en esta spec y manuales ops/f07. Todo se ejecuta en ragdev01.
Sin UI, billing, agentes con herramientas, nuevas fuentes o cambios de tenancy.

Tareas independientes de D-07: contratos tipados, mock determinista, políticas de
evidencia, diseño/esquema con rollback y pruebas negativas. No usar proveedor
real nuevo hasta su decisión y prueba, ni adoptar esquema persistente sin
revisión/compatibilidad y gates de operación correspondientes.

## Proveedor y límites

ChatModelProvider recibe política del servidor y evidencia tipada, además de
pregunta/historial acotados. Perfil inmutable: proveedor/modelo/revisión/hash,
tokenizer/template, contexto/salida/timeout, parámetros de muestreo y capacidades.
No endpoints, secretos o nombres de modelo libres enviados por cliente.
Proveedor mock offline no descarga ni abre sockets y no acredita calidad real.

Proveedor devuelve respuesta estructurada y uso real, con límites de texto/IDs.
Citas solo pueden referir a evidencia suministrada. Rechazar ID desconocido,
contenido no finito/inválido o salida fuera de límites sin guardar respuesta
exitosa. No exponer razonamiento interno o texto de errores del proveedor.
No solicitar ni aceptar herramientas/acciones externas del modelo.

D-07 propone ensayo público Qwen3-1.7B GGUF Q8_0/llama.cpp, con hashes/revisiones
fijados, CPU/RAM acotados y embeddings cerrados durante el primer ensayo.
No se presume capacidad/calidad ni se modifica la VM. Retención propuesta:
mensajes/citas/uso privados en tenant, sin borrado automático o contexto
expandido/prompt privado en control/logs. Pendiente de decisión expresa.

## Datos y permisos

assistant.assistants y repository_links dentro de cada base tenant; identidad
global por UUID lógico sin FK entre bases. Configuración acotada y perfil de
proveedor permitido por servidor, espacio embedding y política obligatoria.
CRUD de asistentes propios, roles tenant adecuados, denegar por defecto.
Enlaces de repositorio no conceden permiso: revalidar todas las ACL actuales
al usar/configurar un asistente. No permitir que una instrucción personalizada
desactive políticas obligatorias del servidor.

conversation.threads/messages/message_citations en tenant, FK locales coherentes
entre asistente/thread/mensaje/documento/versión/chunk/space.
Historial privado del propietario por defecto, incluso dentro del mismo tenant.
Conocer thread_id no permite acceder desde otro tenant o usuario.
No exponer metadatos físicos, refs de secretos o existencia de recurso ajeno.
Antes de reutilizar o mostrar una respuesta citada, revalidar sus fuentes; si
falta permiso o publicación actual, no reexponer ese contenido como evidencia
vigente. Conservar el registro almacenado bajo la política de retención.
Cambios de política y estado/versiones se comprueban al confirmar respuesta.

Migración aditiva y perfil de esquema explícito: no relajar heads para aceptar
cualquier versión. API F03..F06 compatible antes de adopción. Probar roles/TLS,
rollback/fallo/recovery/repetición en ambas topologías; conservar datos e imágenes.
No generalizar un token bootstrap al runtime ni crear políticas Bao por iniciativa.

## Pipeline y consistencia

1. Autenticar/autorizar tenant, asistente, thread propio y repositorios efectivos.
2. Recuperar con HybridService usando perfil/espacio y límites del servidor.
3. Construir evidencia con IDs/offsets y texto no confiable delimitado; presupuestar
   contexto/historial sin cortar una cita ni truncar silenciosamente la pregunta.
4. Abstenerse ante ausencia de evidencia; la evaluación F06 demuestra que ranking
   puede devolver fragmentos irrelevantes, por lo que un top-k no prueba suficiencia.
5. Ejecutar proveedor fuera de transacciones SQL; una generación acotada por turno.
6. Validar respuesta/citas/contradicciones y autorizar de nuevo contexto/repos/
   asistente/thread. Resolver cada cita con permiso y publicación vigentes.
7. Guardar mensaje final/citas/uso atómicamente en tenant y devolver no-store.

POST con idempotencia: huella por actor/thread/cuerpo/perfil, sin duplicar mensajes.
Replay no regenera ni evita permiso actual. Proteger concurrencia de turnos con
estado/CAS y leases acotados, sin mantener transacción mientras infiere.
No fingir commit entre modelo externo y DB: resultado perdido antes de persistir
no acredita exactamente-una-inferencia; marcar incertidumbre y evitar retry
automático de generación/duplicación silenciosa de coste.
Errores del proveedor no publican respuesta ni citas inventadas.
Uso y fallos mínimos, sin prompts privados en control o logs; no billing F11.

## Evaluación y puertas

Corpus técnico F06 más conjunto de respuestas esperadas versionado >=30casos,
con cubiertas, imposibles, ambiguas/contradictorias e inyección documental.
Mock CI prueba orquestación/negativos, no calidad de modelo.
Ensayo real opt-in después de decisión D-07 y perfil/artefactos verificados.

AC01 respuesta respaldada/citas auténticas; AC02 abstención ante fuera de corpus;
AC03 cero bypass ACL por asistente; AC04 historial aislado aunque conozcan UUID;
AC05 instrucciones documentales no alteran políticas ni causan exfiltración.
Citas válidas100%, cero fuga tenant/repo, ninguna respuesta exitosa con cita
inventada o fuente dada de baja. Registrar fallos/latencia/uso/recursos y límites.
Si falla calidad, analizar antes de adoptar otro modelo o aumentar recursos.

## Secuencia

T001 planificación/D-07. T002 contratos/mock/políticas offline.
T003 esquema/CRUD de asistentes y versiones compatibles.
T004 conversación/historial/idempotencia/pipeline y citas.
T005 HTTP opt-in y límites, sin cambiar F05.
T006 ensayo real y cuatro fixtures/regresiones/privacidad.
T007 expediente, CI/revisión/integración/postmerge y aceptación antes de F08.
