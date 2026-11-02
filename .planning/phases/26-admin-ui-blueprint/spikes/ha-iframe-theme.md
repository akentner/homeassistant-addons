# Spike: ha-iframe-theme (Phase 26)

Date: 2026-11-02. Scope: HA iframe, parent theme access, bridge, CSP, identity of the admin-ui demo add-on (D-14).
Legend: **[V]** verified in a live run, **[A]** assumed, not verified. Only run A was done; runs B to H were not done.
Redaction: no credentials, hostnames, addresses or user names.

## 0. Verdict

- Run A (desktop panel, default dark theme) works as designed for parent access, variable read (4 of 5), bridge answer,
  no double bar on a docked sidebar and identity headers.
- Everything else is **not run**. R-11 and R-13 stay `unverified` (S9 lacks a confirmed CSP header, S3 was not run).
- No code or default was changed: the data does not contradict the design.

## 1. Runs

| Run | Context                                                | Status  |
| --- | ------------------------------------------------------ | ------- |
| A   | Desktop Chromium 156.0.8078.48, panel, ingress, dark   | done    |
| B   | Narrow and hidden sidebar, kiosk policies              | not run |
| C   | Phone browser and Companion app                        | not run |
| D   | Ingress URL in a plain tab                             | not run |
| E   | Dashboard webpage card                                 | not run |
| F   | Non-admin user                                         | not run |
| G   | CSP and storage-blocked runs (beyond the panel counter) | not run |
| H   | After an HA update (optional)                          | not run |

### Run A: HA core 2026.10.4, add-on 0.1.0-2, HA default dark theme, embedded, access path ingress

Frontend version was not recorded. The field `ha.frontend` in the block holds the add-on version by mistake; it is not
the frontend version. CSP header presence was not confirmed.

```json
{"schema":1,"generated_at":"2026-11-02","ha":{"core":"2026.10.4","frontend":"Add-on 0.1.0-2"},"client":{"app":"Chromium: 156.0.8078.48"},"access_path":"ingress","embedded":true,"probes":{"S1":{"ok":true,"detail":"readable_same"},"S2":{"ok":true,"detail":"4_of_5"},"S3":{"ok":true,"detail":"observer 0, poll 76, apply 1"},"S4":{"ok":true,"detail":"ok"},"S5":{"ok":true,"detail":"bar false, kiosk false"},"S6":{"ok":true,"detail":"safe_area_off"},"S7":{"ok":null,"detail":"not_run"},"S8":{"ok":null,"detail":"not_run"},"S9":{"ok":true,"detail":"violations_0"},"S10":{"ok":null,"detail":"not_run"},"S11":{"ok":true,"detail":"identity_yes"},"S12":{"ok":true,"detail":"ingress"},"S13":{"ok":true,"detail":"sync_on"},"S14":{"ok":null,"detail":"de_dark"},"S15":{"ok":true,"detail":"versions_entered"}},"sync":{"mode":"dark","surface":false,"accent":false,"skipped":["surface","accent"],"counters":{"observer":0,"poll":76,"apply":1,"refresh":80},"colors":{"bg":"#111111","card":"#1c1c1c","fg":"#e1e1e1","bd":null,"acc":"#009ac7"}},"bridge":{"status":"ok","narrow":false,"kiosk":false,"hostBar":false,"kioskFrozen":false,"messages":1,"insets_present":true,"route_present":false},"csp":{"violations":{}},"whoami":{"identity_present":true,"groups":["system-admin"]}}
```

The page's own S12 and S13 probes report `ingress` and `sync_on`, but they come from the panel and are not the direct-tab
or card cases; the human classified them as not run.

## 2. Items

- **S1** [V] verified: parent readable in the panel (`readable_same`). Direct-tab case belongs to S12.
- **S2** [V] verified, limited: HA default dark only. 4 of 5 variables parsed, `bd` null (divider not read), surface and
  accent skipped by the contrast guard (accent `#009ac7` on dark surface). Light, custom, new primary colour not run.
- **S3** [A] not-applicable: observer 0, poll 76, apply 1; no theme switch during the run, detection unchecked.
- **S4** [V] verified, limited: bridge `ok`, `narrow` false, insets present, 1 message. Flip at 870 px and rotation not run.
- **S5** [V] verified, limited: docked sidebar only, host bar false, kiosk false, not frozen. Other modes not run.
- **S6** [V] verified, limited: default off (`safe_area_off`). Toggle on iOS and Android not run.
- **S7** [A] not-applicable: not run.
- **S8** [A] not-applicable: not run.
- **S9** [V] verified with reservation: `violations_0`, but CSP header presence was not confirmed, so weak evidence.
- **S10** [A] not-applicable: not run.
- **S11** [V] verified, admin only: identity present, group `system-admin`. Non-admin not run.
- **S12** [A] not-applicable: only the ingress path in the panel; no direct tab, no published port.
- **S13** [A] not-applicable: block came from the panel, not a dashboard card.
- **S14** [A] not-applicable: `de_dark` is the state only; no live switch.
- **S15** [V] verified, limited: core 2026.10.4 recorded, frontend version missing; no run after an HA update yet.

## 3. Follow-ups

- Rerun S3, S4, S5, S6, S7, S8, S10, S12, S13, S14 and the non-admin case of S11.
- Find out why `bd` is null (which parent variable and raw value; whitelist correction?).
- Check the CSP response header in the network tab before S9 counts as reliable.
- Record the frontend version; the `ha.frontend` result field shows the add-on version.
- R-07 stays `review` (user decision): interpolate number formatting and a scanner rule for `toLocale*`, `toFixed`,
  `Intl.*` outside `lib/format.mjs` (see DOCS Follow-up).
