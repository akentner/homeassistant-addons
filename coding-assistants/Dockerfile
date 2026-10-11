ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm
FROM $BUILD_FROM

# System packages (Debian Bookworm) — nodejs is installed separately below
# to pin to Node 24.x via NodeSource (Bookworm's main repo only ships Node 18).
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    openssh-server openssh-client \
    nginx \
    curl wget git jq make \
    ripgrep fd-find fzf bat shellcheck \
    python3 \
    gh \
    tig ncdu btop direnv sqlite3 zoxide unzip \
    fish mc \
    mosquitto-clients \
    ca-certificates \
    locales \
    && sed -i '/en_US.UTF-8/s/^# //' /etc/locale.gen \
    && locale-gen \
    && rm -rf /var/lib/apt/lists/*

# Node.js 24.x via NodeSource — gsd-core@1.12.0 requires Node >=24
# (Debian Bookworm's main repo only ships Node 18, and Debian does not backport newer Node).
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version \
    && npm --version

# yq — not in Debian repos, install from GitHub
RUN YQ_VER=$(curl -sf https://api.github.com/repos/mikefarah/yq/releases/latest | jq -r '.tag_name') \
    && curl -fsSL \
        "https://github.com/mikefarah/yq/releases/download/${YQ_VER}/yq_linux_amd64" \
        -o /usr/local/bin/yq \
    && chmod +x /usr/local/bin/yq

# uv — Python package manager (used for all Python package installs)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -sf /root/.local/bin/uv /usr/local/bin/uv \
    && ln -sf /root/.local/bin/uvx /usr/local/bin/uvx

# Python packages via uv
RUN uv pip install --system --break-system-packages \
    httpie websockets pyyaml python-dotenv paho-mqtt \
    mycli pymysql cryptography

# Debian installs fd as fdfind and bat as batcat — create standard aliases
RUN ln -sf /usr/bin/fdfind /usr/local/bin/fd \
    && ln -sf /usr/bin/batcat /usr/local/bin/bat

# Fisher plugin manager + tide prompt (installed to /root/.config/fish — persisted at runtime)
RUN fish -c "curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source \
    && fisher install jorgebucaran/fisher \
    && fisher install IlanCosman/tide@v6"

# HA API tools
COPY ha-api ha-ws lovelace-sync ha-check-logs ha-check-repairs \
     generate-commit-prompt git-commit-with-ai git-submodule-changes \
     /usr/local/bin/
RUN chmod +x \
    /usr/local/bin/ha-api \
    /usr/local/bin/ha-ws \
    /usr/local/bin/lovelace-sync \
    /usr/local/bin/ha-check-logs \
    /usr/local/bin/ha-check-repairs \
    /usr/local/bin/generate-commit-prompt \
    /usr/local/bin/git-commit-with-ai \
    /usr/local/bin/git-submodule-changes

# Home Assistant CLI — uses $SUPERVISOR_TOKEN injected by HA supervisor
RUN HA_CLI_VER=$(curl -sf https://api.github.com/repos/home-assistant/cli/releases/latest \
        | jq -r .tag_name) \
    && curl -fsSL \
        "https://github.com/home-assistant/cli/releases/download/${HA_CLI_VER}/ha_amd64" \
        -o /usr/local/bin/ha \
    && chmod +x /usr/local/bin/ha

# ttyd — static web terminal binary
RUN TTYD_VER=$(curl -sf https://api.github.com/repos/tsl0922/ttyd/releases/latest \
        | jq -r .tag_name) \
    && curl -fsSL \
        "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VER}/ttyd.x86_64" \
        -o /usr/local/bin/ttyd \
    && chmod +x /usr/local/bin/ttyd

# herdr — terminal workspace manager for coding agents (static release binary, replaces the previous multiplexer).
# CI forwards only the standard build args (BUILD_FROM, VERSION, BUILD_*), so build.yaml args never reach this build:
# the pins live here as ARG defaults and are mirrored 1:1 in build.yaml (internal/verify-coding-assistants.sh, scenario
# `drift`, fails when they diverge). The digests are the GitHub release asset digests of the tag. The architecture
# is picked with `uname -m`; any other value fails the build.
ARG HERDR_VERSION=0.9.3
ARG HERDR_SHA256_X86_64=18a8dc65f1c2fa485884344356dea1cfd911c6f06cf46fa78e193f4087f4dba7
ARG HERDR_SHA256_AARCH64=4de7aa3e25678812e92960de64f7c2aaa1bca1f0f80a3c5e559837e231e1f5c0
RUN ARCH=$(uname -m) \
    && case "${ARCH}" in \
        x86_64) HERDR_SHA256="${HERDR_SHA256_X86_64}" ;; \
        aarch64) HERDR_SHA256="${HERDR_SHA256_AARCH64}" ;; \
        *) echo "herdr: unsupported architecture ${ARCH}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL \
        "https://github.com/herdrdev/herdr/releases/download/v${HERDR_VERSION}/herdr-linux-${ARCH}" \
        -o /usr/local/bin/herdr \
    && echo "${HERDR_SHA256}  /usr/local/bin/herdr" | sha256sum -c - \
    && chmod +x /usr/local/bin/herdr \
    && [ "$(herdr --version | cut -d' ' -f2)" = "${HERDR_VERSION}" ]

# fff-mcp — fast file search MCP server for AI agents (glibc build for Debian)
RUN FFF_VER=$(curl -sf https://api.github.com/repos/dmtrKovalenko/fff/releases/latest \
        | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/dmtrKovalenko/fff/releases/download/v${FFF_VER}/fff-mcp-x86_64-unknown-linux-gnu" \
        -o /usr/local/bin/fff-mcp \
    && chmod +x /usr/local/bin/fff-mcp

# MCP2ZigBee2MQTT — Zigbee2MQTT MCP server for AI assistants (TypeScript, no releases — build from main)
# g++ is the only extra build dep (python3 and make are already installed above)
# hadolint ignore=DL3003,DL3008
RUN apt-get update && apt-get install -y --no-install-recommends g++ \
    && mkdir -p /opt/mcp2zigbee2mqtt \
    && curl -fsSL "https://github.com/ichbinder/MCP2ZigBee2MQTT/archive/refs/heads/main.tar.gz" \
        | tar xz -C /opt/mcp2zigbee2mqtt --strip-components=1 \
    && (cd /opt/mcp2zigbee2mqtt \
        && npm install \
        && npm run build \
        && npm prune --omit=dev) \
    && apt-get purge -y --auto-remove g++ \
    && rm -rf /var/lib/apt/lists/*

# eza — modern ls replacement, glibc build for Debian
RUN EZA_VER=$(curl -sf https://api.github.com/repos/eza-community/eza/releases/latest \
        | jq -r '.tag_name | ltrimstr("v")') \
    && mkdir -p /tmp/eza \
    && curl -fsSL \
        "https://github.com/eza-community/eza/releases/download/v${EZA_VER}/eza_x86_64-unknown-linux-gnu.tar.gz" \
        | tar xz -C /tmp/eza \
    && mv /tmp/eza/eza /usr/local/bin/ \
    && rm -rf /tmp/eza

# delta — git diff pager with syntax highlighting (glibc build)
RUN TAG=$(curl -sf https://api.github.com/repos/dandavison/delta/releases/latest | jq -r '.tag_name') \
    && VER=${TAG#v} \
    && mkdir -p /tmp/delta \
    && curl -fsSL \
        "https://github.com/dandavison/delta/releases/download/${TAG}/delta-${VER}-x86_64-unknown-linux-gnu.tar.gz" \
        | tar xz -C /tmp/delta \
    && mv /tmp/delta/delta-*/delta /usr/local/bin/ \
    && rm -rf /tmp/delta

