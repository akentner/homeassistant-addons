ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm
FROM $BUILD_FROM

# System packages (Debian Bookworm)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash tmux \
    openssh-server openssh-client \
    nginx \
    curl wget git jq make \
    nodejs npm \
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
RUN uv pip install --system --break-system-packages httpie websockets pyyaml python-dotenv paho-mqtt

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
            | jq -r '.assets[] | select(.name == "difft-x86_64-unknown-linux-gnu.tar.gz") | .browser_download_url')" \
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
    && cp /root/.opencode/bin/opencode /opt/opencode-initial/opencode

# Coding assistants + fx JSON viewer via npm
# hadolint ignore=DL3016
RUN npm install -g @anthropic-ai/claude-code @github/copilot fx

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

# System-wide tmux config
COPY tmux.conf /etc/tmux.conf

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
