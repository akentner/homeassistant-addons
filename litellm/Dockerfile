# Global ARGs must be declared before first FROM so they can be used in FROM instructions
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie
ARG LITELLM_VERSION
ARG VERSION

# Stage 1: Build wheelhouse + install final Python stack + generate Prisma
# client. node/npm live ONLY here (transitive deps of prisma codegen). The
# discarded builder stage takes the ~340M of libllvm/libicu/libnode/libz3
# with it. Stage 2 ships just the 18M statically-linked engine binary + the
# installed Python packages — verified via `ldd` against the engine binary.
FROM python:3.13-slim-bookworm AS litellm-builder

# Default falls the build workflow does not pass LITELLM_VERSION via --build-arg.
# The repo-wide build.yml workflow only forwards the standard set
# (BUILD_ARCH/BUILD_DATE/BUILD_NAME/BUILD_DESCRIPTION/BUILD_REF/BUILD_REPOSITORY/
# BUILD_VERSION); addon-specific args from build.yaml are not forwarded, so
# this default keeps the build self-sufficient.
ARG LITELLM_VERSION=1.101.0

# Install nodejs + npm in the builder ONLY. `prisma generate` (Python CLI)
# bootstraps a nodevenv internally and runs the JS prisma CLI via npm; that
# node toolchain is discarded with this stage.
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install the final Python stack into /install (custom prefix). Stage 2
# does NOT need pip at runtime — it just COPYs /install into the runtime
# dist-packages dir. Saves ~12M of pip + ~5M of __pycache__ vs. installing
# at runtime via `pip install --find-links=/wheels`. `--target=/install`
# keeps the install isolated, so we can also prune per-package bloat
# (pip's own bootstrap, .pyc files, test fixtures) before the COPY.
#
# We need PYTHONPATH=/install for the subsequent `import litellm` call —
# --target installs to /install but doesn't register it on sys.path.
RUN pip install --no-cache-dir --break-system-packages --target=/install \
        "litellm[proxy]==${LITELLM_VERSION}" \
        "psycopg[binary]==3.2.*" \
        "prisma==0.*" \
    # prisma generate downloads the engine binary to ~/.cache/prisma-python/
    # and writes the generated client into the installed prisma package dir.
    && LITELLM_PRISMA_SCHEMA="$(PYTHONPATH=/install python3 -c "import litellm, os; print(os.path.join(os.path.dirname(litellm.__file__), 'proxy/schema.prisma'))")" \
    && echo "Prisma schema: ${LITELLM_PRISMA_SCHEMA}" \
    && PATH=/install/bin:$PATH PYTHONPATH=/install prisma generate --schema="${LITELLM_PRISMA_SCHEMA}" \
    # Prune the prisma engine cache to ONLY the one binary this image needs.
    # `prisma generate` drops ~134M of variants (openssl-1.1.x, musl,
    # musl-openssl, the .so.node shared lib, the duplicate copies in
    # @prisma/engines/). The runtime only ever invokes the statically-linked
    # `node_modules/prisma/query-engine-debian-openssl-3.0.x` binary
    # (verified via `prisma.client.BINARY_PATHS` — `migrationEngine`,
    # `introspectionEngine`, `libqueryEngine`, `prismaFormat` are all empty,
    # so only query-engine matters). HA base is Debian Trixie with libssl3,
    # matching the openssl-3.0.x variant. Drops ~116M from the runtime image.
    && echo "Pruning engine cache..." \
    && find /root/.cache/prisma-python -type f \
        ! -path '*/node_modules/prisma/query-engine-debian-openssl-3.0.x' \
        -delete \
    && find /root/.cache/prisma-python -type d -empty -delete \
    && echo "Engine cache after prune:" \
    && find /root/.cache/prisma-python -type f -exec du -h {} \; \
    # Drop pip's own bootstrapped deps from /install (we copy the install
    # wholesale to runtime — pip itself isn't needed there). Saves ~5M.
    && find /install -maxdepth 4 -name "pip-*" -prune -exec rm -rf {} + 2>/dev/null \
    && find /install -maxdepth 4 -name "wheel-*" -prune -exec rm -rf {} + 2>/dev/null \
    && find /install -maxdepth 4 -name "pip" -prune -exec rm -rf {} + 2>/dev/null \
    && find /install -maxdepth 4 -name "wheel" -prune -exec rm -rf {} + 2>/dev/null \
    # Drop __pycache__ dirs from the install — Python regenerates them on
    # first import (cheap one-time cost at startup). Saves ~22M.
    && find /install -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null \
    # KEEP *.dist-info dirs! They look like pip-only metadata, but some
    # packages (e.g. pydantic[email]'s `import_email_validator`) introspect
    # sibling dist-info dirs at runtime to discover installed packages.
    # Dropping them breaks proxy startup with `Missing dependency
    # No package metadata was found for email-validator` even though the
    # package code itself is still present. Cost: ~3M; not worth the risk.
    && echo "Install size after prune:" \
    && du -sh /install

