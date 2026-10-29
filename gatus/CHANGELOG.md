## What's Changed

- feat(alerting): add Resend alerting provider by @geffersonFerraz in https://github.com/TwiN/gatus/pull/1830
- fix(maintenance): validate maintenance windows for external, DNS and SSH endpoints by @anandghegde in
  https://github.com/TwiN/gatus/pull/1804
- fix(alerting): Redact telegram token from errors on send failure by @hippi345 in
  https://github.com/TwiN/gatus/pull/1843
- fix(websocket): apply the client timeout to reads and writes by @somaz94 in https://github.com/TwiN/gatus/pull/1845
- fix(ssh): support keyboard-interactive authentication for endpoints and tunnels by @peckto in
  https://github.com/TwiN/gatus/pull/1863
- fix(security): add comprehensive logging and diagnostics for OIDC (#1802) by @tech00exploere in
  https://github.com/TwiN/gatus/pull/1862
- fix(jsonpath): support object keys containing dots via quoted accessors by @leotemtem in
  https://github.com/TwiN/gatus/pull/1864
- fix: Honor minimum-reminder-interval for external endpoints by @yzxcj797 in https://github.com/TwiN/gatus/pull/1773
- chore(alerting): restyle matrix alerts with errors, safe links and escaping by @mazzz1y in
  https://github.com/TwiN/gatus/pull/1875

## New Contributors

- @anandghegde made their first contribution in https://github.com/TwiN/gatus/pull/1804
- @yzxcj797 made their first contribution in https://github.com/TwiN/gatus/pull/1773
- @hippi345 made their first contribution in https://github.com/TwiN/gatus/pull/1843
- @geffersonFerraz made their first contribution in https://github.com/TwiN/gatus/pull/1830
- @somaz94 made their first contribution in https://github.com/TwiN/gatus/pull/1845
- @peckto made their first contribution in https://github.com/TwiN/gatus/pull/1863
- @tech00exploere made their first contribution in https://github.com/TwiN/gatus/pull/1862
- @leotemtem made their first contribution in https://github.com/TwiN/gatus/pull/1864
- @mazzz1y made their first contribution in https://github.com/TwiN/gatus/pull/1875

**Full Changelog**: https://github.com/TwiN/gatus/compare/v5.37.0...v5.38.0

## What's Changed

- feat(alerting): allow configuring the topic for Zulip alerts by @ChrisJr404 in https://github.com/TwiN/gatus/pull/1764
- feat(client): Allow configuration of client cookie storage by @AaronLionsheep in
  https://github.com/TwiN/gatus/pull/1716
- feat(dns): Support TXT query type by @hernil in https://github.com/TwiN/gatus/pull/1679
- ci: Remove codecov from repository by @TwiN with @Copilot in https://github.com/TwiN/gatus/pull/1684
- fix(jsonpath): prevent panic on negative array index by @nikolauspschuetz in https://github.com/TwiN/gatus/pull/1703
- docs(alerting): Revise HomeAssistant alerts and add Home Assistant integration info by @TN-1 in
  https://github.com/TwiN/gatus/pull/1723
- docs: update the postgres bind mount in the compose example by @vshulcz in https://github.com/TwiN/gatus/pull/1761
- test(config): make HasLoadedConfigurationBeenModified deterministic by @nikolauspschuetz in
  https://github.com/TwiN/gatus/pull/1786

## New Contributors

- @hernil made their first contribution in https://github.com/TwiN/gatus/pull/1679
- @nikolauspschuetz made their first contribution in https://github.com/TwiN/gatus/pull/1703
- @AaronLionsheep made their first contribution in https://github.com/TwiN/gatus/pull/1716
- @TN-1 made their first contribution in https://github.com/TwiN/gatus/pull/1723
- @vshulcz made their first contribution in https://github.com/TwiN/gatus/pull/1761
- @GRbit made their first contribution in https://github.com/TwiN/gatus/pull/1787
- @ChrisJr404 made their first contribution in https://github.com/TwiN/gatus/pull/1764
- @pujitha24 made their first contribution in https://github.com/TwiN/gatus/pull/1813

**Full Changelog**: https://github.com/TwiN/gatus/compare/v5.36.0...v5.37.0

# Changelog

All notable changes to the **Gatus** add-on are documented in this file.

The daily `.github/workflows/auto-update.yml` workflow prepends upstream release notes from
[TwiN/gatus](https://github.com/TwiN/gatus/releases) at the top, in newest-first order. Add-on-specific changes (Home
Assistant schema, ingress wiring, packaging) are tracked in the "Add-on" sections below.

## Add-on

### [Unreleased]

- _No add-on-specific changes pending._

[Unreleased]: https://github.com/akentner/homeassistant-addons/compare/gatus/v5.36.0...HEAD
