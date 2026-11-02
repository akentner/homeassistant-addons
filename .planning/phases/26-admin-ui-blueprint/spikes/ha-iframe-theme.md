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

## 4. How to test the CSP in a live HA (S9)

1. **Find the header.** Open the add-on in Home Assistant (sidebar panel). In the browser developer tools open the
   Network tab, tick "Disable cache", filter by `hassio_ingress` and reload the page. Select the document request
   (`.../api/hassio_ingress/<token>/`, type `document`) and read the response header `Content-Security-Policy`. It must
   equal `DEFAULT_CSP` from `admin-ui/app/web/skeleton/headers.py`. The header is sent on the HTML page and on static
   files, not on `api/` responses. `curl` or a headless browser cannot test this: the ingress path needs a Home
   Assistant session, and the point is what HA and its proxies actually deliver.
2. **Header missing or different?** Then the result proves nothing. The container sends it unless the environment
   variable `ADMIN_UI_CSP` is `off` (`strict` is the default, read in `app/main.py`). The add-on has no options and
   `run.sh` does not set the variable, so a missing header means a proxy or HA changed it. Record that as the finding.
3. **Recognise violations.** Open the Console during the whole test. A violation shows as `Refused to load ...` or
   `Refused to execute inline ...` plus the violated directive, and the browser fires a `securitypolicyviolation` event.
   The counter of S9 counts only those events, only for this page's document, and only while the `#/spike` view is
   open (the listener lives in that view). Violations on other views, in the HA frame around it and anything that is
   only logged by HA are not counted: watch the Console there yourself.
4. **When a zero counter counts.** Only if step 1 confirmed the header, the page was loaded with the cache disabled,
   and the actions below were done. The smoke script (`internal/verify-admin-ui-scaffold.sh`) shows the header on the
   container itself (26-13 summary). That is not an observation of what HA or a proxy delivers, so it does not replace
   step 1.
5. **Actions during the test.** Open the gallery and use toast, modal and confirm dialog. Do the sample CRUD (create,
   edit, delete with type-to-confirm). Switch language and dark mode so theme sync applies. On `#/spike` press the
   bridge buttons (policy, `handleSafeArea`, navigate), copy a sample and run the storage and identity checks. Return
   to `#/spike` at the end and read the counter.
6. **Record it.** Update the S9 row with the date, the HA core version and the access path (panel, card, direct
   tab), and say whether the header was seen in the network tab. Set `verified` only with a confirmed header and no
   violation. The `Verified on:` line gets the same date.
7. **On a violation** the fix is a code change, not a setting: `DEFAULT_CSP` is a constant in
   `admin-ui/app/web/skeleton/headers.py` and cannot be changed through add-on options. Note the directive and the
   blocked kind (`inline`, `eval`, `self`, other), fix the page or loosen the constant deliberately, rerun
   `make test-admin-ui`, and run the test again. Do not switch the header off to get a green result.

## 5. Version capture (S15)

Since add-on 0.1.0-3 the spike view fills the versions itself: core from the same-origin parent (`hass.config.version`),
add-on from `api/health`, browser from client hints or the user agent. The block has `ha.core_source`,
`ha.frontend_source`, `ha.addon_source` and `client.app_source` (`auto`, `manual`, `not_recorded`). The frontend version
is not detectable (HA frontend: build-time constant `__VERSION__`, shown by `ha-config-info.ts`, no runtime property),
so it stays a typed field. Fields are labelled core, frontend and add-on separately, which prevents the run A mistake
(add-on version in the frontend field).
