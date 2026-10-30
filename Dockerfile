FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable
ENV PATH="/app/.venv/bin:$PATH"
USER 10001:10001
CMD ["uvicorn", "rag_platform.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS smoke
USER root
RUN uv sync --frozen --no-editable
COPY scripts/f00_smoke.py /app/smoke.py
USER 10001:10001
CMD ["python", "/app/smoke.py"]
