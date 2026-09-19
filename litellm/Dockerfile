# Global ARGs must be declared before first FROM so they can be used in FROM instructions
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie
ARG LITELLM_VERSION
ARG VERSION

# Stage 1: Build LiteLLM wheelhouse (no HA base — builder stage is discarded)
FROM python:3.13-slim-bookworm AS litellm-builder

# Default falls the build workflow does not pass LITELLM_VERSION via --build-arg.
# The repo-wide build.yml workflow only forwards the standard set
# (BUILD_FROM/VERSION/BUILD_ARCH/BUILD_DATE/BUILD_NAME/BUILD_DESCRIPTION/BUILD_REF/
# BUILD_REPOSITORY/BUILD_VERSION); addon-specific args from build.yaml are not
# forwarded, so this default keeps the build self-sufficient.
ARG LITELLM_VERSION=1.101.0

RUN pip wheel --wheel-dir=/wheels \
        "litellm[proxy]==${LITELLM_VERSION}" \
        "psycopg[binary]==3.2.*" \
        "prisma==0.*"

# Stage 2: HA Debian base + PGDG-postgres-16 + LiteLLM
# PGDG repo + PostgreSQL 16 (NOT Debian-default postgresql-15) — see PLAN.md Q7
FROM ${BUILD_FROM}

ARG VERSION
ARG LITELLM_VERSION=1.101.0

WORKDIR /

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        postgresql-16 \
        postgresql-client-16 \
        jq \
        bash \
        libssl3 \
        libffi8 \
        python3 \
        python3-pip \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

# LiteLLM runtime (from wheelhouse). Use python3 -m pip (not bare `pip`)
# because python3-pip installs pip3 but not a `pip` shim on Debian Trixie.
# --break-system-packages is required because Debian Trixie marks the
# system python3 as externally-managed (PEP 668); in a Docker container
# this is the standard escape hatch since the container IS its own
# isolated environment.
COPY --from=litellm-builder /wheels /wheels
# Install litellm + psycopg + prisma. prisma is NOT a transitive dep of
# litellm[proxy] (litellm ships it as a separate optional dep that's only
# pulled when you `pip install litellm[prisma]`). The wheelhouse builds
# `prisma==0.*` for the codegen client; without installing it here,
# litellm.proxy fails at startup with `No module named 'prisma'`. The
# `prisma generate` post-install is needed to fetch the engine binary
# (not part of the wheel; downloaded on first install).
RUN python3 -m pip install --no-cache-dir --no-index --break-system-packages \
        --find-links=/wheels \
        "litellm[proxy]==${LITELLM_VERSION}" \
        "psycopg[binary]==3.2.*" \
        "prisma==0.*" \
    # prisma generate needs the schema.prisma file. litellm ships its
    # Prisma schema inside the installed package at litellm/proxy/prisma/
    # schema.prisma — point prisma at it explicitly. Without --schema,
    # prisma generate fails with "Could not find Prisma Schema" because
    # the workdir `/` has no schema.prisma.
    && LITELLM_PRISMA_SCHEMA="$(python3 -c "import litellm.proxy.prisma, os; print(os.path.join(os.path.dirname(litellm.proxy.prisma.__file__), 'schema.prisma'))")" \
    && echo "Prisma schema: ${LITELLM_PRISMA_SCHEMA}" \
    && prisma generate --schema="${LITELLM_PRISMA_SCHEMA}" \
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
