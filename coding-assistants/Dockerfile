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

# Pinned GitHub release tools (yq, ha CLI, ttyd, fff-mcp, eza, delta, difftastic, yazi, atuin, tealdeer, lazygit).
# No GitHub API call at build time: the unauthenticated API is rate limited on shared CI runners and returned an empty
# tag (curl exit 22). Every tool is an ARG version plus the SHA256 of its x86_64 asset (the add-on builds for amd64
# only); the ARG defaults are mirrored 1:1 in build.yaml (verify scenario `drift`). Renovate bumps the *_VERSION values;
# on Renovate PRs the workflow refresh-pins.yml refreshes the digests (internal/refresh-pins-ci.sh, which runs
# internal/update-*-pins.sh) and pushes to the branch; run that script by hand only for non-Renovate bumps. A digest
# mismatch fails the build.

# yq — not in Debian repos, install from GitHub
ARG YQ_VERSION=4.54.3
ARG YQ_SHA256_X86_64=129534601871538efe0ba4c5e62a34fb1d5f469bcb975c4fddeb467d82974973
RUN curl -fsSL "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_amd64" -o /usr/local/bin/yq \
    && echo "${YQ_SHA256_X86_64}  /usr/local/bin/yq" | sha256sum -c - \
    && chmod +x /usr/local/bin/yq \
    && [ "$(yq --version | grep -oE '[0-9]+[.][0-9]+[.][0-9]+' | head -n 1)" = "${YQ_VERSION}" ]

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
     generate-commit-prompt git-commit-with-ai git-submodule-changes codex-mcp-merge \
     /usr/local/bin/
RUN chmod +x \
    /usr/local/bin/ha-api \
    /usr/local/bin/ha-ws \
    /usr/local/bin/lovelace-sync \
    /usr/local/bin/ha-check-logs \
    /usr/local/bin/ha-check-repairs \
    /usr/local/bin/codex-mcp-merge \
    /usr/local/bin/generate-commit-prompt \
    /usr/local/bin/git-commit-with-ai \
    /usr/local/bin/git-submodule-changes

# Home Assistant CLI — uses $SUPERVISOR_TOKEN injected by HA supervisor
ARG HA_CLI_VERSION=6.0.0
ARG HA_CLI_SHA256_X86_64=faab39046723cb68d43e9d5c8ac5a2cf105f3ecb3f5c8a01c0999c2699c56489
RUN curl -fsSL "https://github.com/home-assistant/cli/releases/download/${HA_CLI_VERSION}/ha_amd64" -o /usr/local/bin/ha \
    && echo "${HA_CLI_SHA256_X86_64}  /usr/local/bin/ha" | sha256sum -c - \
    && chmod +x /usr/local/bin/ha

# ttyd — static web terminal binary
ARG TTYD_VERSION=1.7.7
ARG TTYD_SHA256_X86_64=8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55
RUN curl -fsSL "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.x86_64" -o /usr/local/bin/ttyd \
    && echo "${TTYD_SHA256_X86_64}  /usr/local/bin/ttyd" | sha256sum -c - \
    && chmod +x /usr/local/bin/ttyd

