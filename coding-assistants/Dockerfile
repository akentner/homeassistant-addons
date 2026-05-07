ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23
FROM $BUILD_FROM

# System packages (Alpine community repo)
RUN apk add --no-cache \
    bash tmux \
    openssh-server openssh-client \
    curl wget git jq yq make \
    nodejs npm \
    ripgrep fd fzf bat shellcheck \
    python3 py3-pip \
    github-cli \
    tig ncdu btop direnv sqlite zoxide unzip \
    fish mc

# Fisher plugin manager + tide prompt (installed to /root/.config/fish — persisted at runtime)
RUN fish -c "curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source \
    && fisher install jorgebucaran/fisher \
    && fisher install IlanCosman/tide@v6"

# hadolint ignore=DL3013
RUN pip install --no-cache-dir --break-system-packages httpie websockets

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

# fff-mcp — fast file search MCP server for AI agents (musl build for Alpine)
RUN FFF_VER=$(curl -sf https://api.github.com/repos/dmtrKovalenko/fff/releases/latest \
        | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/dmtrKovalenko/fff/releases/download/v${FFF_VER}/fff-mcp-x86_64-unknown-linux-musl" \
        -o /usr/local/bin/fff-mcp \
    && chmod +x /usr/local/bin/fff-mcp

# MCP2ZigBee2MQTT — Zigbee2MQTT MCP server for AI assistants (TypeScript, no releases — build from main)
# hadolint ignore=DL3003
RUN apk add --no-cache --virtual .build-mcp2z2m python3 make g++ \
    && mkdir -p /opt/mcp2zigbee2mqtt \
    && curl -fsSL "https://github.com/ichbinder/MCP2ZigBee2MQTT/archive/refs/heads/main.tar.gz" \
        | tar xz -C /opt/mcp2zigbee2mqtt --strip-components=1 \
    && (cd /opt/mcp2zigbee2mqtt \
        && npm ci \
        && npm run build \
        && npm prune --omit=dev) \
    && apk del .build-mcp2z2m

# eza — modern ls replacement, musl build for Alpine
RUN EZA_VER=$(curl -sf https://api.github.com/repos/eza-community/eza/releases/latest \
        | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/eza-community/eza/releases/download/v${EZA_VER}/eza_x86_64-unknown-linux-musl.tar.gz" \
        | tar xz -C /usr/local/bin

# delta — git diff pager with syntax highlighting
RUN TAG=$(curl -sf https://api.github.com/repos/dandavison/delta/releases/latest | jq -r '.tag_name') \
    && VER=${TAG#v} \
    && mkdir -p /tmp/delta \
    && curl -fsSL \
        "https://github.com/dandavison/delta/releases/download/${TAG}/delta-${VER}-x86_64-unknown-linux-musl.tar.gz" \
        | tar xz -C /tmp/delta \
    && mv /tmp/delta/delta-*/delta /usr/local/bin/ \
    && rm -rf /tmp/delta

# difftastic — structural diff (understands syntax)
RUN mkdir -p /tmp/difft \
    && curl -fsSL \
        "$(curl -sf https://api.github.com/repos/Wilfred/difftastic/releases/latest \
            | jq -r '.assets[] | select(.name == "difft-x86_64-unknown-linux-musl.tar.gz") | .browser_download_url')" \
        | tar xz -C /tmp/difft \
    && mv /tmp/difft/difft /usr/local/bin/ \
    && rm -rf /tmp/difft

# yazi — terminal file manager (includes ya companion CLI)
RUN YAZI_VER=$(curl -sf https://api.github.com/repos/sxyazi/yazi/releases/latest | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/sxyazi/yazi/releases/download/v${YAZI_VER}/yazi-x86_64-unknown-linux-musl.zip" \
        -o /tmp/yazi.zip \
    && unzip -j /tmp/yazi.zip '*/yazi' '*/ya' -d /usr/local/bin \
    && rm /tmp/yazi.zip

# atuin — shell history with TUI search
RUN ATUIN_VER=$(curl -sf https://api.github.com/repos/atuinsh/atuin/releases/latest | jq -r '.tag_name | ltrimstr("v")') \
    && mkdir -p /tmp/atuin \
    && curl -fsSL \
        "https://github.com/atuinsh/atuin/releases/download/v${ATUIN_VER}/atuin-x86_64-unknown-linux-musl.tar.gz" \
        | tar xz -C /tmp/atuin \
    && mv /tmp/atuin/atuin-*/atuin /usr/local/bin/ \
    && rm -rf /tmp/atuin

# tealdeer — fast tldr client (simplified man pages)
RUN TLDR_VER=$(curl -sf https://api.github.com/repos/tealdeer-rs/tealdeer/releases/latest | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/tealdeer-rs/tealdeer/releases/download/v${TLDR_VER}/tealdeer-linux-x86_64-musl" \
        -o /usr/local/bin/tldr \
    && chmod +x /usr/local/bin/tldr

# lazygit — Go binary, statically compiled, works on musl
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

# uv — Python package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -sf /root/.local/bin/uv /usr/local/bin/uv \
    && ln -sf /root/.local/bin/uvx /usr/local/bin/uvx

# opencode — musl build from sst/opencode (npm package targets wrong repo)
RUN OPENCODE_VER=$(curl -sfL https://api.github.com/repos/sst/opencode/releases/latest \
        | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/sst/opencode/releases/download/v${OPENCODE_VER}/opencode-linux-x64-musl.tar.gz" \
        | tar xz -C /usr/local/bin \
    && chmod +x /usr/local/bin/opencode

# Coding assistants + fx JSON viewer via npm
# hadolint ignore=DL3016
RUN npm install -g @anthropic-ai/claude-code @github/copilot fx

# Tool context for AI assistants
RUN mkdir -p /etc/coding-assistants
COPY TOOLS.md /etc/coding-assistants/TOOLS.md

# SSH config
COPY sshd_config /etc/ssh/sshd_config

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
