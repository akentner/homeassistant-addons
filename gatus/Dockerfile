# Global ARGs must be declared before first FROM so they can be used in FROM instructions
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23
ARG VERSION

# Stage 1: Extract statically-linked Gatus binary from upstream image
FROM ghcr.io/twin/gatus:v${VERSION} AS gatus-source

# Stage 2: HA base image
FROM ${BUILD_FROM}

# Re-declare VERSION for use in this stage
ARG VERSION

# CA certificates for HTTPS monitoring; nginx for ingress proxy; python3 + py3-yaml for generate_config.py
# curl + jq for external endpoint scripts; dcron for cron job support; bash for script compatibility
# mosquitto-clients for MQTT monitoring; open-plc-utils for HomePlug/Powerline (requires NET_RAW capability)
# ethtool + arping + iproute2 + mtr for Layer 2 / network diagnostics
RUN apk add --no-cache \
    ca-certificates nginx python3 py3-yaml \
    curl jq dcron bash \
    mosquitto-clients \
    open-plc-utils \
    ethtool arping iproute2 mtr

# Copy statically-linked binary — no additional runtime dependencies needed
COPY --from=gatus-source /gatus /usr/local/bin/gatus

# Copy add-on scripts and nginx config
COPY run.sh generate_config.py /
COPY nginx.conf /etc/nginx/gatus-nginx.conf

RUN chmod +x /run.sh /usr/local/bin/gatus

EXPOSE 8099
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
