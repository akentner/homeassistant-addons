ARG BUILD_FROM
FROM $BUILD_FROM

# Install required packages
RUN apk add --no-cache curl tar

# Build arguments for version and architecture
ARG VERSION="1.0.3"
ARG TARGETARCH

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
    tar -xzf /tmp/fritz-callmonitor2mqtt.tar.gz -C /usr/local/bin/ && \
    chmod +x /usr/local/bin/fritz-callmonitor2mqtt && \
    rm /tmp/fritz-callmonitor2mqtt.tar.gz

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
