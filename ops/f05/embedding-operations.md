# Entorno opcional y entrega del worker EMBED

T007 parcial, desarrollo ragdev01. Esta entrega prepara imagen, composición y
herramientas; no adopta control0007/tenant0006 ni inicia servicios. El worker necesita
ambos esquemas antes de cargar Qwen. El controlador de adopción de publicación y
la ventana de cambio siguen pendientes.

## Imagen y límites

Construir desde la raíz con
`docker build -f ops/f05/embedding.Dockerfile -t rag-f05-embedding:t004 .`.
El lock de ops/f05/worker-inference combina las dependencias de aplicación e
inferencia CPU y conserva las versiones compartidas del lock principal.
No cambia pyproject.toml/uv.lock de la API. Pesos fuera de la imagen, montados RO
en la revisión Qwen aprobada; HF offline y sin descarga de modelos.

Usar ops/f02/compose.yaml junto con ops/f05/embedding.compose.yaml y las variables
F02 existentes. El servicio embedding-worker exige las dos banderas F05 y publica
ningún puerto. UID/GID1000, raíz RO, sin capabilities, no-new-privileges,
core0, tmp64MiB, CPU1.5, RAM/swap total6GiB, pids128 y cierre120s.
OMP/MKL/OpenBLAS limitados a2 hilos. La composición no arranca dependencias por
sí sola. No usar up sobre toda la composición para una prueba del worker.

## Entrega privada

En el host, con el entorno de herramientas ya existente y PYTHONPATH=src:
`python scripts/f05_worker_host.py prepare` crea únicamente
/run/user/1000/rag-f05-worker0700 y dos locks0600. Repetir conserva los inodos.
La acción status informa archivo ausente/vencido/no vencido y consumer_busy.
UNEXPIRED solo describe la fecha del archivo, no confirma autorización en Bao.

Después de comprobar la sesión diaria vigente, el servicio embedding-issue ensure
reutiliza el AppRole existente. replace solo después del cierre del consumidor.
El wrapper toma consumer.lock antes de abrir la sesión diaria y lo conserva durante
la emisión; un consumidor activo impide ambas acciones. No ejecutar configure,
crear políticas, recuperar root, renovar día ni imprimir archivos privados.
La entrega del worker es distinta de API e INGEST. El contenedor de ejecución
no recibe día, bootstrap, migrador ni S3. Su cierre revoca su token limitado.

## Evidencia y límites

Seis pruebas de lock opcional, privacidad, idempotencia y exclusión de consumidor.
Imagen probada sin red, sin credenciales y sin pesos: importación del entrypoint,
Torch2.7.1+cpu, transformers4.51.3, cuda=None, hashes de90 módulos iguales al árbol.
La revisión propia corrigió tag y banderas de la composición antes de ejecutarla.
No se ha preparado el directorio real ni emitido credencial ni arrancado el worker.

Los ledgers ops.embedding_intents/batches no reciben SELECT readonly; solo app
SELECT/INSERT y UPDATE acotado en intents. La publicación knowledge sí conserva
SELECT readonly. Negativas SQL42501 ensayadas en cuatro fixtures con rollback;
no se han aplicado estos grants persistentemente.

Faltan adopción controlada revisada, handoffs reales, inferencia del proceso,
crash entre commits independientes, regresión de originales HTTP/S3 y búsqueda.
No aceptar T004/T005/T007 ni F05 con esta evidencia.
