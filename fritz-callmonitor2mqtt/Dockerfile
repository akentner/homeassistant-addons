ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.22
FROM $BUILD_FROM

# Install required packages
RUN apk add --no-cache curl tar

# Build arguments for version and architecture
ARG VERSION
ARG WORKING_DIR=/opt/fritz-callmonitor2mqtt
ARG TARGETARCH

ENV WORKING_DIR=${WORKING_DIR}
ENV FRITZ_CALLMONITOR_DATABASE_DATA_DIR="${WORKING_DIR}/data"

RUN mkdir -p ${WORKING_DIR} ${FRITZ_CALLMONITOR_DATABASE_DATA_DIR}
WORKDIR ${WORKING_DIR}

# Download and extract Go binary based on architecture
RUN case "${TARGETARCH}" in \
    "amd64") ARCH="amd64" ;; \
    "arm64") ARCH="arm64" ;; \
    "arm/v7") ARCH="armv7" ;; \
    "arm/v6") ARCH="armv6" ;; \
    *) ARCH="amd64" ;; \
    esac && \
    curl -L "https://github.com/akentner/fritz-callmonitor2mqtt/releases/download/v${VERSION}/fritz-callmonitor2mqtt-${VERSION}-linux-${ARCH}.tar.gz" \
    -o /tmp/fritz-callmonitor2mqtt.tar.gz && \
    tar -xzf /tmp/fritz-callmonitor2mqtt.tar.gz -C ${WORKING_DIR} && \
    chmod +x ${WORKING_DIR}/fritz-callmonitor2mqtt && \
    rm /tmp/fritz-callmonitor2mqtt.tar.gz

# Copy run script for add-on
COPY run.sh ${WORKING_DIR}/
RUN chmod +x ${WORKING_DIR}/run.sh

# Add useful aliases
RUN echo "alias ll='ls -alFh --color=auto'" >> /etc/profile.d/aliases.sh

# Set working directory and entrypoint
WORKDIR ${WORKING_DIR}
CMD [ "./run.sh" ]

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
