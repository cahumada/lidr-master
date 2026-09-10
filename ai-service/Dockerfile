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

# El arranque migra y RECIÉN DESPUÉS sirve. Copiar `alembic/` a la imagen y no
# usarlo dejaba cada migración como un paso manual que nada recuerda, y la forma
# que toma el olvido es un `UndefinedColumn` en la primera pregunta.
#
# Es seguro porque el servicio corre como UNA SOLA instancia en Railway —la
# misma premisa del buffer en memoria de `app/domain/graph/activity.py`—, así
# que no hay dos procesos compitiendo por el lock de migración. El día que haya
# más de un worker, esto se mueve a un paso de release, no antes.
#
# El `&&` es lo importante: si la migración falla, el contenedor NO levanta.
# Un servicio que responde con el esquema viejo miente, y Railway mantiene el
# deploy anterior vivo en vez de promover este.
#
# `sh -c` además hace que `$PORT` se expanda; en exec form quedaría literal.
#
# || Startup migrates and only THEN serves. Safe because the service runs as a
# SINGLE instance on Railway, so no two processes race for the migration lock.
# The `&&` matters: if the migration fails the container does NOT come up, and
# Railway keeps the previous deploy instead of promoting this one. `sh -c` also
# makes `$PORT` expand; in exec form it would stay literal.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
