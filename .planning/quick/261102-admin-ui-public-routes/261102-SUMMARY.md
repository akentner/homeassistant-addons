# Quick 261102 summary: public routes

Decisions
- Match: literal compare of (method, request target as sent without query) against registered public routes. The
  request line is used, because `http.server` collapses leading slashes in `self.path` (`//api/health` would become
  `/api/health`). No decoding, prefix, case folding or trailing-slash tolerance. A query string does not change the
  route (`/api/health?x=1` is public, `/api/private?/api/health` is not).
- Registration guards: public patterns must be literal (`^(/seg)+$`, no `{param}`, no dot segments, no trailing slash,
  not `/`, `/icon`, `/static...`); otherwise `ValueError`. Default stays private.
- HEAD and OPTIONS: 403 on a public route unless registered themselves (conservative, tested); other methods on the
  path: 403.
- Static, index and icon are never served to non-ingress requests (also skipped in dispatch, not only at
  registration).
- Public handlers get `Request.public = True` and a header view without `X-Ingress-*` and `X-Remote-User-*`
  (a caller on the published port could forge them), so `ingress_user` is None. Same API headers and `no-store`; the
  CSP setting is irrelevant.
- Python skeleton exports are unchanged (no new name), so no export contract change; lib 0.5.0 because the skeleton
  changed additively; skeleton hash in `lib.lock` refreshed.

Verification: test-admin-ui (295 node, 354 pytest, incl. new `test_public_routes.py` with 90+ cases), sync and rules
checks, validate-versions, validate-addons green. `internal/verify-admin-ui-scaffold.sh` passed (the demo registers no
public route, so the script is unchanged); image `admin-ui-verify:local` removed, no containers left.

For ss-control: use `public=True` only for those two GET routes, return no secret values, treat requests as
anonymous (`req.public`), and keep the port unpublished by default.
