# Global ARG must be declared before first FROM so it is available in all stages
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23

# ---- Build stage ----
# Compiles TypeScript source from GitHub release tarball using bun
FROM oven/bun:1 AS build

ARG VERSION
WORKDIR /build

RUN curl -fsSL "https://github.com/rynfar/meridian/archive/refs/tags/meridian-v${VERSION}.tar.gz" | \
    tar xz --strip-components=1

# --ignore-scripts: skip postinstall which downloads a glibc-native claude-code binary
# (build stage is debian/glibc; runtime stage is alpine/musl — mismatched binary fails)
RUN bun install --ignore-scripts

RUN bun build bin/cli.ts src/proxy/server.ts \
    --outdir dist \
    --target node \
    --splitting \
    --external @anthropic-ai/claude-agent-sdk \
    --external libsql \
    --entry-naming '[name].js'

# ---- Runtime stage ----
FROM $BUILD_FROM

RUN apk add --no-cache nodejs npm nginx

COPY --from=build /build/dist /opt/meridian/dist
COPY --from=build /build/node_modules /opt/meridian/node_modules
COPY --from=build /build/package.json /opt/meridian/package.json

# Re-run claude-code native binary install for alpine/musl runtime
RUN node /opt/meridian/node_modules/@anthropic-ai/claude-code/install.cjs 2>/dev/null || true

# bun build --target node does not emit a shebang — wrap with a shell launcher
RUN printf '#!/bin/sh\nexec node /opt/meridian/dist/cli.js "$@"\n' > /usr/local/bin/meridian && \
    chmod +x /usr/local/bin/meridian

# Expose claude CLI for interactive login (docker exec ... claude)
RUN ln -sf /opt/meridian/node_modules/@anthropic-ai/claude-code/bin/claude.exe /usr/local/bin/claude

# Copy run script and nginx config
COPY run.sh /run.sh
RUN chmod +x /run.sh
COPY nginx.conf /etc/nginx/nginx.conf

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
