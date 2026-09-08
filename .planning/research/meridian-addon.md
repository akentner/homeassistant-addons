# Meridian HA Add-on Research

_Researched: 2026-04-03_

## Summary

Meridian (https://github.com/rynfar/meridian) publishes GitHub Releases and can be fetched via git archive or source
tarball at build time. The app is a TypeScript/Bun project that compiles to Node.js — the HA base image
(`ghcr.io/home-assistant/amd64-base`) is Alpine-based and does not include Node.js, so Node.js must be installed via
`apk`. Claude Code stores its OAuth token in `~/.claude/` (the home directory of the user running the process); in the
container this must be symlinked or redirected to `/data` for persistence. The `claude login` OAuth flow requires an
interactive terminal and cannot run headlessly, so it must be done once via the HA terminal add-on.

## Findings

### 1. Does Meridian Publish GitHub Releases?

Yes. Meridian publishes frequent GitHub Releases via a `release-please` workflow. As of 2026-04-03, the latest is
v1.26.5. Releases are created automatically by `github-actions[bot]` with verified GPG signatures. Each release has 2
assets (the auto-generated source tarball and zip from GitHub). **There are no pre-compiled binary assets** — only
source archives.

The release cadence is very high: multiple releases per day are common (v1.26.0 through v1.26.5 all on April 3, 2026).
This makes daily auto-update polling appropriate — it will catch the latest release of the day without tracking every
micro-release.

Source archive URL pattern:

```
https://github.com/rynfar/meridian/archive/refs/tags/v{VERSION}.tar.gz
```

This follows the same pattern used by the existing `phone-logger` add-on.

### 2. What HA Base Image Fits Best?

**There is no official Node.js-specific HA base image.** The `ghcr.io/home-assistant/` registry provides
architecture-specific Alpine images:

- `ghcr.io/home-assistant/amd64-base:{tag}` — Alpine Linux (no Node.js)
- `ghcr.io/home-assistant/aarch64-base:{tag}` — same, ARM64
- `ghcr.io/home-assistant/armv7-base:{tag}` — same, ARMv7

The community `ghcr.io/hassio-addons/base` images (used by the Node-RED add-on) are also generic Alpine, not
Node.js-specific.

**Recommended approach: use `ghcr.io/home-assistant/amd64-base` and install Node.js 22 via `apk`.**

Alpine's package repository includes `nodejs` and `npm`. For Node.js 22 specifically (required by Meridian's
`package.json`: `"node": ">=22"`), check Alpine version compatibility. Alpine 3.21+ includes Node.js 22.x in the
community repo. The current HA base image version `3.23` maps to Alpine 3.23 which includes Node.js 22.

```dockerfile
RUN apk add --no-cache nodejs npm
```

**Alternative: multi-stage build using `oven/bun:1` for build, then `ghcr.io/home-assistant/amd64-base` for runtime.**
This is the correct approach since Meridian's Dockerfile already does this — it builds TypeScript with Bun, then runs
the compiled output with Node.js. The HA add-on Dockerfile would mirror this structure.

### 3. How Do Other HA Add-ons Handle Node.js Apps?

The Node-RED HA add-on (`hassio-addons/addon-node-red`) uses `ghcr.io/hassio-addons/base:20.0.2` and installs Node.js
from Alpine's apk repos. It does not use a dedicated Node.js base image. This confirms the standard pattern: Alpine
base + `apk add nodejs npm`.

The hassio-addons community base (`ghcr.io/hassio-addons/base`) is functionally equivalent to the official HA base
images for this purpose — both are Alpine-based. Using the official `ghcr.io/home-assistant/` image is preferred for
consistency with the existing add-ons in this repo.

### 4. How Does `claude login` Work in a Container?

**Credential storage location:** The `claude login` command (from `@anthropic-ai/claude-code` npm package) stores the
OAuth token in `~/.claude/` relative to the home directory of the process user. In Meridian's upstream Dockerfile, the
user is named `claude` with UID 1000, so credentials live at `/home/claude/.claude/`.

Meridian's Docker example confirms this:

```bash
docker run -v ~/.claude:/home/claude/.claude -p 3456:3456 meridian
```

**The OAuth flow is interactive.** `claude login` opens a browser and requires the user to approve in a web browser,
then pastes a code back. This cannot be automated — it must be done once by the user via the HA terminal.