# difftastic — structural diff (understands syntax), glibc build
RUN mkdir -p /tmp/difft \
    && curl -fsSL \
        "$(curl -sf https://api.github.com/repos/Wilfred/difftastic/releases/latest \
            | jq -r '.assets[] | select(.name | test("^difft-(.+-)?x86_64-unknown-linux-gnu[.]tar[.]gz$")) | .browser_download_url')" \
        | tar xz -C /tmp/difft \
    && mv /tmp/difft/difft /usr/local/bin/ \
    && rm -rf /tmp/difft

# yazi — terminal file manager; glibc release requires GLIBC_2.39 (Bookworm has 2.36), use musl build
RUN YAZI_VER=$(curl -sf https://api.github.com/repos/sxyazi/yazi/releases/latest | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/sxyazi/yazi/releases/download/v${YAZI_VER}/yazi-x86_64-unknown-linux-musl.zip" \
        -o /tmp/yazi.zip \
    && unzip -j /tmp/yazi.zip '*/yazi' '*/ya' -d /usr/local/bin \
    && rm /tmp/yazi.zip

# atuin — shell history with TUI search; glibc release requires GLIBC_2.39 (Bookworm has 2.36), use musl build
RUN ATUIN_VER=$(curl -sf https://api.github.com/repos/atuinsh/atuin/releases/latest | jq -r '.tag_name | ltrimstr("v")') \
    && mkdir -p /tmp/atuin \
    && curl -fsSL \
        "https://github.com/atuinsh/atuin/releases/download/v${ATUIN_VER}/atuin-x86_64-unknown-linux-musl.tar.gz" \
        | tar xz -C /tmp/atuin \
    && mv /tmp/atuin/atuin-*/atuin /usr/local/bin/ \
    && rm -rf /tmp/atuin

# tealdeer — fast tldr client; only musl builds available upstream, but musl binaries work fine on glibc
RUN TLDR_VER=$(curl -sf https://api.github.com/repos/tealdeer-rs/tealdeer/releases/latest | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/tealdeer-rs/tealdeer/releases/download/v${TLDR_VER}/tealdeer-linux-x86_64-musl" \
        -o /usr/local/bin/tldr \
    && chmod +x /usr/local/bin/tldr

# lazygit — Go binary, statically compiled, works everywhere
RUN LG_VER=$(curl -sf https://api.github.com/repos/jesseduffield/lazygit/releases/latest \
        | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/jesseduffield/lazygit/releases/download/v${LG_VER}/lazygit_${LG_VER}_Linux_x86_64.tar.gz" \
        | tar xz -C /usr/local/bin lazygit

# task — taskfile.dev task runner
RUN curl -fsSL https://taskfile.dev/install.sh | sh -s -- -d -b /usr/local/bin

# bun — JavaScript runtime
RUN curl -fsSL https://bun.sh/install | bash \
    && ln -sf /root/.bun/bin/bun /usr/local/bin/bun \
    && ln -sf /root/.bun/bin/bun /usr/local/bin/bunx

# graphify — knowledge graph skill for AI coding assistants
RUN uv tool install graphifyy

# opencode — installed via the official installer so `opencode upgrade` works at runtime.
# The installer hardcodes $HOME/.opencode/bin as its target path, which matches opencode's
# own method-detection heuristic in packages/opencode/src/installation/index.ts. A copy is
# stashed at /opt/opencode-initial/ so run.sh can bootstrap the binary into the persistent
# /data volume on first start; subsequent upgrades persist across container rebuilds.
# --no-modify-path: we manage PATH ourselves in /etc/profile.d/00-coding-assistants.sh.
RUN curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path \
    && mkdir -p /opt/opencode-initial \
    && cp /root/.opencode/bin/opencode /opt/opencode-initial/opencode \
    && ln -sf /root/.opencode/bin/opencode /usr/local/bin/opencode

# Claude Code — native installer (no Node dependency). The installer places the versioned binary in
# /root/.local/share/claude/versions/<ver> and a launcher symlink in /root/.local/bin/claude; both are moved out
# of /root so no per-user state is baked into the image. The single binary (~250 MB) is kept once, as a seed in
# /opt/claude-initial. run.sh seeds it into the persistent /data/.local/share/claude/versions (only when it is
# newer than what is persisted) and re-creates the launcher /root/.local/bin/claude on EVERY start, pointing it
# into that directory. This works because the updater honours XDG_DATA_HOME=/data/.local/share and writes new
# versions to $XDG_DATA_HOME/claude/versions, so `claude update` really replaces the running version and
# survives image rebuilds. This replaces the originally locked /data/claude/bin layout (phase 23, user decision
# 1): with a launcher symlink pointing outside versions/, `claude update` was reproduced as a silent no-op.
# The seed is executed once with --version so a broken download fails the build.
RUN curl -fsSL https://claude.ai/install.sh | bash \
    && mkdir -p /opt/claude-initial \
    && mv /root/.local/share/claude/versions/* /opt/claude-initial/ \
    && set -- /opt/claude-initial/* \
    && [ "$#" -eq 1 ] \
    && "$1" --version \
    && rm -rf /root/.local/bin/claude /root/.local/share/claude /root/.claude /root/.claude.json

# OpenCode + GitHub Copilot CLI + fx JSON viewer + MariaDB/MySQL MCP server via npm
# hadolint ignore=DL3016
RUN npm install -g @github/copilot fx mcp-server-mysql

# herdr plugins (phase 23, plugin review gate 23-PLUGIN-REVIEW.md). Each plugin is checked out at a pinned COMMIT into
# /opt/herdr-plugins/<repository-name>: none of the repositories has a tag, so a tag pin is not possible (D-06). The pins
# are ARG defaults, mirrored 1:1 in build.yaml and compared by `internal/verify-coding-assistants.sh drift`. The commit
# is fetched directly (`git fetch --depth 1 origin <sha>`), checked out detached, and `git rev-parse HEAD` must equal
# the pin or the build fails. `.git` is removed afterwards. run.sh links every directory below /opt/herdr-plugins into
# herdr before the server starts (the plugins' startup hooks run when the server comes up).
# No plugin setup action runs at build time or at runtime, and the add-on writes no herdr config.toml and no Claude
# settings.json (D-02, D-04): wiring such as subagent-watch's key binding or claude-limits' tab-bar entry stays opt-in.
# subagent-watch needs Node >= 22 (NodeSource 24.x above); claude-limits needs jq and curl (installed above).
# These blocks sit after all the download layers on purpose, so a pin bump does not invalidate them.
ARG HERDR_SUBAGENT_WATCH_REF=c47d49b247d8ca3387d88d5bb9731a3b7bf4f6a8
RUN PLUGIN_DIR=/opt/herdr-plugins/herdr-subagent-watch \
    && mkdir -p "${PLUGIN_DIR}" \
    && git -C "${PLUGIN_DIR}" init -q \
    && git -C "${PLUGIN_DIR}" remote add origin https://github.com/silencechung/herdr-subagent-watch.git \
    && git -C "${PLUGIN_DIR}" fetch -q --depth 1 origin "${HERDR_SUBAGENT_WATCH_REF}" \
    && git -C "${PLUGIN_DIR}" -c advice.detachedHead=false checkout -q --detach FETCH_HEAD \
    && [ "$(git -C "${PLUGIN_DIR}" rev-parse HEAD)" = "${HERDR_SUBAGENT_WATCH_REF}" ] \
    && rm -rf "${PLUGIN_DIR}/.git"

ARG HERDR_CLAUDE_LIMITS_REF=9c0c9a1931ac91f9d865031e2dc58d66a7d1b594
RUN PLUGIN_DIR=/opt/herdr-plugins/herdr-claude-limits \
    && mkdir -p "${PLUGIN_DIR}" \
    && git -C "${PLUGIN_DIR}" init -q \
    && git -C "${PLUGIN_DIR}" remote add origin https://github.com/martin-saldinger/herdr-claude-limits.git \
    && git -C "${PLUGIN_DIR}" fetch -q --depth 1 origin "${HERDR_CLAUDE_LIMITS_REF}" \
    && git -C "${PLUGIN_DIR}" -c advice.detachedHead=false checkout -q --detach FETCH_HEAD \
    && [ "$(git -C "${PLUGIN_DIR}" rev-parse HEAD)" = "${HERDR_CLAUDE_LIMITS_REF}" ] \
    && rm -rf "${PLUGIN_DIR}/.git"

# herdr-web-service — fetched like the plugins above, then PATCHED and BUILT here: the stock client hard-codes
# root-absolute URLs (/api/..., /ws, /sw.js, ...) that cannot work behind the HA ingress sub-path (user decision 3), so
# patches/herdr-web-service-subpath.patch (9 client files, no server file) makes every URL relative. The patch was
# validated against exactly this pin by internal/spike-herdr-web-service.sh (23-SPIKE-WEB-SERVICE.md). A build failure at
# `git apply` therefore means the pin moved: re-validate the patch with the spike script before bumping.
# `herdr plugin link` skips the manifest [[build]] steps, so the build runs here: `bun install --frozen-lockfile` (the
# plugin's own lockfile), `bun run build` (vite -> dist/), then the production prune proven in the spike (node_modules
# 148 MB -> 19 MB, server still starts) and removal of the bun install cache. The final asserts fail the build when
# dist/index.html is missing or the built JavaScript still contains a root-absolute /api/, /ws, ... string.
ARG HERDR_WEB_SERVICE_REF=e9082b3fb969064e89153a8c6b2170366982f7f9
COPY patches/herdr-web-service-subpath.patch /tmp/herdr-web-service-subpath.patch
# hadolint ignore=DL3003
RUN PLUGIN_DIR=/opt/herdr-plugins/herdr-web-service \
    && mkdir -p "${PLUGIN_DIR}" \
    && cd "${PLUGIN_DIR}" \
    && git init -q . \
    && git remote add origin https://github.com/i-montes/herdr-web-service.git \
    && git fetch -q --depth 1 origin "${HERDR_WEB_SERVICE_REF}" \
    && git -c advice.detachedHead=false checkout -q --detach FETCH_HEAD \
    && [ "$(git rev-parse HEAD)" = "${HERDR_WEB_SERVICE_REF}" ] \
    && git apply --check /tmp/herdr-web-service-subpath.patch \
    && git apply /tmp/herdr-web-service-subpath.patch \
    && bun install --frozen-lockfile \
    && bun run build \
    && test -f dist/index.html \
    && rm -rf node_modules \
    && bun install --frozen-lockfile --production \
    && rm -rf /root/.bun/install/cache /tmp/herdr-web-service-subpath.patch .git \
    && test -f dist/index.html \
    && if grep -rEq "[\"'\`]/(api/|ws[\"'\`]|sw\\.js|assets/|manifest|icon|apple-touch)" dist --include='*.js'; then \
        echo "herdr-web-service: root-absolute URL left in the built client" >&2; exit 1; \
    fi

# Web UI + nginx config
RUN mkdir -p /opt/coding-assistants
COPY index.html info.html /opt/coding-assistants/
COPY nginx.conf /etc/nginx/nginx.conf

# Tool context for AI assistants
RUN mkdir -p /etc/coding-assistants
COPY TOOLS.md /etc/coding-assistants/TOOLS.md

# SSH config
COPY sshd_config /etc/ssh/sshd_config
RUN mkdir -p /run/sshd

# Attach-or-create wrapper — the only way into the shared herdr session (ttyd and the SSH login hooks call it).
# Kept next to the end of the file on purpose: a change here must not invalidate the download layers above.
COPY coding-assistants-attach /usr/local/bin/coding-assistants-attach
RUN chmod +x /usr/local/bin/coding-assistants-attach

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

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
