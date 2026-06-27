ARG BUILD_FROM
FROM ${BUILD_FROM}

ARG VERSION
ARG DOCSIFY_VERSION=4.13.1
ARG MERMAID_VERSION=11.15.0
ARG WORKING_DIR=/app

# Install runtime dependencies: nginx for serving Docsify SPA,
# curl + tar for vendoring Docsify/Mermaid from GitHub release tarballs.
# python3 + bashio are already provided by amd64-base-python:3.12-alpine3.20.
RUN apk add --no-cache nginx curl tar

# Vendored Docsify 4.13.1 (ADD-02): extract lib/docsify.min.js + themes/vue.css
# from the GitHub release tarball. Pinned via ARG DOCSIFY_VERSION.
WORKDIR ${WORKING_DIR}/_docsify
RUN mkdir -p themes && \
    curl -fsSL "https://github.com/docsifyjs/docsify/archive/refs/tags/v${DOCSIFY_VERSION}.tar.gz" \
    | tar xz --strip-components=1 --wildcards "*/lib/docsify.min.js" "*/themes/vue.css"

# Vendored Mermaid 11.15.0 UMD build (ADD-02): extract dist/mermaid.min.js.
# Tarball URL uses the encoded "@" (mermaid@11.15.0 tag -> mermaid%4011.15.0).
# --strip-components=2 drops both <repo>-mermaid-<version> and dist/ from the path.
RUN curl -fsSL "https://github.com/mermaid-js/mermaid/archive/refs/tags/mermaid%40${MERMAID_VERSION}.tar.gz" \
    | tar xz --strip-components=2 --wildcards "*/dist/mermaid.min.js"

# Copy add-on-specific files (run.sh + generate_nginx.py); both must be chmod +x.
WORKDIR ${WORKING_DIR}
COPY run.sh generate_nginx.py ./
RUN chmod a+x run.sh generate_nginx.py

ENV WORKING_DIR=${WORKING_DIR}
EXPOSE 8099
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
