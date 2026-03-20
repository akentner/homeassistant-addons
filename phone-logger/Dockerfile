ARG BUILD_FROM
FROM ${BUILD_FROM}

ARG VERSION
ARG WORKING_DIR=/app

# Install build deps for lxml + runtime tools
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libxml2-dev \
    libxslt-dev \
    python3-dev \
    tzdata \
    curl \
    tar

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Download upstream source
WORKDIR ${WORKING_DIR}
RUN curl -fsSL "https://github.com/akentner/phone-logger/archive/refs/tags/v${VERSION}.tar.gz" \
    | tar xz --strip-components=1

# Install Python dependencies from uv.lock
RUN uv sync --frozen --no-dev --no-install-project

# Remove build dependencies
RUN apk del gcc musl-dev python3-dev

# Copy addon-specific files (override upstream placeholders)
COPY run.sh generate_config.py ./
RUN chmod a+x run.sh generate_config.py

ENV WORKING_DIR=${WORKING_DIR} TZ=Europe/Berlin
EXPOSE 8080

CMD ["/app/run.sh"]

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
