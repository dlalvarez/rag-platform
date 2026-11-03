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

## Siguiente acción — cierre F06

Pruebas técnicas F06 completas. Falta CI/revisión/merge/postmerge del expediente.
Rama docs/F06-acceptance conserva métricas verificadas y diagnósticos.
Operativo54b4c9684044fc179d7766158e11bd3ae507b31f (PR82), código core probado,
cuatro checks HEAD/tres postmerge correctos. No cambiar checkout con consumidores.

Calidad ac2b8e1743994b4c9bed1aa5a0573126:44ops/2281tokens,Recall10=1.0
ES/EN vector+híbrido,1600citas/32FTS/rollbackPASS; baseline-v1.json allowlisted.
Servicio real7e04eee3dac24d269d825a0fb37bde66:8ops184tokens,4hybridcites
y12exactF05resultsciteresolved,0deniedinference, sin mutar corpus.
Regresiónfinal4fb9bbd4bda24235bb401a7c753051a2 exit0/37.58s, cuatro
tenants/dos instancias OIDC/SQL/TLS/roles/S3/privacidad/históricosPASS.

S3ProtocolError reproducido68bc0f45... RemoteDisconnected en conexión reutilizada.
PR82: lectura GET/HEAD retry1, escrituras/status/TLS/conexión sin replay,
sin redirects y logs saneados antes del retry. No denegaciones relajadas.
Suite1295PASS91.31s/1warning; hashsmoke105módulos/sourceRO/sinTorch.
Imagen anterior retenida; nuevoAPI rag-f06-api-source-t010 cerrado limpiamente,
locks F03/F04/F05 libres. No Qwen activo.

Integrar expediente y registrar aceptación efectiva antes de implementar F07.
Continuar el roadmap ADR0010 sin otra autorización de trámite.
F07 D-07 requiere propuesta concreta de perfil LLM/retención y decisión real;
preparar plan/tareas e interfaz/mock dentro del alcance original antes de código.
No usar proveedor externo/modelo nuevo o cambiar retención por iniciativa.

Día válido hasta2026-11-04T08:51:32-05:00; sin renovación automática.
Todo en ragdev01, revisión propia ADR0007, sin main/tag/producción/visibilidad/
purgas/root/políticas Bao. Conservar imágenes/contenedores/documentos/journals.
