# Qwen local — F05 T001

Decisión expresa ADR0011: Qwen0.6B, 1024/coseno/L2. No API externa ni producción.
Cota operativa 512 tokens incluyendo instrucción/EOS, batch4 y un llamado simultáneo
por proceso. La orquestación deberá mantener un worker de inferencia por VM;
esta cota en proceso no impide que un operador abra dos procesos independientes.
Mantener2 vCPU; evaluar4 con mediciones si hace falta, sin prometer duplicación.

## Artefactos y entorno reproducible

Manifest público ops/f05/qwen-model-manifest.json, revisión y huella de cada archivo.
La verificación de inicio usa identidades upstream fijadas en el código, no confía
en que el manifest local pueda redefinir sus hashes. Pesos safetensors, sin pickle.
Instalar artefactos explícitamente; no descargar durante inferencia. Root del modelo
es ruta de operador, nunca request del usuario. Montar RO en futuros consumidores.

Entorno opcional separado: ops/f05/inference/pyproject.toml y uv.lock.
uv0.13.6 y Python3.12; torch CPU desde índice explícito oficial, resto PyPI.
UV_PROJECT_ENVIRONMENT=/home/diego/proyectos/rag-platform-f05-inference-venv\nuv sync --locked --project ops/f05/inference --no-dev, siempre en ragdev01; no cambiar dependencias/runtime del core.
La instalación de referencia está en
/home/diego/proyectos/rag-platform-f05-inference-venv.
AutoTokenizer/AutoModel local_files_only, sin trust_remote_code, CPUfloat32,
eval/inference_mode y use_cache=False. Pooling último token/EOS con padding izquierdo.
Instrucción query fijada; pasajes sin prefijo. Cada entrada se cuenta sin truncar
antes de inferir, y el lote entero se valida antes de devolver vectores.

## Ejemplo opt-in, solo en ragdev01

Desde checkout con PYTHONPATH=src, ejecutar con el Python del entorno opcional:
scripts/f05_embedding_benchmark.py --model-dir RUTA_MODELO_FIJADO --output ARCHIVO_NUEVO.
Definir HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1 y TOKENIZERS_PARALLELISM=false.
Output debe ser nuevo; intento fallido conserva el archivo y no simula PASS.
Solo corpus ficticio congelado: no utilizar este comando para documentos sensibles.
No logs de textos/vectores ni secretos; salida de métricas agregadas/códigos cerrados.

## Medición real en2 vCPU, 2026-11-02

qwen-benchmark-01.json conserva resultado agregado y perfil/corpus hash.
16 pasajes,16 preguntas: recall@3=1.0 ES y EN, dos gold por pregunta.
No SQL/ANN/ACL ni documentos reales; cero pruebas de aislamiento acreditadas aquí.
Carga proceso nuevo26.203s (incluye importación/verificación; no disco frío garantizado).
Indexación19.764s/0.810 fragmentos por segundo; consultas p50=2.154s,p95=3.950s.
Pico RSS proceso3796.6MiB, no RAM estable de inferencia ni requerimiento mínimo.
Repetición consulta calentada p50=2.165s. Tokens primarios961.
Repetición vector <=1e-6 y exceso de512 rechazado antes de ejecutar modelo.

Es evidencia de integración/viabilidad inicial en desarrollo, no SLA/capacidad bajo
concurrencia, comparación E5, calidad de dominio o aceptación F06. Longitudes del
fixture son cortas, no extrapolar throughput a512/32768 tokens. Mantener gates F05
SQL/ANN/aislamiento/publicación y evaluación representativa de calidad pendientes.

## Capacidad al máximo operativo, 2026-11-02

qwen-capacity-01.json: proceso nuevo, 2 vCPU/2 hilos torch, cuatro pasajes ficticios
de 512 tokens cada uno (2048 totales), sin red ni datos tenant. Lote 63.601s,
85.608 segundos CPU (134.6% medio del proceso), pico RSS3774.2MiB. Cota previa
de prueba:6144MiB por proceso; no requisito mínimo ni presupuesto multi-proceso.
Carga13.643s con caché del SO posiblemente caliente; no mejora atribuida al modelo.
Llamada simultánea rechazada por LIMIT_EXCEEDED; siguiente llamada tras liberar
correcta. Las dimensiones/finitos/norma/cantidad pasan el validador real.

No es concurrencia entre procesos/API+worker, comparación4vCPU o SLA. Scheduler
y cargas del NAS influyen. El worker debe reautorizar después de cada lote, porque
el contexto30s puede vencer durante inferencia; lease mayor y heartbeat entre lotes.
Esta medición completa la comprobación inicial del perfil, no los AC vectoriales
ni calidad de dominio/F06. No ampliar tokens/batch sin perfil/evidencia nuevos.
