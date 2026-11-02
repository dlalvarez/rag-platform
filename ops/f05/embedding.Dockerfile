FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/embedding-venv UV_CACHE_DIR=/tmp/uv-cache
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6
COPY ops/f05/worker-inference/pyproject.toml ops/f05/worker-inference/uv.lock /opt/worker/
RUN uv sync --locked --no-dev --no-install-project --project /opt/worker --python /usr/local/bin/python && uv cache clean
COPY src ./src
COPY ops/f03/application-scope.json ./ops/f03/application-scope.json
ENV PATH="/opt/embedding-venv/bin:$PATH" PYTHONPATH=/app/src \
    HF_HOME=/tmp/hf HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
USER 1000:1000
ENTRYPOINT ["python", "-m", "rag_platform.embeddings.worker_main"]
