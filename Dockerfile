# syntax=docker/dockerfile:1

# ---------- Stage 1: builder — install dependencies with uv ----------
FROM python:3.12-slim AS builder

# Copy the uv binary from Astral's official image (pinned minor version).
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

# Pre-compile .pyc for faster startup; copy files instead of hard-linking (cache is a mount);
# never download a Python — use the one in this base image.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# 1) Dependencies only (changes rarely → this layer is cached between builds).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# 2) Our own code (changes often → only this cheap step reruns).
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ---------- Stage 2: runtime — small image, no build tools, non-root ----------
FROM python:3.12-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
