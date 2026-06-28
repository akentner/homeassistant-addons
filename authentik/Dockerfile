# Global ARGs must be declared before first FROM so they can be used in FROM instructions
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie
ARG VERSION

# Stage 1: authentik official image — source for binaries, Python runtime, and app files
FROM ghcr.io/goauthentik/server:${VERSION} AS authentik-source

# Stage 2: HA Debian base — add PostgreSQL, Valkey, and everything from stage 1
FROM ${BUILD_FROM}

ARG VERSION

# System dependencies: PostgreSQL, Valkey (Redis-compat in Debian Trixie), and shared libs
# Python 3.14 runtime is copied from stage 1 — no Python apt package needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql \
    valkey \
    curl \
    jq \
    bash \
    libssl3 \
    libffi8 \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# ── Authentik binaries ───────────────────────────────────────────────────────
# authentik-server: Go binary, nearly static — only needs libc
COPY --from=authentik-source /usr/bin/authentik-server /usr/bin/authentik-server
# authentik: Rust binary — dynamically linked to libpython3.14
COPY --from=authentik-source /usr/bin/authentik /usr/bin/authentik

# ── Python 3.14 runtime (needed by the Rust worker binary and lifecycle scripts) ──
COPY --from=authentik-source /usr/local/bin/python3.14 /usr/local/bin/python3.14
COPY --from=authentik-source /usr/local/bin/python3 /usr/local/bin/python3
COPY --from=authentik-source /usr/local/bin/python /usr/local/bin/python
COPY --from=authentik-source /usr/local/lib/libpython3.14.so.1.0 /usr/local/lib/libpython3.14.so.1.0
COPY --from=authentik-source /usr/local/lib/libpython3.14.so /usr/local/lib/libpython3.14.so
COPY --from=authentik-source /usr/local/lib/libpython3.so /usr/local/lib/libpython3.so
COPY --from=authentik-source /usr/local/lib/python3.14 /usr/local/lib/python3.14

# Register copied shared library so the dynamic linker finds it
RUN ldconfig

# ── Authentik Python venv (pre-built against Python 3.14 on Bookworm/glibc) ─
COPY --from=authentik-source /ak-root /ak-root

# ── Authentik application files ──────────────────────────────────────────────
COPY --from=authentik-source /authentik /authentik
COPY --from=authentik-source /blueprints /blueprints
COPY --from=authentik-source /schemas /schemas
COPY --from=authentik-source /web /web
COPY --from=authentik-source /lifecycle /lifecycle
COPY --from=authentik-source /locale /locale
COPY --from=authentik-source /geoip /geoip
COPY --from=authentik-source /manage.py /manage.py
COPY --from=authentik-source /pyproject.toml /pyproject.toml

# ── Create authentik user (uid 1000, matching the upstream image) ─────────────
RUN groupadd --gid 1000 authentik && \
    useradd --uid 1000 --gid 1000 --home /ak-root --no-create-home \
            --shell /usr/sbin/nologin authentik && \
    chown -R authentik:authentik /ak-root && \
    mkdir -p /media /certs && \
    chown -R authentik:authentik /media /certs

# ── PostgreSQL runtime directories ───────────────────────────────────────────
RUN mkdir -p /var/run/postgresql && chown postgres:postgres /var/run/postgresql

# ── Add-on startup script ─────────────────────────────────────────────────────
COPY run.sh /
RUN chmod +x /run.sh

WORKDIR /
EXPOSE 9000 9443

CMD ["/run.sh"]

# ### LABELS
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