# herdr — terminal workspace manager for coding agents (static release binary, replaces the previous multiplexer).
# CI forwards only the standard build args (BUILD_FROM, VERSION, BUILD_*), so build.yaml args never reach this build:
# the pins live here as ARG defaults and are mirrored 1:1 in build.yaml (internal/verify-coding-assistants.sh, scenario
# `drift`, fails when they diverge). The digests are the GitHub release asset digests of the tag. The architecture
# is picked with `uname -m`; any other value fails the build.
ARG HERDR_VERSION=0.9.5
ARG HERDR_SHA256_X86_64=14d9e8bc8b4a9e0118d77c32266f76d461f09b40342eb23752960bd89f59929d
ARG HERDR_SHA256_AARCH64=17d7536f2da50859523680ef279dffcac8e4a235f4e46fe8da6c2ec44141897c
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
ARG FFF_VERSION=0.11.0
ARG FFF_SHA256_X86_64=1b645947cfa086f8080cd6419899e32cb2c531b122618c1141d9155e449ce647
RUN curl -fsSL \
        "https://github.com/dmtrKovalenko/fff/releases/download/v${FFF_VERSION}/fff-mcp-x86_64-unknown-linux-gnu" \
        -o /usr/local/bin/fff-mcp \
    && echo "${FFF_SHA256_X86_64}  /usr/local/bin/fff-mcp" | sha256sum -c - \
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
ARG EZA_VERSION=0.23.5
ARG EZA_SHA256_X86_64=35c70c5c43c29108075e58b893234c67ef585f0b53a7eaf8e9e7d4eec9f339b4
RUN mkdir -p /tmp/eza \
    && curl -fsSL \
        "https://github.com/eza-community/eza/releases/download/v${EZA_VERSION}/eza_x86_64-unknown-linux-gnu.tar.gz" \
        -o /tmp/eza/eza.tar.gz \
    && echo "${EZA_SHA256_X86_64}  /tmp/eza/eza.tar.gz" | sha256sum -c - \
    && tar xzf /tmp/eza/eza.tar.gz -C /tmp/eza \
    && mv /tmp/eza/eza /usr/local/bin/ \
    && rm -rf /tmp/eza

# delta — git diff pager with syntax highlighting (glibc build)
ARG DELTA_VERSION=0.21.2
ARG DELTA_SHA256_X86_64=5d41046c4ada17e7d080e1e5dbbd46544146bb5597e2ab56881a8c594272cd06
RUN mkdir -p /tmp/delta \
    && curl -fsSL \
        "https://github.com/dandavison/delta/releases/download/${DELTA_VERSION}/delta-${DELTA_VERSION}-x86_64-unknown-linux-gnu.tar.gz" \
        -o /tmp/delta/delta.tar.gz \
    && echo "${DELTA_SHA256_X86_64}  /tmp/delta/delta.tar.gz" | sha256sum -c - \
    && tar xzf /tmp/delta/delta.tar.gz -C /tmp/delta \
    && mv /tmp/delta/delta-*/delta /usr/local/bin/ \
    && rm -rf /tmp/delta

# difftastic — structural diff (understands syntax), glibc build
ARG DIFFTASTIC_VERSION=0.72.0
ARG DIFFTASTIC_SHA256_X86_64=33ea1f003081e9f2422299a434e6040c89085bd9f102b08f3fe30393720d5d4a
RUN mkdir -p /tmp/difft \
    && curl -fsSL \
        "https://github.com/Wilfred/difftastic/releases/download/${DIFFTASTIC_VERSION}/difft-${DIFFTASTIC_VERSION}-x86_64-unknown-linux-gnu.tar.gz" \
        -o /tmp/difft/difft.tar.gz \
    && echo "${DIFFTASTIC_SHA256_X86_64}  /tmp/difft/difft.tar.gz" | sha256sum -c - \
    && tar xzf /tmp/difft/difft.tar.gz -C /tmp/difft \
    && mv /tmp/difft/difft /usr/local/bin/ \
    && rm -rf /tmp/difft

# yazi — terminal file manager; glibc release requires GLIBC_2.39 (Bookworm has 2.36), use musl build
ARG YAZI_VERSION=26.9.1
ARG YAZI_SHA256_X86_64=9b9c39decccf8cb0ff53a7d637d38f8a79d93bbd0099f4ea9c619ef6bb392f5d
RUN curl -fsSL \
        "https://github.com/sxyazi/yazi/releases/download/v${YAZI_VERSION}/yazi-x86_64-unknown-linux-musl.zip" \
        -o /tmp/yazi.zip \
    && echo "${YAZI_SHA256_X86_64}  /tmp/yazi.zip" | sha256sum -c - \
    && unzip -j /tmp/yazi.zip '*/yazi' '*/ya' -d /usr/local/bin \
    && rm /tmp/yazi.zip

