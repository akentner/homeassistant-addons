ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23
FROM $BUILD_FROM

# System packages (Alpine community repo)
RUN apk add --no-cache \
    bash tmux \
    openssh-server \
    curl wget git jq yq make \
    nodejs npm \
    ripgrep fd fzf bat shellcheck \
    python3 py3-pip \
    github-cli

# hadolint ignore=DL3013
RUN pip install --no-cache-dir --break-system-packages httpie

# ttyd — static web terminal binary
RUN TTYD_VER=$(curl -sf https://api.github.com/repos/tsl0922/ttyd/releases/latest \
        | jq -r .tag_name) \
    && curl -fsSL \
        "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VER}/ttyd.x86_64" \
        -o /usr/local/bin/ttyd \
    && chmod +x /usr/local/bin/ttyd

# lazygit — Go binary, statically compiled, works on musl
RUN LG_VER=$(curl -sf https://api.github.com/repos/jesseduffield/lazygit/releases/latest \
        | jq -r '.tag_name | ltrimstr("v")') \
    && curl -fsSL \
        "https://github.com/jesseduffield/lazygit/releases/download/v${LG_VER}/lazygit_${LG_VER}_Linux_x86_64.tar.gz" \
        | tar xz -C /usr/local/bin lazygit

# task — taskfile.dev task runner
RUN curl -fsSL https://taskfile.dev/install.sh | sh -s -- -d -b /usr/local/bin

# bun — JavaScript runtime (BUN_INSTALL=/usr/local puts binaries in /usr/local/bin)
RUN BUN_INSTALL=/usr/local curl -fsSL https://bun.sh/install | bash

# uv — Python package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -sf /root/.local/bin/uv /usr/local/bin/uv \
    && ln -sf /root/.local/bin/uvx /usr/local/bin/uvx

# Coding assistants via npm
# hadolint ignore=DL3016
RUN npm install -g @anthropic-ai/claude-code @github/copilot opencode-ai

# Persist /root/.claude and credentials in /data at runtime via run.sh symlinks
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
