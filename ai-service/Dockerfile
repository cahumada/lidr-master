# Imagen del servicio IA. || AI service image.
#
# Railway construye desde este directorio (`ai-service/` como root directory),
# así que el contexto de build NO incluye `business-backend/` ni `openspec/`.
#
# || Railway builds from this directory (`ai-service/` as the root directory),
# so the build context does NOT include `business-backend/` or `openspec/`.

FROM python:3.11-slim AS base

# uv desde su imagen oficial: una copia de un binario, sin instalar pip ni curl.
# || uv from its official image: one binary copied in, no pip or curl install.
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Las dependencias primero, en su propia capa: el código cambia todos los días
# y el lockfile no, así que un deploy normal no reinstala nada.
# || Dependencies first, in their own layer: the code changes every day and the
# lockfile does not, so an ordinary deploy reinstalls nothing.
#
# `--frozen` falla si `uv.lock` no coincide con `pyproject.toml`: la imagen
# instala exactamente lo que el lockfile fija, igual que CI.
# || `--frozen` fails if `uv.lock` disagrees with `pyproject.toml`: the image
# installs exactly what the lockfile pins, the same as CI.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

RUN uv sync --frozen --no-dev

# Railway inyecta `PORT`. El default es para correrla a mano.
# || Railway injects `PORT`. The default is for running it by hand.
ENV PORT=8000
EXPOSE 8000

# `sh -c` para que `$PORT` se expanda; en exec form quedaría literal.
# || `sh -c` so `$PORT` expands; in exec form it would stay literal.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
