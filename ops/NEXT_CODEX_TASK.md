# Continuidad — cierre de F05

Operativo develop31a1eebc935e57a5b51b6e9b46d6802001170a06 (PR73),
cuatro checks HEAD/tres postmerge correctos. Worktree docs/F05-T008-acceptance.
F05: pruebas técnicas completas; falta CI/revisión/merge/postmerge del expediente.
No declarar aceptada ni implementar F06 antes de completar esas puertas.

## Evidencia final

- Corpus cefed930e3444ddda29e581d61ceaec9:4documentos públicos persistidos,
  11250bytes/14chunks/4lotes cada uno, originales HTTP/SHA verificados4/4.
- Recuperación df669c4900ac4727be6e0612fef8fd13:4SUCCEEDED intento2,
  14vectores/4ledgers/1publicación por documento; inferencias al retomar3/0/3/0.
  Cortes BATCH y RESULT, fences/heartbeat/usage/originales conservados.
- Regresión f9b70369f2cb41d9aaa58d69407e6df3:exit0/35.58s,
  cuatro tenants/dos instancias, OIDC/SQL/TLS/roles/S3/privacidad/históricosPASS.
  Intento aa8183859536407388a7cf6c1db9018c falló two-a/S3 ProtocolError;
  causa desconocida, repetición sin modelo activo pasó sin relajar controles.
- Logs:4controles positivos PostgreSQL(3+1),0canary privado/0texto multilote/
  0patrones Bearer comprobados. Corpus/recuperación/API también sin marcadores.
- API rag-f05-api-search-t009 cerrada limpiamente; consumidoresF03/F04/F05
  locks libres. Modelos cerrados. Imágenes/contenedores/documentos/journals retenidos.
- Nueva sesión diaria habilitada por Diego, validada ACTIVE; vence
  2026-11-04T08:51:32-05:00. Sin renovación automática ni cambios Bao/root/políticas.

## Siguiente acción — F07

F06 aceptada PR83/merge80b29f2adfae2f985a6414a236dc19807e8d8050,
cuatro checks HEAD/tres postmerge correctos, comentario6608799838.
Operativo alineado y todos los consumidores cerrados; no Qwen activo.
Worktree docs/F07-plan, plan/tareas/checklist/evidencia/propuesta preparados.

D-07 pendiente de respuesta expresa: Qwen3-1.7B GGUF Q8_0/llama.cpp local,
ensayo sintético CPU1.5/RAM4GiB/context2048/salida256/una generación,
sin modelo de embeddings activo durante primer ensayo, sin API pagada ni
envío a terceros, sin VMM/GPU/puertos públicos. Historial privado tenant/
propietario sin borrado automático. No descargar/ejecutar hasta decisión.
Ver provider-proposal.md con revisiones/hashes/tamaño verificados.
No inferir aprobación de la autorización anterior de Qwen embeddings.

Trabajo independiente: T002 contratos/provider mock/políticas de evidencia
offline, sin sockets/modelo/credenciales. Preparar diseño de esquema/CRUD
sin adopción persistente hasta pruebas/revisión/compatibilidad.
No pausar toda la fase por D-07 mientras quede trabajo independiente.
F05 HTTP conserva contrato y exacto; chat F07 concretará su perfil previsto.

Día válido hasta2026-11-04T08:51:32-05:00. Sin renovación automática,
root/políticas Bao, main/tag/producción/visibilidad/purgas.
Todos los documentos/originales/espacios/imágenes/contenedores/journals retenidos.
Toda ejecución ragdev01, revisión propia ADR0007 y continuidad ADR0010.
