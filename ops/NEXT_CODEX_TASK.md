# Siguiente tarea Codex — validar y revisar T005

T001–T004 aceptadas e integradas mediante PR #9/#10/#11/#12.
Base T005: develop@e46b46f822ca3726086d3b2ba3dc78b71db9ba3e.
Rama feat/F01-T005-resolver-pools.
[Runbook](f01/T005.md), [evidence](../specs/F01-aislamiento-provisionamiento/evidence.md).

T005 implementa P5/V03/V06 parcial: resolver interno, refs sin password y pools
limitados por tenant/destino/rol/ref-versión. No AuthorizedTenantContext de F02.
Batería real completada por Diego: cuatro PASS T005 mediante pool-check.
Código probado: bd3145baf48971c40d77b1f3c9146d0de5ed537a; PR #13.
Reutiliza fixtures READY T004; no nuevos tenants, servicios ni passwords SQL.
Cambio temporal de referencia sintética se restaura en finally; conservar la referencia
de prueba adicional en OpenBao. No convertir esto en rotación operativa o limpieza.

Resultado y fuentes exactas registrados; 138 pruebas offline correctas.
Comprobar CI del HEAD final y presentar PR para revisión;
no fusionar hasta aprobación explícita. Tras merge autorizado verificar postmerge.
Solo después de aceptar T005 y autorizar continuar: T006 conforme P6/V01–V07,
incluida la segunda instancia real y migraciones coordinadas; no acreditarlas con mocks.

Conservar F00 y fixtures F01, incluso FAILED/REVIEW. No reinicializar OpenBao,
regenerar secretos, borrar recursos o repetir prepare-storage.
Desarrollo/pruebas siempre en ragdev01, nunca local. F01 e Issue #7 siguen abiertos.