**Persistence via /data:** HA add-ons get a persistent `/data` volume automatically. The strategy is:

1. At container startup (`run.sh`), check if `/data/.claude` exists
2. If yes, symlink `/root/.claude -> /data/.claude` (or whichever user runs the process)
3. If no, print instructions to run `claude login` via the HA terminal

**User in container:** Unlike Meridian's upstream Dockerfile which creates a `claude` user, HA add-ons typically run as
root (the HA supervisor handles security). Using root simplifies the path: credentials go to `/root/.claude`, symlinked
from `/data/.claude`.

**Token refresh:** Meridian handles automatic token refresh internally via its `refresh-token` mechanism. The token
expires roughly every 8 hours, but Meridian detects this and refreshes automatically. No manual intervention needed
after initial login.

### 5. Meridian Repo Structure — What Files Are Needed?

Meridian's build process:

- **Build stage:** `oven/bun:1` — installs deps, compiles TypeScript
  - Input: `package.json`, `package-lock.json`, `bun.lock`, `tsconfig.json`, `tsconfig.build.json`, `src/`, `bin/`
  - Output: `dist/` with compiled JS bundles
- **Runtime stage:** `node:22-alpine`
  - Needs: `dist/` from build stage, `node_modules/` (production only), `@anthropic-ai/claude-code` (installed globally
    via npm), shell scripts

The source tarball from GitHub contains all of the above. The HA add-on Dockerfile needs to:

1. Download and extract the source tarball (like `phone-logger` does)
2. Run `bun install && bun run build` in a build stage (using `oven/bun:1`)
3. Copy compiled output to the HA base image runtime stage
4. Install `@anthropic-ai/claude-code` globally via npm in the runtime stage
5. Add `run.sh` from the add-on repo (overrides any upstream placeholder)

