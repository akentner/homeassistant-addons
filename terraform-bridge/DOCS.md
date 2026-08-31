# Configuration

**Phase 9 stub.** This add-on exposes no user-facing configuration options yet. The Bridge container reads
`SUPERVISOR_TOKEN` from its environment (auto-injected by Supervisor when `hassio_api: true`) and serves a placeholder
`GET /` on port 8124.

## Phase 9 options

_None._ Both `options:` and `schema:` blocks in `config.yaml` are empty by design. Plan 10 introduces `bind_address`
(Tailscale interface detection); Plan 11 introduces version-endpoint read parameters; nothing is user-configurable
before then.

## Phase 14 operator documentation

Full installation steps, token-issuance procedure, OpenTofu provider install command, an example `*.tf` file, every
error code with documented remediation, and a troubleshooting section land in Phase 14 after the real-HA end-to-end
verification pass. See `docs/DEVELOPMENT.md` in the repo root for the operator-doc scope.
