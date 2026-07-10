FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md .python-version ./
COPY src ./src
COPY scripts ./scripts

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD [".venv/bin/uvicorn", "docparser.app:app", "--host", "0.0.0.0", "--port", "8000"]