# atuin — shell history with TUI search; glibc release requires GLIBC_2.39 (Bookworm has 2.36), use musl build
ARG ATUIN_VERSION=18.25.0
ARG ATUIN_SHA256_X86_64=9ebfb49d9f5cc5fb03588315f8f54277fe9e3648bd98de7666a350000670cd19
RUN mkdir -p /tmp/atuin \
    && curl -fsSL \
        "https://github.com/atuinsh/atuin/releases/download/v${ATUIN_VERSION}/atuin-x86_64-unknown-linux-musl.tar.gz" \
        -o /tmp/atuin/atuin.tar.gz \
    && echo "${ATUIN_SHA256_X86_64}  /tmp/atuin/atuin.tar.gz" | sha256sum -c - \
    && tar xzf /tmp/atuin/atuin.tar.gz -C /tmp/atuin \
    && mv /tmp/atuin/atuin-*/atuin /usr/local/bin/ \
    && rm -rf /tmp/atuin

# tealdeer — fast tldr client; only musl builds available upstream, but musl binaries work fine on glibc
ARG TEALDEER_VERSION=1.9.1
ARG TEALDEER_SHA256_X86_64=5a9c3f0691b9cf375ee5c99de802885f3d50498cf686a539e2ddda028eb6b4f6
RUN curl -fsSL \
        "https://github.com/tealdeer-rs/tealdeer/releases/download/v${TEALDEER_VERSION}/tealdeer-linux-x86_64-musl" \
        -o /usr/local/bin/tldr \
    && echo "${TEALDEER_SHA256_X86_64}  /usr/local/bin/tldr" | sha256sum -c - \
    && chmod +x /usr/local/bin/tldr

# lazygit — Go binary, statically compiled, works everywhere
ARG LAZYGIT_VERSION=0.66.3
ARG LAZYGIT_SHA256_X86_64=0a23f429a95f0d09db298b3c291536d818de066aa5a85c255806f0490ff6656b
RUN curl -fsSL \
        "https://github.com/jesseduffield/lazygit/releases/download/v${LAZYGIT_VERSION}/lazygit_${LAZYGIT_VERSION}_linux_x86_64.tar.gz" \
        -o /tmp/lazygit.tar.gz \
    && echo "${LAZYGIT_SHA256_X86_64}  /tmp/lazygit.tar.gz" | sha256sum -c - \
    && tar xzf /tmp/lazygit.tar.gz -C /usr/local/bin lazygit \
    && rm /tmp/lazygit.tar.gz

# task — taskfile.dev task runner
RUN curl -fsSL https://taskfile.dev/install.sh | sh -s -- -d -b /usr/local/bin

# bun — JavaScript runtime
RUN curl -fsSL https://bun.sh/install | bash \
    && ln -sf /root/.bun/bin/bun /usr/local/bin/bun \
    && ln -sf /root/.bun/bin/bun /usr/local/bin/bunx

# graphify — knowledge graph skill for AI coding assistants
RUN uv tool install graphifyy

