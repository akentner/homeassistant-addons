# Phase 21: cups-print-server-addon-airprint-mdns-fixes - Context

**Gathered:** 2026-09-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Fork/adapt the CUPS print server Home Assistant add-on (currently the third-party
`f1c878cb_cups` add-on from `MaxWinterstein/homeassistant-addons`, itself based on
`zajac-grzegorz/homeassistant-addon-cups-airprint`) into a new, own add-on `cups/`
in this repo, following the repo's 4-file add-on pattern. Core deliverable is a
**permanent fix for the AirPrint/mDNS reliability bug** diagnosed in
`cups/DIAGNOSIS.md` (Avahi legacy-unicast reflector slot-table exhaustion +
Avahi hostname-conflict rename + IPv6 resolution ambiguity), exposed through
HA options instead of the upstream's hardcoded (`options: {}` / `schema: []`)
configuration. Scope includes rollout: installing the new add-on on
`haos-op3050-1` to replace `f1c878cb_cups`.

</domain>

<decisions>
## Implementation Decisions

### Fork Scope
- **D-01:** New, standalone add-on (not a drop-in patch of the upstream) — own directory `cups/`, own slug (e.g. `akentner_cups`), full 4-file pattern (`config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `README.md`, `DOCS.md`) per repo convention. Upstream's `options: {} / schema: []` is replaced with a real options schema.
- **D-02:** Add-on name/slug: **`cups`** (matches existing folder naming style: `gatus/`, `phone-logger/`, `meridian/`). The existing `cups/DIAGNOSIS.md` working directory is the basis for this add-on's folder.
- **D-03:** Printer support: **multiple printers from the start** (not just the current single Brother MFC-7460DN use case) — Reversibility: costly — retrofitting a list-based schema after a single-printer schema ships would require an options migration for existing installs.
- **D-04:** Printer options shape: `printers` as a **list of objects** `{name, uri, enabled}` (mirrors `phone-logger`'s adapter-list pattern), each registered via `lpadmin` at container start — not comma-separated parallel string lists.
- **D-05:** Minimum options/schema surface: `avahi_reflector` (bool), `avahi_hostname` (str), `avahi_use_ipv6` (bool), `printers` (list of `{name, uri, enabled}`), `log_level`.
- **D-06:** Version tracking: **no `.upstream.yaml`** — CUPS/Avahi come from Alpine `apk` packages baked into the HA base image, not a downloadable GitHub release tarball, so the `.upstream.yaml` "sync to upstream tag" model (used by `phone-logger`, `gatus`) does not apply. Instead, add a `cups` entry to `internal/base-image-config.yaml` using the same Alpine-base-image pattern as `gatus`/`meridian`/`network-tools` (`ghcr.io/home-assistant/amd64-base`, source `home-assistant/docker-base` `alpine/Dockerfile`). The existing daily `base-image-update.yml` workflow will bump the add-on subpatch when Alpine's base version changes — the closest available proxy for "a newer CUPS became available," since there's no per-package tracking mechanism in this repo.

### Avahi Reflector Fix (root cause)
- **D-07:** `enable-reflector` defaults to **`no`** — Reversibility: reversible — exposed via `avahi_reflector` option so it can be re-enabled if the add-on is ever run without `host_network: true` (e.g. Docker-bridge networking, where cross-namespace mDNS bridging would actually be needed). Rationale: with `host_network: true` the container already shares the host's real interfaces directly, so the reflector's primary purpose (bridging mDNS across network namespaces) provides no benefit — but its side effect (a finite in-memory slot table for legacy-unicast mDNS queries) is the confirmed root cause of the outage (`No slot available for legacy unicast reflection, dropping query packet.` — fills up under sustained legacy-unicast traffic, e.g. from a FritzBox mesh repeater, and then silently drops all further queries including resolves of CUPS's own advertised printer).
- **D-08:** No watchdog/log-monitoring for the slot-exhaustion error — with `enable-reflector=no` this failure mode cannot occur at all, so a watchdog for it would be dead code.
- **D-09:** Config mechanism: `run.sh` **generates `avahi-daemon.conf` from a template** at startup, reading `bashio::config` values (mirrors `gatus/generate_config.py`'s config-bridge pattern) — not a static file patched via `sed`.
- **D-10:** Additional fix, `avahi_use_ipv6` (bool, default `no`) — Reversibility: reversible — motivated directly by raw evidence in `cups/DIAGNOSIS.md`: `avahi-resolve -a 192.168.178.3` resolves to an IPv6 ULA address (`fdd8:7b39:...`), which may be unreachable/unrouted for iOS clients independent of the reflector bug. Also generated via the same `avahi-daemon.conf` template mechanism (`use-ipv6=no`).

### Hostname Stability
- **D-11:** Fix the `f1c878cb-cups` vs. `f1c878cb-cups-2` conflict-rename via a fixed, explicit `host-name=` directive in the generated `avahi-daemon.conf`, driven by an `avahi_hostname` option — **not** by changing the actual Docker/container hostname. Avahi's `host-name=` setting is independent of the kernel/container hostname (`gethostname()` is only the fallback when unset); setting it explicitly requires no extra capability (no `CAP_SYS_ADMIN`, no touching the Supervisor-assigned container hostname) and carries no Supervisor conflict risk. `cupsd`'s own DNS-SD/Bonjour publishing queries the Avahi client API for its host-name, so it automatically inherits the same fixed name for its `_ipp._tcp`/`_ipps._tcp`/`_printer._tcp` service records without separate CUPS-side configuration.

### Rollout
- **D-12:** Deployment/installation of the new `cups` add-on on `haos-op3050-1`, replacing `f1c878cb_cups`, is **in scope for this phase** — not just the repo artifact. Immediate production mitigation (restarting the old add-on to clear Avahi's in-memory slot table) is **not** in scope — it was already performed manually by the user before this discussion; the live outage no longer exists.
- **D-13:** Migration aid: read the current live CUPS configuration from `f1c878cb_cups` (printer URIs/names/queue settings) and **print it as a suggested `printers` option value** (e.g. a YAML snippet) at the end of the rollout — no automated config migration, just a proposal the user copies into the new add-on's options manually.

### Claude's Discretion
- Exact schema syntax for the `printers` list-of-objects option in HA's `schema:` YAML dialect (e.g. `list(match(...))?` vs. nested `schema` block) — pick whatever matches HA add-on schema conventions and is closest to an existing repo pattern.
- Exact default values for `avahi_hostname` (e.g. `"cups"` vs. slug-derived) — pick something sensible; user did not specify a literal string.
- Whether the printer's `enabled` field defaults to `true` — reasonable default, not discussed explicitly.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Diagnosis and root-cause evidence
- `cups/DIAGNOSIS.md` — Full investigation: symptom, findings (mDNS browse-vs-resolve split, Avahi reflector slot exhaustion, hostname-conflict rename, ghost mDNS record), raw `nmap`/`avahi-resolve`/`avahi-browse` evidence, access/tooling notes for `haos-op3050-1`. This is the primary source document for this phase — every decision above traces back to a specific finding in it.

### Repo conventions (add-on pattern)
- `CLAUDE.md` (repo root) — 4-file add-on pattern, 3-file version sync scheme, HA-base-image-only constraint, GSD workflow enforcement.
- `internal/base-image-config.yaml` — pattern to follow for adding `cups` as a base-image-tracked add-on (see `gatus`, `meridian`, `network-tools` entries).
- `.github/workflows/base-image-update.yml` — daily workflow that will pick up Alpine version bumps for the new `cups` entry.

### Closest structural analogue
- `gatus/` (`Dockerfile`, `run.sh`, `generate_config.py`, `nginx.conf`) — closest existing add-on with its own service + generated config file, referenced explicitly in `cups/DIAGNOSIS.md` as the pattern to follow for `avahi-daemon.conf` generation.
- `phone-logger/` — reference for list-of-objects options schema pattern (`input_adapters`, `resolver_adapters`, `output_adapters`), applicable to the new `printers` option.

No other external specs/ADRs apply — requirements for this phase are captured entirely in the decisions above and in `cups/DIAGNOSIS.md`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `gatus/generate_config.py` + `gatus/run.sh`: template for a Python (or shell) config-generation step that reads `bashio::config` / `/data/options.json` and writes a service config file before `exec`-ing the real daemon — directly reusable pattern for generating `avahi-daemon.conf`.
- `phone-logger`'s adapter-list options schema: reference for expressing `printers` as a list of `{name, uri, enabled}` objects in HA's `schema:` dialect.

### Established Patterns
- 4-file add-on pattern + `.upstream.yaml` for GitHub-tag-tracked add-ons (`phone-logger`, `gatus`) vs. `internal/base-image-config.yaml` entry for Alpine-base-tracked add-ons with no separate app upstream (`meridian`, `network-tools`) — `cups` falls into the latter category.
- 3-file version sync (`config.yaml` `X.Y.Z-N`, `build.yaml` `args.VERSION` `X.Y.Z`, `README.md` badge `vX.Y.Z`) via `make update-version` — applies to `cups` like every other add-on.

### Integration Points
- `f1c878cb_cups` on `haos-op3050-1` is the add-on being replaced — its current live printer configuration is the source for the migration-suggestion output (D-13).
- HA Supervisor sets the container hostname/`host_uts` for add-ons; this phase's hostname fix deliberately avoids touching that layer (see D-11).

</code_context>

<specifics>
## Specific Ideas

- Root-cause chain to fix, in the user's own framing: reflector-off (removes slot exhaustion) → fixed Avahi `host-name` (removes conflict-rename) → IPv6 off (removes ULA-resolution ambiguity) — all three implemented via the same generated `avahi-daemon.conf`.
- Migration convenience: read `f1c878cb_cups`'s live printer config and print a ready-to-paste `printers` option suggestion at the end of rollout, rather than building an automated migrator.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (The user raised and resolved several implementation questions — IPv6 handling, Supervisor-hostname risk, migration convenience — directly within this discussion rather than deferring them.)

### Reviewed Todos (not folded)
None — discussion stayed within phase scope.

</deferred>

---

*Phase: 21-cups-print-server-addon-airprint-mdns-fixes*
*Context gathered: 2026-09-26*
