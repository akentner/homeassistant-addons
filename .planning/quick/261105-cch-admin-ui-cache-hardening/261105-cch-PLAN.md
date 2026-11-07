---
quick_id: 261105-cch
slug: admin-ui-cache-hardening
status: planned
scope: plan only - no code, no release, no push
---

# Quick 261105-cch: admin-ui skeleton cache hardening (part 3)

Source: brief-plan3.md (session scratchpad). Branch `docs/admin-ui-cache-hardening-plan` (from origin/main, after PR #95).
This file is the only change of this task. STATE.md, ROADMAP.md and state.json stay untouched.

## 1. Problem and findings

Symptom: after the 0.7.x update one browser kept showing the old front end (old `hosts.json` call -> 404, "Update
failed: 404"); a second browser was fine.

Facts checked in the repo (origin/main):

- `admin-ui/app/web/skeleton/server.py:142`: static files and `/` are sent with `Cache-Control: no-cache`, **no ETag, no
  Last-Modified**. `no-cache` means "revalidate before reuse", but without a validator the browser can only refetch in
  full - fine for correctness, wasteful, and no 304 path. Copy in `haos-monitor/app/web/admin_ui/server.py:142`.
- `admin-ui/app/web/skeleton/static.py` `StaticFiles.resolve()` returns `(bytes, ctype)`; it has no hash/mtime.
- `static/index.html` references `static/app.mjs`, `static/app.css`, `static/lib/base.css` without any version. `app.mjs`
  imports its modules relatively (`./lib/ui.mjs`, ...): a query on the entry URL does **not** propagate to them.
- 0.6.x served the page from **busybox httpd** (`haos-monitor/httpd.conf`, `/www`), which sends `Last-Modified` and no
  `Cache-Control`. 0.7.0 moved the page to the Python server on port 8100 (`ingress_port: 8100`).

Hypotheses (none proven; the user's browser state is not available):

| # | Hypothesis | Fit | How to check |
| - | ---------- | --- | ------------ |
| H1 | Heuristic caching of the 0.6.x page (`Last-Modified` without `Cache-Control`, browsers reuse for ~10 % of the file age, possibly days) kept the old `/` fresh in that browser, so it never asked the new server | strong: explains one browser only, old `hosts.json` call, no revalidation | DevTools Network on the bad browser: `/` "(from disk cache)" without request; response headers of the cached entry show `Last-Modified`, no `Cache-Control` |
| H2 | Service worker or HA frontend caching of ingress content | weak: HA's service worker does not cache ingress responses | DevTools Application -> Service Workers, check scope for `/api/hassio_ingress/` |
| H3 | Traefik / Cloudflare cache in front of HA | unproven; ingress is cookie-authenticated and HTML is not cached by Cloudflare by default, static extensions (js/css/png) are | `curl -I` via the public URL with a valid session: look for `cf-cache-status`, `age`, `via`; compare with the LAN URL |

Consequence: H1 is a one-off legacy entry. The new `no-cache` header already prevents a repeat; it self-heals once the
heuristic lifetime ends. The hardening below is defence in depth plus cheaper revalidation, not a proven fix.
Hard reload (Ctrl+Shift+R) or "clear site data" for the HA origin clears the stale entry immediately.

## 2. Goal

Static responses are validated cheaply (ETag/304) and a changed asset can never be served from a stale cache, without
consumer-side edits and without weakening the ingress gate or CSP.

## 3. Changes (admin-ui source only; consumers get them by sync)

Files:

- `admin-ui/app/web/skeleton/static.py` - core change.
- `admin-ui/app/web/skeleton/server.py` - static branch of `_dispatch` (line ~139-143), `_send` accepts extra headers
  already.
- `admin-ui/app/web/static/lib/VERSION` + `admin-ui/lib.lock` - written by `make release-admin-ui-lib`, never by hand.
- Consumer copies `<addon>/app/web/admin_ui/` and `<addon>/app/web/static/vendor/admin-ui/` - written by sync only.
- Docs: `admin-ui/DOCS.md` (caching section), `admin-ui/CHANGELOG.md`.
- Tests: `admin-ui/tests/test_skeleton_server.py` (line 175 asserts `no-cache`; keep), new
  `admin-ui/tests/test_static_cache.py`.

### 3.1 ETag + 304 (goal 1)

- `StaticFiles.resolve()` returns a small result object (content, ctype, etag) instead of the tuple; update the two
  call sites (`server.py`, tests). Keep the whitelist/containment code untouched.
- ETag = strong validator `"<first 16 hex of sha256(content)>"`. Cache hash per path keyed by `(st_mtime_ns, st_size)`
  so a request does not rehash an unchanged file.
- `GET`/`HEAD` with `If-None-Match` (comma list, `W/` prefix tolerated, `*`) matching -> `304`, no body, no
  `Content-Length` body, same `ETag`, `Cache-Control: no-cache`, and the security headers (CSP, nosniff).
- 200 responses carry `ETag`; `Cache-Control` stays `no-cache` (revalidate every time; 304 makes it cheap).
- `Last-Modified` is deliberately **not** sent (it re-enables heuristic caching if `Cache-Control` is ever dropped).
- ETag only on the ingress-gated static branch; API responses stay `no-store`, public routes unchanged.

### 3.2 Versioned asset URLs (goal 2)

- Do it server-side in `StaticFiles` when serving `/` (index.html): rewrite `src`/`href` values starting with
  `static/` to `static/...?v=<hash of that asset>` (per-asset hash from 3.1). No consumer HTML edit, no build step.
- The served index is then different content -> its own ETag changes whenever any referenced asset changes, so a
  changed asset invalidates `index.html` automatically. `index.html` itself stays `no-cache`.
- `/static/<rel>?v=...` must still resolve: `urlsplit(...).path` is already used, query is ignored - verify in test.
- Limit (document it): the query only covers entry assets. ES module imports (`./lib/ui.mjs`, `./views/*`) stay
  unversioned; they rely on `no-cache` + ETag revalidation. An import map would fix this but inline `<script>` is
  blocked by `script-src 'self'`; rewriting import specifiers in served `.mjs` is too invasive. Rejected.
- Check `internal/check-admin-ui-rules.py` and `test_static_rules.py` do not forbid query strings in asset URLs.

### 3.3 Cleanup of the legacy cache entry (goal 3)

- Server cannot evict an entry the browser never revalidates; only a request that reaches the server can help, and
  H1 means that request does not happen. So no server change fixes the already-stale browser.
- `Clear-Site-Data: "cache"`: **not recommended** as default. It is stateless, so it would purge the cache on every
  page load (defeats ETag) and can cause reload loops; it is honoured only in secure contexts. Option: one-shot, gated
  by a version cookie - added complexity for a one-off. Listed as open decision D3 (default: skip).
- Recommendation: document in `admin-ui/DOCS.md` and the haos-monitor CHANGELOG that after the 0.6 -> 0.7 jump a hard
  reload may be needed once. Service worker: none exists in the skeleton; add a one-line DOCS note that none is
  registered and that this is why no SW cleanup is needed.
- H3: separate verification step, no code. `curl -I` against LAN and public URL as in the table; only if
  `cf-cache-status: HIT`/`age` shows up, add a Cloudflare cache rule bypass for the ingress path (infra, out of repo).

## 4. Execution order (when approved)

1. Branch `fix/admin-ui-cache-hardening` from fresh `origin/main` (not this docs branch), `git branch --unset-upstream`.
2. Edit `static.py`, `server.py`; add tests (section 6). `make test-admin-ui` green.
3. Docs + CHANGELOG for admin-ui.
4. `make release-admin-ui-lib VERSION=0.7.1` (behaviour-compatible addition -> patch; 0.8.0 if D2 chooses minor). It
   writes `lib/VERSION`, syncs every discovered consumer, refreshes `lib.lock`, runs `check-admin-ui-rules`,
   `test-admin-ui`, `test-admin-ui-consumers`.
5. Determine consumers by script, do not trust this list:
   `python3 -c "import sys; sys.path.insert(0,'internal'); ..."` is awkward (hyphenated module); use instead
   `for d in */app/web/admin_ui/LIB.stamp; do echo ${d%%/*}; done` (same rule as `discover_consumers`: LIB.stamp in
   `app/web/admin_ui` or `app/web/static/vendor/admin-ui`). Today: **haos-monitor, ntfy, secrets-sync** (all at lib
   0.7.0, skeleton hash `0f46d30e...`). admin-ui itself is the source, not a consumer (its own version 0.2.0-0).
6. Version bumps per consumer, only via `make update-version` (never by hand):
   - haos-monitor 0.7.2-0 -> 0.7.3-0 (own code, manual bump, CHANGELOG entry).
   - secrets-sync 0.7.1-0 -> 0.7.2-0 (own code, CHANGELOG entry).
   - ntfy 2.37.2-1 -> 2.37.2-2 (wrapper: add-on-only fix = subpatch increment; upstream auto-update resets to -0).
   - admin-ui add-on: bump only if its own add-on files change (demo app uses the skeleton directly) - check
     `check-admin-ui-sync` output; decision D4.
7. Verify (section 6), then commit by path per add-on, PR, no merge/tag without request.

## 5. Risks

| Risk | Mitigation |
| ---- | ---------- |
| 304 sent without security headers or with body -> broken keep-alive on HTTP/1.1 | test raw socket, assert no body bytes, next request on same connection works |
| ETag cache keyed wrongly -> stale validator after file replace | key on `(mtime_ns, size)`; test overwrite of a file between two requests |
| Index rewrite breaks pages with unusual markup (`static/` in text/inline) | rewrite only attribute values `src="static/..."`/`href="static/..."`; leave unknown refs unchanged; test with all 3 consumer index files |
| Entry assets versioned, module imports not -> mixed old/new modules | all assets `no-cache` + ETag; accepted and documented |
| Consumers drift (one forgets sync) | `make check-admin-ui-sync STRICT=yes` is in `check-all` / CI |
| Shared skeleton change hits three add-ons at once | staged rollout option D1; haos-monitor first |
| Hypothesis H1 wrong, user still sees stale UI | keep DevTools evidence step (section 1) before declaring done |

## 6. Tests and verification

- `make test-admin-ui` (Node + pytest) and `make test-admin-ui-consumers` (each consumer separately).
- New `test_static_cache.py`: 200 has strong `ETag`, same content -> same tag, changed content -> new tag; matching
  `If-None-Match` (plain, list, `W/`, `*`) -> 304 no body, with CSP/nosniff/`Cache-Control: no-cache`; non-matching ->
  200; HEAD; `/static/app.mjs?v=x` resolves; index contains `?v=` for every `static/` asset and the value changes when
  an asset changes; whitelist/containment/ingress-gate tests unchanged and still passing (non-ingress peer still 403,
  no 304 leak).
- `make check-admin-ui-rules`, `make check-admin-ui-sync STRICT=yes`, `make validate-versions`, `make lint`.
- `docker build` per consumer before committing (CLAUDE.md rule), one after the other:
  `docker build -t t-haos-monitor haos-monitor/`, same for `ntfy/` and `secrets-sync/` (use each add-on's build args from
  `build.yaml`).
- Verify scripts **sequentially, never in parallel / never in two worktrees**: `internal/verify-admin-ui-scaffold.sh`,
  `verify-ntfy-scaffold.sh`, `verify-ntfy-e2e.sh`, `verify-secrets-sync-scaffold.sh`; haos-monitor has its own tests in
  `haos-monitor/tests`.
- Manual: `curl -sI -H 'X-Ingress-Path: /x' ...` against a running container twice with `If-None-Match` -> 200 then 304.

## 7. Goal-backward acceptance criteria

1. A second request of `/`, `/static/app.mjs`, `/static/lib/*.mjs` with the previous ETag returns 304 without body.
2. Editing any static file changes its ETag and the served `index.html` ETag/asset `?v=` values; the next page load gets
   the new assets without a hard reload.
3. `index.html` is never cacheable without revalidation (`Cache-Control: no-cache`, no `Last-Modified`).
4. No request from a non-ingress peer gets a static response or 304 (gate unchanged).
5. `lib.lock`, every consumer `LIB.stamp` and the lib `VERSION` agree (`check-admin-ui-sync STRICT=yes` passes); each
   consumer bumped by `make update-version`, `validate-versions` passes.
6. Three consumer images build and their verify scripts pass.
7. H1/H2/H3 each have a recorded outcome (confirmed / ruled out / not reproducible) in the SUMMARY.

## 8. Open decisions

- **D1** All three consumers in one PR (recommended: one lib release, one `lib.lock` state, `check-admin-ui-sync` stays
  green) or staged (haos-monitor first, others later - leaves consumers "behind" and needs non-strict check).
- **D2** Lib version 0.7.1 (recommended, backward compatible) vs 0.8.0. Note `resolve()` return type changes for
  consumers that call it directly - verify none does (grep) before choosing patch.
- **D3** `Clear-Site-Data` one-shot: skip (recommended) / version-gated cookie variant.
- **D4** Bump the `admin-ui` demo add-on version too, or only the consumers.
- **D5** Query-versioning only for entry assets (recommended) vs also rewriting `.mjs` import specifiers.
- **D6** Release now, or hold until the next planned haos-monitor change to save one bump per add-on.
