# Quick 261102 summary: admin-ui experimental stage

- `stage: "experimental"` added to `admin-ui/config.yaml`. HA docs (contributors.home-assistant.io, app configuration
  reference): "Where the app is in its life: `stable`, `experimental`, or `deprecated`", type string, default `stable`.
  The reference does not describe the effect. How the Store and the app page show it (label, advanced mode filter) is
  not documented there and was not verified: the HA frontend app dashboard does not use `stage`, so any display comes
  from elsewhere in the frontend or the Supervisor. Check it in HA after the reload.
- No other add-on sets `stage`, and no validator knows or rejects it (`make validate-addons` and the config schema
  hook accept it); no validator change was needed.
- README: shield already `project stage experimental` (orange, same pattern as other add-ons); About sentence updated.
  DOCS.md has no stage classification, so unchanged.
- Version: `make update-version` needs `VERSION=0.1.0-6` (plain `0.1.0` would reset the subpatch to `-0`). Only
  `config.yaml` changes for an add-on-only bump (build.yaml and README badges carry `0.1.0`); with NO_TAG/NO_PUSH there
  are no tag or push side effects.
- Checks green: test-admin-ui (295 node, 267 pytest), sync and rules checks, validate-addons, validate-versions.