**Key dependency:** `@anthropic-ai/claude-code` must be installed globally (not in the project's `node_modules`) — this
is how Meridian's upstream Dockerfile works, and it's what provides the `claude` binary used for authentication checks
and the SDK.

Production runtime dependencies from `package.json`:

- `@anthropic-ai/claude-agent-sdk` (^0.2.89) — listed as the sole production dep
- `@hono/node-server`, `hono` — listed as devDependencies but used at runtime (since Bun bundles them into `dist/`)

Since Bun bundles everything into `dist/`, the runtime stage may not need `node_modules/` at all — the compiled output
is self-contained. This needs to be verified against the actual build output.

### 6. Port and Network Configuration

- Meridian binds to port 3456 by default (configurable via `MERIDIAN_PORT` env var)
- Default host is `127.0.0.1` — **this must be changed to `0.0.0.0` in the HA add-on** for the port to be accessible
  from outside the container. Set `MERIDIAN_HOST=0.0.0.0` in the Dockerfile or `run.sh`.
- Health check: `GET /health` returns 200 when ready (confirmed in README)
- HA `config.yaml` must expose port 3456

### 7. `ingress` vs Direct Port Exposure

Meridian acts as an API endpoint that tools like Cline or Continue.dev call directly via
`ANTHROPIC_BASE_URL=http://homeassistant.local:3456`. HA ingress (reverse proxy through the HA UI) adds path prefixes
and auth headers that would break standard Anthropic API clients. **Use direct port exposure**, not ingress.

## Recommended Approach

**Multi-stage Dockerfile** following Meridian's upstream pattern, adapted for HA:

```dockerfile
# Stage 1: Build with Bun
FROM oven/bun:1 AS builder

ARG VERSION
WORKDIR /build

# Download source from GitHub release tarball
RUN apk add --no-cache curl tar && \
    curl -fsSL "https://github.com/rynfar/meridian/archive/refs/tags/v${VERSION}.tar.gz" \
    | tar xz --strip-components=1

RUN bun install --frozen-lockfile
# Use direct bun build (not bun run build) to skip postbuild hook requiring node --check
RUN bun build bin/cli.ts src/proxy/server.ts \
    --target=node --splitting --outdir=dist \
    --external=@anthropic-ai/claude-agent-sdk

# Stage 2: Runtime on HA base image
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23
FROM ${BUILD_FROM}

ARG VERSION
WORKDIR /app

# Install Node.js 22 and npm
RUN apk add --no-cache nodejs npm

# Install claude-code globally (provides `claude` binary)
RUN npm install -g @anthropic-ai/claude-code

# Copy compiled output and production deps from builder
COPY --from=builder /build/dist ./dist
COPY --from=builder /build/node_modules ./node_modules
COPY --from=builder /build/package.json ./package.json

# Add add-on run script
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

# Meridian must bind to all interfaces in the container
ENV MERIDIAN_HOST=0.0.0.0
ENV MERIDIAN_PORT=3456

EXPOSE 3456

CMD ["/app/run.sh"]
```

**`run.sh`** should:

1. Ensure `/data/.claude` directory exists
2. Symlink `/root/.claude` to `/data/.claude` if not already done
3. Check if `claude` is authenticated (via `claude auth status` or checking for token file)
4. If not authenticated, print instructions and exit with error
5. Start Meridian: `exec node /app/dist/cli.js`

**`.upstream.yaml`** for auto-update:

```yaml
upstream:
  repository: "rynfar/meridian"
  version_pattern: "v*"
  version_strip: "^v"
addon:
  version_pattern: "sync"
```

**`config.yaml`** ports section:

```yaml
ports:
  3456/tcp: 3456
ports_description:
  3456/tcp: "Meridian proxy (Anthropic API compatible)"
```

**Architecture support:** Since this is a personal add-on and the primary host is `haos-op3050-1` (an Intel NUC based on
the name), start with amd64 only in `build.yaml`. Add aarch64 later if `hassio-n2plus` (Odroid N2+, ARM64) needs it.

## Gotchas / Risks

**`claude login` is interactive and cannot be automated.** The user must open the HA terminal add-on and run
`claude login` manually after the add-on starts for the first time. The `run.sh` script should detect the absence of
credentials and print clear instructions, then exit non-zero so HA marks the add-on as failed with a visible error
message.

**`~/.claude` home path depends on the running user.** HA add-ons run as root by default, so `~` resolves to `/root`. If
the Dockerfile sets a different user (like Meridian's upstream `claude` user), the path changes. Recommendation: run as
root for simplicity, use `/root/.claude -> /data/.claude` symlink.

**Bun `--target=node` external deps.** Meridian's upstream Dockerfile explicitly skips `bun run build` and calls
`bun build` directly to avoid the `postbuild` hook that uses `node --check` (unavailable in the Bun builder image). The
`--external` flags must match what the upstream build uses — check the actual `package.json` build script for exact
flags.

**Node.js 22 on Alpine 3.23 availability.** Alpine 3.23's `nodejs` package provides Node.js 22.x (confirmed by Alpine's
package tracker). However, the exact minor version may lag behind the official Node.js releases. If Meridian requires a
very specific Node.js 22.x minor, an alternative is to use the `node:22-alpine` image as the runtime stage instead of
the HA base image, and manually add HA-specific tooling (bashio). This trades HA integration quality for Node.js version
precision.

**Meridian's release velocity means frequent auto-updates.** With multiple releases per day, the daily cron will update
Meridian every day. Each update triggers a Docker image rebuild (if CI is set up for that). This is fine but adds noise
to the commit history. Consider whether all patch releases need tracking or only minor/major versions — the current
`version_pattern: "v*"` catches everything.

**Port 3456 on the HA host network.** HA add-ons with `host_network: true` skip Docker port mapping. If `host_network`
is false (the default), port 3456 must be mapped in `config.yaml`. External tools need to know the HA host's IP, e.g.,
`ANTHROPIC_BASE_URL=http://192.168.x.x:3456`. The HA Companion app or mDNS hostname (`homeassistant.local:3456`) can be
used instead of raw IP.

**`@anthropic-ai/claude-agent-sdk` version pinning.** Meridian pins to `^0.2.89` which allows minor/patch updates. If a
newer SDK version breaks compatibility, the build may silently install a broken version. Pin to an exact version in the
Dockerfile's `npm install` step, or rely on `bun install --frozen-lockfile` to respect the `bun.lock` file (which does
pin exactly).

**No official HA Node.js base image means manual Node.js installation.** The official HA add-on validator
(`frenck/action-addon-linter`) expects HA base images in `build.yaml`. Using `node:22-alpine` directly may cause linting
warnings. Using the HA base image with `apk add nodejs` avoids this.
