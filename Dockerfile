# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM python:3.14.8-slim

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock README.md .python-version ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

RUN useradd --create-home --uid 10001 xeon \
    && chown -R xeon:xeon /app

USER xeon

EXPOSE 8000

CMD ["uvicorn", "xeon.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

