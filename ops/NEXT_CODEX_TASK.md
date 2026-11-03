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

Revisar diff documental y validar docs/diff; árbol idéntico VM/GitHub,
PR a develop, CI HEAD exacto, revisión propia delegada ADR0007, merge y postmerge.
Registrar aceptación efectiva y continuar plan/tareas F06 dentro de ADR0010.
No terminar por cierre de PR/fase ni pedir autorización de trámite.
HTTP sigue exacto; ANN interno validado, sin promesas de latencia o dominioF06.
Qwen/HTTPfragmentos/adopciónBD/conexiónprivada ya aprobados; no volver a pedir.
Control0007/cuatro tenants0006, espacios publicados. No repetir adopción.

F06 tiene spec en specs/F06-recuperacion-evaluacion/spec.md. Revisar AC03:
document.state RECEIVED indica recepción original y se conserva con versión
procesada PUBLISHED; aclarar su relación con versiones no publicadas bajo
contratos vigentes antes de implementar. No cambiar contrato rector unilateralmente.
Toda ejecución en ragdev01; no main/tag/producción/visibilidad/purgas.
