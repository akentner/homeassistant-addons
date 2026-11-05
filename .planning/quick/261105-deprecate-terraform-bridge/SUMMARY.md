---
status: complete
---

# Quick: deprecate terraform-bridge

- Directory kept; deprecation notice added to `terraform-bridge/README.md` and `DOCS.md`.
- `build.yml`: path filter `!terraform-bridge/**` plus `DEPRECATED_ADDONS` skip in the detect job (covers dispatch).
- `.pre-commit-config.yaml`: global `exclude: ^terraform-bridge/` (also disables both bridge verify hooks).
- `lint.yml`: yamllint and shellcheck skip `terraform-bridge/`; `.markdownlint-cli2.yaml` ignores it.
- Not changed: version files, `validate-versions.sh` bridge/provider sync check, provider workflows, release docs.
