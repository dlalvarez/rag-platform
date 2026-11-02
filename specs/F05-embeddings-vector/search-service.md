# Servicio interno de búsqueda F05

F05-R04/R06, AC-F05-02/04 parciales. SearchService recibe RepositoryService con
autoridad embedding_publication y provider de perfil inmutable coseno/L2.
No carga Qwen ni configura transporte/API.

Valida el contexto firmado, forma de entrada y todos los repositorios antes de
tokenizar o inferir. Perfil completo contra catálogo, cota real de tokens incluyendo
prefijo/especiales, sin truncar. Libera transacciones/conexiones antes del proveedor.
Valida dimensión, norma, finitud, perfil y uso de la respuesta. Después crea contexto
nuevo, repite ACL completa y catálogo y usa la referencia exacta publicada. Revalida
control antes de devolver evidencia. Una revocación durante inferencia no devuelve
hits; el coste de esa inferencia ya realizada no se deshace.

Resultado interno privado: hits y uso, sin vector/query en repr. Errores cerrados
usan DocumentError/AccessError existentes: perfil incompatible409, input422,
cota429, dependencia503. Sin escritura de jobs/documentos ni uso persistido de consulta;
la respuesta informa tokens y una solicitud. No cambia cuotas de indexación ni billing.
La API futura deberá aplicar límites de request/response, timeout del proveedor y
no-store. El transporte del provider local queda separado de este componente.

## Prueba real opt-in preparada
Combinación F02 con ops/f05/search-check.compose.yaml, variables privadas F02
existentes, RAG_F04_QA_ROOT al manifest retenido y RAG_F05_EMBED_QA_ROOT al journal
Qwen verificado. run --rm --no-deps --pull never f05-search-check, después de CI,
revisión, integración y postmerge. La imagen opcional existente y fuentes revisadas
montadas RO evitan instalar Torch en API o descargar modelo. Conserva CPU1.5/6GiB,
modelo RO y red control, sin nuevo servidor.

El trabajador EMBED debe estar detenido, lock libre y entrega F05 válida independiente;
usar replace autorizado tras cerrar consumidor, nunca compartir ni renovar el día.
La prueba cierra/revoca su entrega al terminar. Comprueba cuatro atomic publicados,
consulta Qwen real y procedencia SQL exacta, repo de otro tenant rechazado antes del
proveedor. Imprime solo PASS/códigos cerrados, sin fragmentos, vectores ni credenciales.
No prueba HTTP, ANN, calidad semántica, crash ni latencia; no crea corpus ni jobs.