# Stage 2: HA Debian base + PGDG-postgres-16 + LiteLLM (slim runtime)
FROM ${BUILD_FROM}

ARG VERSION
ARG LITELLM_VERSION=1.101.0

WORKDIR /

# Runtime apt deps. NO nodejs / npm / libllvm / libicu / libz3 (those are
# only needed in the builder for `prisma generate`). NO python3-pip —
# we copy the installed packages from the builder instead of installing
# from wheels at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
        > /etc/apt/list.d/pgdg.list 2>/dev/null || \
       echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        postgresql-16 \
        postgresql-client-16 \
        jq \
        bash \
        libssl3 \
        libffi8 \
        python3 \
        valkey-server \
    # Purge everything we don't need at runtime.
    #
    # perl-base + perl: pulled in transitively via postgresql-16 (plperl
    # optional dep). No service in this image links libperl, so safe to drop
    # (~13M). Note: Trixie's package name is `perl-base` (not `libperl5.40`
    # as on older Debian — naming changed).
    #
    # gnupg + gpg-agent + gnupg-l10n + dirmngr: only used at build to
    # dearmor the postgres repo key. No runtime signature verification
    # happens in this image (~10M).
    #
    # sqv: OpenPGP signature verifier from the sequoia suite — pulled in
    # by the HA base image, never invoked here (~2M).
    #
    # tempio: s6-overlay service-config templating tool — used at HA base
    # build time, never invoked at runtime (~7M).
    && apt-get purge -y --auto-remove \
        perl-base perl \
        gnupg gnupg-l10n gpg gpg-agent dirmngr \
        sqv tempio \
        2>/dev/null || true \
    # postgresql-client-16 ships 21 client binaries (psql, createdb,
    # pg_dump, …) as symlinks to /usr/share/postgresql-common/pg_wrapper —
    # a Perl script that picks the right cluster version based on env
    # vars or /etc/postgresql-common/user_clusters. We deleted Perl, so
    # every pg_* invocation dies with 'cannot execute: required file
    # not found'. We don't use multi-cluster features (only one cluster
    # ever, the local /data/postgresql), so re-point each symlink at the
    # real binary under /usr/lib/postgresql/16/bin/. This is what
    # `update-alternatives --remove pg_wrapper ...` does internally on
    # a Debian system without postgresql-common, just done explicitly
    # since we deleted the package.
    && for tool in psql createdb createuser dropdb clusterdb \
                  pg_dump pg_dumpall pg_restore pg_isready pg_basebackup \
                  vacuumdb reindexdb pgbench pg_archivecleanup \
                  pg_receivewal pg_recvlogical createlang droplang \
                  pg_receivexlog; do \
           ln -sf /usr/lib/postgresql/16/bin/${tool} /usr/bin/${tool}; \
       done \
    # Disable Postgres JIT. PGDG postgresql-16 depends on libllvm19 (124M)
    # + libz3-4 (27M) for the llvmjit provider, which dynamically loads
    # libLLVM.so at runtime when JIT-compiling expressions. For our homelab
    # use case (HA Conversation proxy, ~10s of QPS) JIT is unnecessary; the
    # default `jit = on` setting would mean paying 151M of disk for a
    # feature that runs a few hundred microseconds faster per query. Setting
    # `jit = off` + deleting the JIT provider lets us drop libllvm19 +
    # libz3-4 + llvmjit.so safely (verified via initdb + pg_ctl start with
    # the libs deleted). We also delete libxml2 (~1.8M) — it's a dynamic
    # dep of the postgres binary, but the linker only resolves it when
    # XML functions are actually called (verified: pg starts cleanly without
    # it because we never invoke xml2 / xpath).
    && sed -i 's/^#jit = on/jit = off/' /etc/postgresql/16/main/postgresql.conf \
    && rm -f /usr/lib/x86_64-linux-gnu/libLLVM.so.19.1 \
        /usr/lib/x86_64-linux-gnu/libLLVM-19.so \
        /usr/lib/x86_64-linux-gnu/libz3.so.4 \
        /usr/lib/x86_64-linux-gnu/libxml2.so.2 \
        /usr/lib/postgresql/16/lib/llvmjit.so \
        /usr/lib/postgresql/16/lib/llvmjit_types.bc \
    && rm -rf /usr/lib/postgresql/16/lib/bitcode \
    && ldconfig \
    # The apt-get purge above silently no-ops if a package isn't installed
    # (apt returns 0 with a warning we ignore). dpkg is also gone after our
    # purge, so we have to delete the residual files directly:
    #
    #   - perl-base (5.1M) + perl (26M) + /usr/bin/perl (3.8M): pulled in
    #     transitively by postgresql-16 for plperl, which we don't use.
    #   - gpg / gpg-agent / gpgsm / dirmngr + /usr/lib/gnupg (4M): pulled in
    #     by the HA base image, only invoked during the build to dearmor
    #     the postgres repo key. No runtime verification in this image.
    #   - sqv (1.8M): OpenPGP sig verifier from sequoia, never invoked.
    #   - tempio (6.1M): s6-overlay config templating tool, never invoked
    #     at runtime — used by HA base image build only.
    #   - /var/lib/postgresql/16/main (39M): pre-init'd DB templates that
    #     the postgresql-16 package creates during its postinst. run.sh
    #     uses /data/postgresql for the actual data dir, so this is dead.
    && rm -rf /usr/bin/perl /usr/bin/perl5.40.1 \
        /usr/lib/x86_64-linux-gnu/perl /usr/lib/x86_64-linux-gnu/perl-base \
        /usr/share/perl /usr/share/perl5 /usr/lib/x86_64-linux-gnu/libperl.so.5.40.1 \
        /usr/bin/gpg /usr/bin/gpg-agent /usr/bin/gpgsm /usr/bin/dirmngr /usr/bin/sqv /usr/bin/tempio \
        /usr/lib/gnupg \
        /var/lib/postgresql/16/main \
        # i18n/locale data (16M) + glibc gconv (8.2M): only used when PG
        # needs locale-aware collation. We initdb with `--locale=C`, which
        # needs neither (verified via initdb + pg start with both dirs
        # absent). C.utf8 collations are baked into glibc itself.
        /usr/share/i18n /usr/lib/x86_64-linux-gnu/gconv \
        # dpkg + apt: package manager tools, only used at build. They pull
        # in `libapt-pkg.so.7.0.0` (2.5M) + several dpkg-* helpers. Drop
        # wholesale (~3M).
        /usr/bin/dpkg /usr/bin/dpkg-deb /usr/bin/dpkg-query \
        /usr/bin/dpkg-divert /usr/bin/dpkg-maintscript-helper /usr/bin/dpkg-realpath \
        /usr/bin/dpkg-split /usr/bin/dpkg-statoverride /usr/bin/dpkg-trigger \
        /usr/lib/x86_64-linux-gnu/libapt-pkg.so.7.0.0 \
        # localedef: locale-compiler CLI. Not invoked at runtime — we use
        # the C locale throughout, and locales are pre-compiled by the
        # base image. Drop (~300K).
        /usr/bin/localedef \
        # valkey-check-rdb / valkey-check-aof: valkey diagnostic tools,
        # never invoked at runtime (~6M).
        /usr/bin/valkey-check-rdb /usr/bin/valkey-check-aof \
        # valkey-benchmark: not invoked at runtime (~600K).
        /usr/bin/valkey-benchmark \
        # openssl CLI: NOT removable — run.sh uses `openssl rand -hex`
        # to generate the master/salt key + postgres password on first
        # start. Re-add here if you ever decide to inline-key those instead.
        # curl: NOT removable — bashio internally calls `curl` to contact
        # the HA Supervisor API (visible in /usr/lib/bashio/api.sh line 47)
        # for option loading. Without it, every bashio::config call fails.
        # Both stay. Libssl3/libcrypto stay for dynamic linking too.
    && rm -rf /var/lib/apt/lists/* /var/cache/* /var/lib/apt /var/lib/dpkg \
        /var/lib/systemd /var/lib/apt \
        # Drop man pages, docs, and other static documentation
        /usr/share/doc /usr/share/man /usr/share/info \
        /usr/share/lintian /usr/share/linda /usr/share/groff \
        /usr/share/bash-completion \
        # Drop Python stdlib bloat (test, pydoc, lib2to3, idle, tkinter, ensurepip)
        /usr/lib/python3.13/test /usr/lib/python3.13/__pycache__ \
        /usr/lib/python3.13/pydoc_data /usr/lib/python3.13/lib2to3 \
        /usr/lib/python3.13/idlelib /tkinter /ensurepip \
        /usr/lib/python3/dist-packages/pip /usr/lib/python3/dist-packages/pip-*.dist-info \
        /usr/lib/python3/dist-packages/wheel /usr/lib/python3/dist-packages/wheel-*.dist-info \
        /usr/lib/python3/dist-packages/__pycache__ \
        # Drop unused Debian locales (only C.utf8 remains after the purge anyway)
        /usr/share/locale /usr/lib/locale

# COPY the full installed Python stack from the builder. The builder ran
# `pip install --target=/install` and pruned __pycache__/dist-info/test
# fixtures — so /install is just the importable .py files + native
# extensions. Runtime's /usr/local/lib/python3.13/dist-packages is empty
# at this point (HA base doesn't ship pip-installed packages), so COPY
# creates it fresh.
COPY --from=litellm-builder /install /usr/local/lib/python3.13/dist-packages

# Engine binary — written by `prisma generate` into /root/.cache/prisma-python.
# Prisma Python looks it up via `BINARY_PATHS.query_engine` at import time
# (the path is hardcoded in the generated `prisma/client.py`).
COPY --from=litellm-builder /root/.cache/prisma-python /root/.cache/prisma-python

# run_litellm.py wraps litellm's ProxyServer.setup_csp_headers() so HA
# Supervisor ingress iframes aren't blocked by litellm's hardcoded
# `frame-ancestors 'none'` (upstream source: litellm/proxy/proxy_server.py
# in the 1.101.0 tag — no upstream config knob to override it). run.sh
# exports $INGRESS_ORIGIN before invoking this script.
COPY run_litellm.py /app/run_litellm.py
RUN chmod +x /app/run_litellm.py

# Sidebar + Apps-overview icon. HA Supervisor auto-detects icon.png
# at the add-on root if present (network-tools, gatus, meridian all
# ship one). 256x256 PNG, transparent BG, neural-net theme.
COPY icon.png /app/icon.png
# HA reads the icon from a well-known path inside the addon_data
# mount (not from /app). Symlink so HA finds it.
RUN mkdir -p /data && ln -sf /app/icon.png /data/icon.png

# Add-on startup script
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 4000

CMD ["/run.sh"]

# ### LABELS (full OCI label block per authentik/Dockerfile lines 78-103)
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
