# Requirements: admin-ui-bearer-api

## Phase 1: Bearer API listener

- [ ] **AUB-01**: Skeleton API server on its own port and bind address, separate from the ingress server, reusing
  `Router`, `Request`, `ApiError`, `ERROR_STATUS` and the API security headers; JSON only, `Cache-Control: no-store`,
  `MAX_BODY` limit, no static files, no CORS.
- [x] **AUB-02**: Bearer gate on every method and path (including unknown paths, `HEAD`, `OPTIONS`): missing, malformed
  or wrong token → `401 unauthorized` with `WWW-Authenticate: Bearer`, identical response for all failure cases.
- [x] **AUB-03**: Token verifiers: `OptionToken` (value from an add-on option, `hmac.compare_digest`) and
  `GeneratedToken` (256-bit from `secrets`, SHA-256 hash file with mode 0600, plaintext available once after
  creation or rotation, `rotate()`); empty or missing token disables the API (startup refuses to listen).
- [x] **AUB-04**: No secret in logs: the request log never contains the `Authorization` header or token values; the
  generated token is never written to stdout.
- [ ] **AUB-05**: Rule R-16 in `admin-ui/DOCS.md` (bearer gate, separate port, never routed through ingress or a public
  reverse proxy by default) with enforcing tests; library reference updated; `test_docs.py` and the lib contract test
  green.
- [ ] **AUB-06**: Release: admin-ui version bump via `make update-version`, `make sync-admin-ui` for all consumers,
  consumer docker builds, `make check-admin-ui-sync`, `make check-admin-ui-rules`, `make test-admin-ui` green.

## Notes

- ntfy Phase 25 (main ROADMAP) plans an option-based token; the proxy plans a generated token. Both are covered by
  AUB-03. Updating Phase 25's text to reference this listener happens in the main checkout, not here.
