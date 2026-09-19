# Global ARGs must be declared before first FROM so they can be used in FROM instructions
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie
ARG LITELLM_VERSION
ARG VERSION

# Stage 1: Build LiteLLM wheelhouse (no HA base — builder stage is discarded)
FROM python:3.13-slim-bookworm AS litellm-builder

ARG LITELLM_VERSION

RUN pip wheel --wheel-dir=/wheels \
        "litellm[proxy]==${LITELLM_VERSION}" \
        "psycopg[binary]==3.2.*" \
        "prisma==0.*"

# Stage 2: HA Debian base + PostgreSQL + LiteLLM
FROM ${BUILD_FROM}

ARG VERSION
ARG LITELLM_VERSION

WORKDIR /

RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql \
        postgresql-client \
        curl \
        jq \
        bash \
        libssl3 \
        libffi8 \
    && rm -rf /var/lib/apt/lists/*

# LiteLLM runtime (from wheelhouse)
COPY --from=litellm-builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
        "litellm[proxy]==${LITELLM_VERSION}" \
        "psycopg[binary]==3.2.*" \
    && rm -rf /wheels

# generate_config.py runs in run.sh to translate HA options.json -> LiteLLM YAML
COPY generate_config.py /app/generate_config.py

# Add-on startup script
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 4000

CMD ["/run.sh"]

# ### LABELS (full OCI label block per authentik/Dockerfile lines 78-103)
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="akentner (https://github.com/akentner)" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Add-ons" \
    org.opencontainers.image.authors="akentner (https://github.com/akentner)" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/akentner" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
