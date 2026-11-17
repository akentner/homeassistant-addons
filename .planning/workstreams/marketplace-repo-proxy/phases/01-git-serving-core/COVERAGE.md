# API Coverage — GitHub (git smart-HTTP transport) and HA Supervisor

> Full coverage by default. Opt-outs are explicit, reasoned decisions.

Phase 1 talks to exactly one external service: GitHub, through git's smart-HTTP transport with a fine-grained PAT
(`Contents: read-only`), and only from the `sync` service. The "API" mentions the detector found refer to this add-on's
own later Provisioning API (Phase 4) and to the Supervisor API, which Phase 1 deliberately does not call.

| capability | decision | reason |
|---|---|---|
| git-upload-pack ref discovery (`info/refs`, `ls-remote --symref`) | INTEGRATE | |
| git-upload-pack fetch of the configured or default branch (`fetch --prune`) | INTEGRATE | |
| Authorization via `http.extraHeader` Basic `x-access-token` (env only) | INTEGRATE | |
| git-receive-pack (push upstream) | OPT-OUT | explicitly out of scope: the proxy is read-only by design (D-10, D-15, read-only PAT) |
| other refs (`refs/pull/*`, tags, non-configured branches) | OPT-OUT | explicitly out of scope: only the configured branch is mirrored (D-10) |
| shallow fetch (`--depth`) of the upstream | OPT-OUT | not needed: full-history mirror chosen so plain clones are complete (RESEARCH Alternatives) |
| SSH transport / per-repository deploy keys | OPT-OUT | not needed yet: deferred idea in CONTEXT.md (later, optional) |
| GitHub REST API (repos, contents, releases, rate limits) | OPT-OUT | not needed: git transport covers sync; HACS support is out of scope (REQUIREMENTS) |
| GitHub webhooks (push events) | OPT-OUT | explicitly out of scope: needs an inbound path, contradicts internal-only (SPIKE "Sync") |
| HA Supervisor store API (`/store/repositories`, `/store/reload`) | OPT-OUT | not needed yet: Phase 2 scope (MRP-07 to MRP-10) |
| HA Supervisor `GET /addons/self/info` (own hostname) | OPT-OUT | not needed: hostname comes from the kernel UTS name (RESEARCH Pattern 6); Phase 2 may cross-check |
