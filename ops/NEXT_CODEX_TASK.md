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

## Siguiente acción

F05 aceptada en PR74, merge7f7f180d400d28203d2b20f1947d792661237251.
Cuatro checks HEAD/tres postmerge SUCCESS, aceptación registrada en comentario
6605895334. Operativo alineado; worktree docs/F06-plan.
Plan/tareas/checklist/evidencia F06 preparados antes de implementación.
Diego aprobó aclarar AC03: solo versiones procesadas vigentes publicadas/completas/
autorizadas, estado recepción original conservado, sin migración.

Validar/revisar/integrar el plan; seguir T002 contratos/filtros/RRF y pruebas.
No requiere otra aprobación de trámite. RRF60/50candidatos por modalidad y FTS
simple, inicialmente sin DDL persistente. API F05 conserva contrato/exacto.
Corpus >=30preguntas congelado antes de medir, golds/negativas/ambigüedad,
citas100% autorizadas y recall@10>=.80; no reusar métricas F05 como calidad F06.

Sesión diaria validada hasta2026-11-04T08:51:32-05:00; no renovación automática.
Modelos/API de pruebas cerrados y consumidores libres, recursos conservados.
Todo código/dependencias/servicios en ragdev01. CI exacto y revisión propia
delegada ADR0007, postmerge; no main/tag/producción/visibilidad/purgas/Bao.
Continuar al completar PR/fase según ADR0010. F07 requiere F06 aceptada.
