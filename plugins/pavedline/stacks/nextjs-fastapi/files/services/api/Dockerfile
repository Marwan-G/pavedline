# syntax=docker/dockerfile:1
# Build:  docker build -t api:dev services/api            (context: services/api)
# Run:    docker run --read-only --tmpfs /tmp -e APP_ENV=... -e DATABASE_URL=... -p 8000:8000 api:dev
# Images are pinned by digest (linux/arm64 and linux/amd64 index digests).

FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

FROM python:3.14.9-slim@sha256:35caba83af2fe6da9a5d922f9b0156f21d1246a48278c58a08bd253303ba42e8 AS build
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /srv
COPY pyproject.toml uv.lock .python-version ./
# Runtime dependencies only, exactly as locked.
RUN uv sync --frozen --no-dev

FROM python:3.14.9-slim@sha256:35caba83af2fe6da9a5d922f9b0156f21d1246a48278c58a08bd253303ba42e8 AS runtime
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /opt/venv /opt/venv
WORKDIR /srv
COPY app ./app
COPY migrations ./migrations
COPY db ./db
COPY alembic.ini ./
USER 10001:10001
# The in-image boot check: import the app and render its OpenAPI without a database.
# An image that cannot start fails the build, not the first pod.
RUN python -m app.boot_check
EXPOSE 8000
# Runs with a read-only root filesystem; only /tmp needs to be writable.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--proxy-headers"]
