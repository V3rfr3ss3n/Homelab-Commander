FROM python:3.14.7-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52 AS builder

ENV PIP_ROOT_USER_ACTION=ignore \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
RUN python -m pip install --no-cache-dir uv==0.12.5
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
RUN uv sync --frozen --no-dev --no-editable \
    && uv pip install --python /app/.venv/bin/python cryptography==50.0.0

FROM python:3.14.7-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52

ARG BUILD_VERSION=0.2.0-dev.0
ARG BUILD_ARCH=amd64

LABEL io.hass.name="Homelab Updates" \
      io.hass.description="Native operations backend for Homelab Updates" \
      io.hass.type="app" \
      io.hass.version="${BUILD_VERSION}" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.licenses="MIT"

ENV HUL_DATA_DIR=/data \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --gid 10001 homelab-updates \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin homelab-updates \
    && apt-get update \
    && apt-get install --yes --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

VOLUME ["/data"]
EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/api/v1/health', timeout=3)"]
ENTRYPOINT ["python", "-m", "homelab_backend.container_entrypoint"]
