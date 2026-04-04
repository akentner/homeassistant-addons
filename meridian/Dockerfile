ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23
# Stage 1: Build — compile TypeScript with bun
FROM oven/bun:1 AS build

ARG VERSION
WORKDIR /build

# Download upstream source archive and install + build
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl tar && \
    curl -fsSL "https://github.com/rynfar/meridian/archive/refs/tags/v${VERSION}.tar.gz" \
    | tar xz --strip-components=1

RUN bun install --frozen-lockfile
RUN bun build bin/cli.ts src/proxy/server.ts --outdir dist --target node --splitting --external @anthropic-ai/claude-agent-sdk --entry-naming '[name].js' && \
    tsc -p tsconfig.build.json

# Stage 2: Runtime — HA base image with Node.js
FROM $BUILD_FROM

# Install Node.js and npm to run dist/cli.js and install @anthropic-ai/claude-code
RUN apk add --no-cache nodejs npm

ARG VERSION
ARG WORKING_DIR=/opt/meridian

ENV WORKING_DIR=${WORKING_DIR}

# Install @anthropic-ai/claude-code globally to provide the claude CLI binary
# hadolint ignore=DL3016
RUN npm install -g @anthropic-ai/claude-code

RUN mkdir -p ${WORKING_DIR}

# Copy compiled output and node_modules from build stage
COPY --from=build /build/dist ${WORKING_DIR}/dist
COPY --from=build /build/node_modules ${WORKING_DIR}/node_modules

# Copy run script
COPY run.sh ${WORKING_DIR}/
RUN chmod +x ${WORKING_DIR}/run.sh

WORKDIR ${WORKING_DIR}
CMD ["./run.sh"]

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
