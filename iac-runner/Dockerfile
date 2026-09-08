# syntax=docker/dockerfile:1

# Global ARGs must be declared before the first FROM so they can be referenced
# inside the FROM instructions below (mirror terraform-bridge/Dockerfile L1-7
# pattern).
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
ARG RUNNER_VERSION=dev
ARG TOFU_VERSION=1.10.6

# Stage 1: Go build — produces a static binary that runs on Alpine/musl with
# no libc/glibc mismatch (CGO_ENABLED=0). Multi-stage keeps the runtime image
# under 60 MiB uncompressed (OPS-05 mirror from terraform-bridge).
FROM golang:1.27-alpine AS builder

ARG RUNNER_VERSION

WORKDIR /workspace

# Copy module manifests first so `go mod download` is cached separately from
# the source tree — re-runs that only touch *.go files skip the dependency
# download step.
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# -trimpath: reproducible builds (no $GOPATH baked in).
# -s -w: strip DWARF + symbol table.
# -X main.runnerVersion=...: inject the version baked into build.yaml.
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -trimpath -ldflags "-s -w -X main.runnerVersion=${RUNNER_VERSION}" \
    -o runner ./cmd/runner

# Stage 2: OpenTofu download — pinned version + upstream SHA256 verification. Kept in its own
# alpine stage so curl/unzip never land in the runtime image (mirror gatus/Dockerfile stage 2).
FROM alpine:3.22 AS tofu

ARG TOFU_VERSION

# WORKDIR instead of an in-RUN `cd /tmp` (hadolint DL3003). sha256sum -c
# resolves the filename inside SHA256SUMS relative to the working
# directory, so the checksum step needs /tmp to BE the workdir — it
# cannot take an absolute path. Nothing later in this build-only stage
# depends on the previous workdir, and the COPY --from=tofu in stage 3
# uses an absolute path, so there is nothing to restore.
WORKDIR /tmp

# The zip MUST keep its upstream filename: `sha256sum -c -` reads the
# name out of the SHA256SUMS line and opens exactly that path relative
# to the workdir. Saving it as tofu.zip made the verification step fail
# with "can't open tofu_<v>_linux_amd64.zip" — a checksum that can never
# pass is worse than none, because it looks like a guarantee.
RUN apk add --no-cache curl unzip && \
    curl -fsSL -o "tofu_${TOFU_VERSION}_linux_amd64.zip" \
        "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_linux_amd64.zip" && \
    curl -fsSL -o SHA256SUMS \
        "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_SHA256SUMS" && \
    grep " tofu_${TOFU_VERSION}_linux_amd64.zip\$" SHA256SUMS | sha256sum -c - && \
    unzip -j "tofu_${TOFU_VERSION}_linux_amd64.zip" tofu -d /usr/local/bin && \
    chmod +x /usr/local/bin/tofu && \
    /usr/local/bin/tofu version

# Stage 3: HA base — minimal Alpine 3.24 image. The binary is the only thing
# we ship from the builder stage; everything else stays behind.
FROM ${BUILD_FROM}

ARG RUNNER_VERSION

# Phase 17 runtime dependencies:
#   git + openssh-client — GIT-02/GIT-03 clone + `git pull --ff-only` over SSH using the deploy key at
#     /data/keys/<name>.key with /data/keys/known_hosts (invoked via GIT_SSH_COMMAND).
#   tofu — RUN-02/RUN-03 `tofu init/plan/apply`. handlers/healthz.go probes exec.LookPath("tofu") and returns
#     503 without it, so this COPY is what makes Phase 16 SC#7 satisfiable.
RUN apk add --no-cache git openssh-client

COPY --from=tofu /usr/local/bin/tofu /usr/bin/tofu
RUN chmod +x /usr/bin/tofu

COPY --from=builder /workspace/runner /usr/bin/runner
RUN chmod +x /usr/bin/runner

COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 8125
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
