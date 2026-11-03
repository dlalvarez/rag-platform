# Continuidad — F07 en implementación

F05 aceptada PR74. F06 aceptada PR83, merge80b29f2adfae2f985a6414a236dc19807e8d8050,
cuatro checks HEAD y tres postmerge correctos, comentario6608799838.
Aclaración AC03 aprobada por Diego: solo versiones publicadas, completas y
autorizadas; RECEIVED del original no habilita versiones pendientes/incompletas.

F07 plan PR84 merge53eabb41be8235a4790ddd09f1449ca3c4f6a640, postmerge verde.
T002 PR85 mergee5d19795515cd350659967d5943467eddb94c58d, cuatro checks HEAD y
tres postmerge correctos, comentario6609674760. Contratos generativos/mock,
79pruebas offline; no equivalen a calidad semántica de un LLM real.

T003 parcial: contrato privado de asistentes y metadata aditiva candidata,
76pruebas offline. No rutas, migración Alembic, perfil activado ni adopción
persistente. Ver assistant-design.md. Seguir con CRUD, migraciones, compatibilidad,
roles y pruebas reales; no declarar T003 completa por crear metadata.
El contexto reader usa readonly: resolver escritura limitada de chat sin
ampliar permisos documentales ni cambiar credenciales silenciosamente.

## Decisión D-07 pendiente

Ensayo Qwen3-1.7B GGUF Q8_0/llama.cpp local y retención de historial privado por
tenant/propietario sin borrado automático. Ver provider-proposal.md para hashes,
revisiones, límites y alternativas. No descargar ni ejecutar hasta respuesta
expresa. La aprobación anterior de Qwen embeddings no autoriza generación.
Continuar trabajo independiente mientras exista; no parar por trámite.

## Entorno y conservación

Operativo develop80b29f2 al último cierre; fuente F06 corregida conservada.
API rag-f06-api-source-t010 cerrada limpiamente, consumidoresF03/F04/F05 con
locks libres y sin Qwen activo. Verificar estado antes de reutilizar entrega.
No ejecutar F05 adoption de nuevo: tablas ya contienen datos.
Día habilitado por Diego válido hasta2026-11-04T08:51:32-05:00; no renovar solo.

Regresión final real4fb9bbd4bda24235bb401a7c753051a2 PASS37.58s cuatro fixtures,
OIDC/SQL/TLS/roles/S3/privacidad e históricos. F06 baseline/corpus y limitaciones
en evidencia de fase. Preservar documentos, originales, espacios, imágenes,
contenedores y journals. Sin root/Bao/políticas, main/tag/producción/visibilidad/purgas.
Todo código/dependencias/servicios se ejecuta en ragdev01. Revisión propia
ADR0007; continuidad ADR0010. No agentes salvo instrucción expresa.
