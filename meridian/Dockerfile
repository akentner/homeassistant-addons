ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23
FROM $BUILD_FROM

# Install Node.js, npm, and nginx (nginx provides the Ingress-facing reverse proxy)
RUN apk add --no-cache nodejs npm nginx

ARG VERSION

# Install meridian CLI and claude-code CLI globally
# hadolint ignore=DL3016
RUN npm install -g @rynfar/meridian@${VERSION}
# hadolint ignore=DL3016
RUN npm install -g @anthropic-ai/claude-code

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
