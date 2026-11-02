FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable
COPY alembic-control.ini alembic-tenant.ini ./
COPY migrations ./migrations
COPY tests/integration/f01/migration_fixture ./tests/integration/f01/migration_fixture
COPY scripts/f01_*.py ./scripts/
COPY ops/f01/*.hcl ./ops/f01/
COPY scripts/f02_*.py ./scripts/
ENV PATH="/app/.venv/bin:$PATH"
COPY scripts/f03_*.py ./scripts/
COPY ops/f03 ./ops/f03/
COPY scripts/f04_*.py ./scripts/
COPY ops/f04/corpus-manifest.json ./ops/f04/