# opencode 2 — pinned release binary (glibc build, runs on Bookworm). The 1.x installer (opencode.ai/install) refuses
# 2.x, so the binary is fetched from the GitHub release instead. The ARG defaults are mirrored 1:1 in build.yaml
# (verify scenario `drift`); the digests are the GitHub release asset digests of tag v<version>. Renovate bumps
# OPENCODE_VERSION only: refresh the digests with internal/update-opencode-pins.sh.
# The binary is placed where the official installer (and `opencode upgrade`) writes it, $HOME/.opencode/bin, and a copy is
# stashed at /opt/opencode-initial/ so run.sh can seed it into the persistent /data volume (only when it is newer than
# what is persisted); user-initiated upgrades persist across container rebuilds.
ARG OPENCODE_VERSION=2.3.2
ARG OPENCODE_SHA256_X86_64=563b5d663637226b6e3bb4bb6803281bc39b0d2cd88db06d674b6420aab009b0
ARG OPENCODE_SHA256_AARCH64=9d10185acdb72336e086e699ca363a6065f410fd3c1caed0dc8046e95ac06ccb
RUN ARCH=$(uname -m) \
    && case "${ARCH}" in \
        x86_64) OPENCODE_ASSET="opencode-linux-x64"; OPENCODE_SHA256="${OPENCODE_SHA256_X86_64}" ;; \
        aarch64) OPENCODE_ASSET="opencode-linux-arm64"; OPENCODE_SHA256="${OPENCODE_SHA256_AARCH64}" ;; \
        *) echo "opencode: unsupported architecture ${ARCH}" >&2; exit 1 ;; \
    esac \
    && mkdir -p /tmp/opencode /root/.opencode/bin /opt/opencode-initial \
    && curl -fsSL \
        "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/${OPENCODE_ASSET}.tar.gz" \
        -o /tmp/opencode/opencode.tar.gz \
    && echo "${OPENCODE_SHA256}  /tmp/opencode/opencode.tar.gz" | sha256sum -c - \
    && tar xzf /tmp/opencode/opencode.tar.gz -C /tmp/opencode \
    && install -m 0755 /tmp/opencode/opencode /root/.opencode/bin/opencode \
    && cp /root/.opencode/bin/opencode /opt/opencode-initial/opencode \
    && ln -sf /root/.opencode/bin/opencode /usr/local/bin/opencode \
    && rm -rf /tmp/opencode \
    && [ "$(opencode --version | grep -oE '[0-9]+[.][0-9]+[.][0-9]+' | head -n 1)" = "${OPENCODE_VERSION}" ]

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

# OpenAI Codex CLI — complete musl release package (no Node needed). Pinned like herdr: ARG defaults are mirrored 1:1
# in build.yaml (verify scenario `drift`); the digests are the GitHub release asset digests of tag rust-v<version>.
# Renovate bumps CODEX_VERSION only — refresh the digests with internal/update-codex-pins.sh. Keep the package layout:
# bin/ contains the CLI and tool hosts; codex-resources/ includes bubblewrap. State lives in CODEX_HOME=/data/.codex.
ARG CODEX_VERSION=0.171.0
ARG CODEX_SHA256_X86_64=8391d67757496bfd14893eca6cbf0c96994bf2627566ff1f018f70600c9ef6b3
ARG CODEX_SHA256_AARCH64=d8c43bee6cf11b01eb18b95f4d7961092bc40228180808859e70dabb7784c1c9
RUN ARCH=$(uname -m) \
    && case "${ARCH}" in \
        x86_64) CODEX_SHA256="${CODEX_SHA256_X86_64}" ;; \
        aarch64) CODEX_SHA256="${CODEX_SHA256_AARCH64}" ;; \
        *) echo "codex: unsupported architecture ${ARCH}" >&2; exit 1 ;; \
    esac \
    && ASSET="codex-package-${ARCH}-unknown-linux-musl" \
    && mkdir -p /tmp/codex \
    && curl -fsSL \
        "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/${ASSET}.tar.gz" \
        -o /tmp/codex/codex.tar.gz \
    && echo "${CODEX_SHA256}  /tmp/codex/codex.tar.gz" | sha256sum -c - \
    && tar xzf /tmp/codex/codex.tar.gz -C /tmp/codex \
    && mkdir -p /opt/codex \
    && cp -a /tmp/codex/bin /tmp/codex/codex-path /tmp/codex/codex-resources \
        /tmp/codex/codex-package.json /opt/codex/ \
    && ln -s /opt/codex/bin/codex /usr/local/bin/codex \
    && ln -s /opt/codex/bin/codex-code-mode-host /usr/local/bin/codex-code-mode-host \
    && ln -s /opt/codex/bin/codex-exec-server /usr/local/bin/codex-exec-server \
    && test -x /opt/codex/codex-resources/bwrap \
    && test -x /usr/local/bin/codex-code-mode-host \
    && test -x /usr/local/bin/codex-exec-server \
    && rm -rf /tmp/codex \
    && [ "$(codex --version | awk '{print $NF}')" = "${CODEX_VERSION}" ]

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
COPY index.html info.html icon.png /opt/coding-assistants/
COPY app/web/static/ /opt/coding-assistants/static/
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
