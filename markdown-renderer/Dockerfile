ARG BUILD_FROM
FROM ${BUILD_FROM}

ARG VERSION
ARG DOCSIFY_VERSION=4.13.1
ARG MERMAID_VERSION=11.15.0
ARG WORKING_DIR=/app

# Install runtime dependencies: nginx for serving Docsify SPA,
# curl + tar for vendoring Docsify/Mermaid from GitHub release tarballs,
# git for optional namespace sync (GIT-01..05). The git binary is always
# installed even when no namespace uses git sync (GIT-03 forbids
# _invocation_ of git when unconfigured; installation is unconditional
# to keep the image layer flat).
# python3 + bashio are already provided by amd64-base-python:3.12-alpine3.20.
RUN apk add --no-cache nginx curl tar git

# Vendored Docsify 4.13.1 (ADD-02): extract lib/docsify.min.js + themes/vue.css.
# Note: the GitHub source tarball (docsifyjs/docsify archive refs/tags/v...) ships
# only source files (.styl, .js source), NOT prebuilt artifacts. The npm registry
# package (docsify-4.13.1.tgz) ships the prebuilt lib/docsify.min.js and
# themes/vue.css. Pinned via ARG DOCSIFY_VERSION.
WORKDIR ${WORKING_DIR}/_static
RUN mkdir -p themes && \
    curl -fsSL "https://registry.npmjs.org/docsify/-/docsify-${DOCSIFY_VERSION}.tgz" \
    | tar xz --strip-components=1 --wildcards "*/lib/docsify.min.js" "*/themes/vue.css"

# Vendored Mermaid 11.15.0 UMD build (ADD-02): extract dist/mermaid.min.js.
# The GitHub source tarball ships only TypeScript sources; the npm registry
# package (mermaid-11.15.0.tgz) ships the prebuilt dist/mermaid.min.js.
RUN curl -fsSL "https://registry.npmjs.org/mermaid/-/mermaid-${MERMAID_VERSION}.tgz" \
    | tar xz --strip-components=1 --wildcards "*/dist/mermaid.min.js"

# Flatten the package layouts to /app/_static/{docsify.min.js,mermaid.min.js,themes/vue.css}.
# The _static/ directory is intentionally distinct from /app/_docsify/
# (the old name) - nginx exposes both /<ns>/_static/ (per-namespace) and
# /_static/ (top-level fallback) and they must NOT collide with any
# user Markdown directory. See validate_namespace()'s RESERVED_NAMES.
RUN mv lib/docsify.min.js ./docsify.min.js && \
    mv lib/themes/vue.css themes/vue.css && \
    mv dist/mermaid.min.js ./mermaid.min.js && \
    rm -rf lib dist

# Copy add-on-specific files (run.sh + generate_nginx.py + _git_sync.py); all must be chmod +x.
WORKDIR ${WORKING_DIR}
COPY run.sh generate_nginx.py _git_sync.py ./
RUN chmod a+x run.sh generate_nginx.py _git_sync.py

ENV WORKING_DIR=${WORKING_DIR}
# Ensure HOME is set for every process in the container. Required because
# `git config --global` aborts with `fatal: $HOME not set` when HOME is unset,
# and some HA Supervisor container environments do not export it by default.
# Mirrors the run.sh:9 export but applies to _all_ entry points (e.g. when
# this script is invoked directly via docker exec with a cleared env).
ENV HOME=/root
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
