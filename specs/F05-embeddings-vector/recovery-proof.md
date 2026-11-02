# Prueba real de recuperación F05 preparada

F05-R03/R05, AC-F05-01/03 parciales; no aceptación todavía.
Solo desarrollo, trabajador EMBED normal detenido y conservado. Código revisado,
CI del HEAD y postmerge antes de cualquier request o interrupción real.

Selecciona positive-txt explícito del manifest worker F04 conservado; atomic queda intacto.
Preflight de los cuatro documentos con tokenizador Qwen real: hasta64chunks,
cada entrada hasta512tokens y32768tokens totales. Si una cota falla, no se crea
ningún intent. No truncar, barrer historia ni sustituirlo por fake.
Antes de leer chunks, exige documento activo y permiso de ingesta. Usar
RAG_F04_QA_ROOT=/home/diego/proyectos/rag-platform-f04-worker-runs/15bbc3e906dd4cdbad151c9ab055d8d3.
El manifest API a75adb4c contiene positive dados de baja durante la aceptación F04;
no reutilizarlos ni restaurarlos. Conservar el journal fallido212416ed y crear otro.
Tras el gate, request idempotente por versión/space en cada base independiente.

La cola QA deriva de EmbeddingQueue y restringe adicionalmente tenant/doc/version.
Conserva runtime.scope de cuatro fixtures y credenciales existentes, sin migrador,
bootstrap, día, S3 ni grants nuevos. Solo encola el objetivo al ejecutar crash.
El trabajador es el código real con hook QA en límites ya previstos.

## Secuencia
Crear un journal nuevo0700 fuera del repo y conservarlo. Combinar F02 con
ops/f05/recovery-check.compose.yaml, manifest RAG_F04_QA_ROOT retenido y variable
RAG_F05_RECOVERY_QA_ROOT al journal nuevo. Cada invocación usa run --rm --no-deps
--pull never f05-recovery-check y entrega F05 válida/exclusiva. Scripts/src/modelo RO.
Reemplazar entrega únicamente tras cerrar proceso/lock libre, con día vigente,
sin auto-renovación ni impresión de archivos privados.

prepare comprueba presupuestos y solicita solo las cuatro versiones positivas.
Después ejecutar crash NOMBRE y resume NOMBRE para same-a, same-b, two-a, two-b,
uno a uno. crash debe terminar exactamente86 y dejar checkpoint; cualquier otro
resultado requiere diagnóstico, no reset ni repetición ciega.
same-a/two-a interrumpen después del primer lote confirmado; same-b/two-b después
de publicación tenant y antes del ack control. El hard exit cierra conexiones por
terminación real de proceso; no simula rollback ni commit distribuido.

Cada primera respuesta real tiene una espera QA35s, con lease15s y heartbeat5s.
Esto prueba contexto30s caducado y renovación real del lease; no es tiempo puro
del modelo ni benchmark de capacidad. Se exigen al menos7heartbeats exitosos antes
de interrumpir. No incluir textos/vectores en el journal.

resume espera/reclama tras caducidad real del lease, hasta25s después de cargar
modelo. Comprueba segundo intento, ledgers previos intactos, cobertura completa,
publicación/pointer/ancla original, consumo exacto precontado y llamadas de modelo
solo para lotes pendientes. Tras publicación-before-ack no debe inferir otra vez.
La cerca del intento viejo no puede renovar, fallar ni confirmar; el tercer claim
no existe. No prueba aún revocación real de membresía/ACL durante inferencia.

## Compatibilidad
El helper de consulta real admite más publicaciones posteriores: contrasta cada
hit contra las identidades publicadas del espacio y exige que atomic siga publicado,
sin asumir que sea el único documento del repositorio. No amplía permisos.
Las fuentes/modos quedan cerrados. El journal conserva evidencia agregada; no se
elimina corpus, imagen, contenedor histórico ni versiones al terminar.

El intento inicial sobre positive API pasó presupuestos1chunk/16tokens por fixture,
pero el control de ingesta rechazó las solicitudes. Diagnóstico con savepoints
revertidos confirmó ausencia de los cuatro intents; no se provocaron crashes.
Se corrigió la selección y se agregó rechazo de tombstone antes de leer/tokenizar.
El código de producción no se relajó. Diagnóstico CLI limitado a vocabulario cerrado
o SQLSTATE, sin cuerpos privados.
