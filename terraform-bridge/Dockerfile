# syntax=docker/dockerfile:1

# Global ARGs must be declared before the first FROM so they can be referenced
# inside the FROM instructions below (mirror authentik/Dockerfile L1-3 pattern).
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
ARG BRIDGE_VERSION=dev

# Stage 1: Go build — produces a static binary that runs on Alpine/musl with
# no libc/glibc mismatch (CGO_ENABLED=0). The full multi-stage pattern is what
# keeps the runtime image under 60 MiB uncompressed (OPS-05).
FROM golang:1.25-alpine AS builder

ARG BRIDGE_VERSION

WORKDIR /workspace

# Copy module manifests first so `go mod download` is cached separately from
# the source tree — re-runs that only touch *.go files skip the dependency
# download step.
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# -trimpath: reproducible builds (no $GOPATH baked in).
# -s -w: strip DWARF + symbol table.
# -X main.bridgeVersion=...: inject the version baked into build.yaml.
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -trimpath -ldflags "-s -w -X main.bridgeVersion=${BRIDGE_VERSION}" \
    -o bridge ./cmd/bridge

# Stage 2: HA base — minimal Alpine 3.24 image. The binary is the only thing
# we ship from the builder stage; everything else stays behind.
FROM ${BUILD_FROM}

ARG BRIDGE_VERSION

COPY --from=builder /workspace/bridge /usr/bin/bridge
RUN chmod +x /usr/bin/bridge

COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 8124
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
