---
quick_id: "260908-pfp"
slug: "add-a-build-workflow-for-the-iac-runner-add-on-there-is-curr"
verified: 2026-09-08T17:20:00Z
status: passed
score: 7/7 must-haves verified
covered_files:
  - ".github/RELEASE.md"
  - ".github/workflows/build-iac-runner.yml"
  - ".planning/quick/add-a-build-workflow-for-the-iac-runner-add-on-there-is-curr/260908-pfp-PLAN.md"
  - ".planning/quick/add-a-build-workflow-for-the-iac-runner-add-on-there-is-curr/260908-pfp-SUMMARY.md"
covered_digest: "v1:sha256:3cc8cf4adee3975fc0965a232a27904d27656a9ecebd617c8b3b2697935d59f4"
behavior_unverified: 0
overrides_applied: 0
re_verification: null
---

# Quick 260908-pfp: Build Workflow für iac-runner — Verification Report

**Ziel:** `.github/workflows/build-iac-runner.yml` ergänzen — modelliert auf `build-terraform-bridge.yml`, delegierend
an `_build-template.yml`, mit derselben Trigger-Form und derselben ghcr-Image-Benennung, actionlint-grün.
**Verifiziert:** 2026-09-08 **Status:** passed **Re-Verification:** Nein — Erstverifikation **Verifizierter
Endzustand:** `main` @ `812f028`; die Item-Commits `6b7d53a` und `af3dda2` sind über den Merge `a4ca23f` in `main`
enthalten (`git branch --contains` → `main` für beide). Es wurde kein Worktree geprüft, sondern der gemergte Zustand.

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                                                                        | Status     | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Push auf `main` unter `iac-runner/**` dispatcht `_build-template.yml` mit den iac-runner-Inputs (strukturell)                                                                                | ✓ VERIFIED | Strukturverifier des Plans erneut ausgeführt (nicht aus SUMMARY übernommen): `OK: build-iac-runner.yml matches the caller contract`, exit 0. Geparste Werte: `on.push.branches: [main]`, `on.push.paths: ["iac-runner/**"]`, `jobs.build.uses = ./.github/workflows/_build-template.yml`. Kein realer Run getriggert.                                                                                                                                                                                            |
| 2   | Push eines `iac-runner/v*`-Tags dispatcht denselben Build über einen LIVE `on.push.tags`-Glob                                                                                                | ✓ VERIFIED | `build-iac-runner.yml:9-10` trägt `tags: ["iac-runner/v*"]` unkommentiert; der Disabled-Kommentar `# tag-trigger temporarily disabled` fehlt in der Datei (grep: not present). Negativkontrolle selbst gefahren: derselbe Verifier auf `build-authentik.yml` → `FAIL: on.push.tags lacks live authentik/v* glob`, exit 1; Positivkontrolle `build-terraform-bridge.yml` → `OK`, exit 0. Damit ist "live" gemessen, nicht gegrept.                                                                                |
| 3   | `pre-commit run actionlint --all-files` exit 0                                                                                                                                               | ✓ VERIFIED | Selbst ausgeführt: `Lint GitHub Actions workflow files....Passed`, sauberer Re-Run mit `exit=0`. Zusätzlich `pre-commit run yamllint --files .github/workflows/build-iac-runner.yml` → Passed, `pre-commit run prettier --files .github/RELEASE.md` → Passed (beide Läufe, kein Reformat nötig, `git status --porcelain .github/` leer).                                                                                                                                                                         |
| 4   | Der Caller-Job trägt KEIN `timeout-minutes`; die Intention lebt in `_build-template.yml`                                                                                                     | ✓ VERIFIED | `build-iac-runner.yml` Job-Body enthält nur `uses`/`permissions`/`with`/`secrets` — kein `timeout-minutes` (Verifier-Assertion `"timeout-minutes" not in job` grün). Gegenstück vorhanden: `_build-template.yml:56 timeout-minutes: 45`, Typ `int` (Assertion `isinstance(..., int)` grün). Akzeptierte Abweichung wie vorgegeben — kein Defekt.                                                                                                                                                                 |
| 5   | Der Image-Name entsteht ausschließlich im Template-Slug-Step; der Caller re-implementiert keine Benennung                                                                                    | ✓ VERIFIED | `_build-template.yml:105-107` (`slug=$(echo '<addon-name>' \| tr '-' '_')`), `:151 IMAGE_BASE: ghcr.io/akentner/homeassistant-addons`, `:168-169 ${IMAGE_BASE}/${matrix.arch}-${slug}:${CONFIG_VERSION}` bzw. `:latest`; `CONFIG_VERSION` aus `iac-runner/config.yaml` (`:78`). Der Caller enthält keinen `run:`-Step, kein `env:`, keinen `ghcr.io`-String, keine Version — geprüft über den vollständigen Dateiinhalt (28 Zeilen). Ergebnis: `ghcr.io/akentner/homeassistant-addons/amd64-iac_runner:0.2.1-1`. |
| 6   | Die RELEASE.md-Tag-Trigger-Tabelle hat eine Zeile pro `build-*.yml` und jede Zeile stimmt mit dem real geparsten `on.push.tags` überein (inkl. der zuvor fehlenden `terraform-bridge`-Zeile) | ✓ VERIFIED | Task-2-Cross-Check selbst gefahren: `OK: RELEASE.md table and prose match every build-*.yml trigger state`, exit 0. 9 Tabellenzeilen ↔ 9 `build-*.yml`-Dateien, keine überzählig/fehlend. Geparst: live = `iac-runner`, `network-tools`, `terraform-bridge`; alle übrigen 6 `disabled`. Beide Prosa-Anker nennen alle drei Live-Add-ons (`RELEASE.md:31-33` Klausel, `:71` "built twice").                                                                                                                       |
| 7   | Es wurde kein Tag gepusht und kein realer Build getriggert                                                                                                                                   | ✓ VERIFIED | `git rev-parse iac-runner/v0.2.1^{commit}` → `455920f9066231de6322f80dccc9142022d1fbf7`, also unverändert der vorbestehende Commit (Tag-Objekt `0e8a26d`, annotiert). Add-on-skopierte Tags (`git tag -l '*/v*'`) = **39** wie erwartet (46 total, davon 7 unskopierte Legacy-Tags). Kein `git push`, kein `gh workflow run`, kein `workflow_dispatch` im Rahmen dieser Verifikation.                                                                                                                            |

**Score:** 7/7 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact                                 | Expected                                                                                 | Status     | Details                                                                                                                                                                                                                                           |
| ---------------------------------------- | ---------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.github/workflows/build-iac-runner.yml` | Per-Addon-Caller mit Delegation an das Template und livem Tag-Trigger                    | ✓ VERIFIED | Existiert (735 B, 28 Zeilen), enthält `uses: ./.github/workflows/_build-template.yml` (Zeile 15). Nicht-Stub: vollständiger Trigger-Block + Job mit `permissions`/`with`/`secrets`. Längste Zeile 111 Zeichen (Zeile 22), unter dem 120er-Budget. |
| `.github/RELEASE.md`                     | Tag-Trigger-Tabelle mit `iac-runner` (active) und der fehlenden `terraform-bridge`-Zeile | ✓ VERIFIED | Enthält `\| iac-runner        \| active             \| **active**       \|` und die neue `terraform-bridge`-Zeile. Diff `af3dda2`: 6 insertions / 4 deletions, ausschließlich `.github/RELEASE.md`.                                               |

Commit-Scope geprüft: `6b7d53a` berührt genau 1 Datei (`build-iac-runner.yml`, +28), `af3dda2` genau 1 Datei
(`RELEASE.md`). Keine Streu-Änderungen über die deklarierten `files_modified` hinaus.

### Key Link Verification

| From                                       | To                                                          | Via                                            | Status  | Details                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------ | ----------------------------------------------------------- | ---------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `build-iac-runner.yml` (`jobs.build.uses`) | `.github/workflows/_build-template.yml`                     | `workflow_call`                                | ✓ WIRED | Ziel-Datei existiert und deklariert `on.workflow_call`. Input-Kontrakt vollständig erfüllt: alle drei `required: true`-Inputs (`addon-name`, `addon-display-name`, `addon-description`) sind gesetzt; `archs` überschreibt den Default; `notify-ha` bleibt auf Default `true` (wie bei terraform-bridge). Keine unbekannten Inputs — actionlint validiert lokale Reusable-Workflow-Calls und ist grün. |
| `build-iac-runner.yml` (`with.archs`)      | `iac-runner/config.yaml` (`arch`) + `iac-runner/build.yaml` | Matrix-Arch-Fan-out                            | ✓ WIRED | `with.archs: '["amd64"]'`; `config.yaml` `arch: [amd64]` — Verifier-Assertion `yaml.safe_load(archs) == cfg["arch"]` grün. `build.yaml` hat `build_from.amd64: ghcr.io/home-assistant/amd64-base:3.24`, also kein leerer `BUILD_FROM` und kein Hard-Fail im Template-Guard.                                                                                                                            |
| `build-iac-runner.yml` (`with.addon-name`) | Verzeichnisname `iac-runner/`                               | Lookup für build.yaml/config.yaml + Image-Slug | ✓ WIRED | `addon-name: iac-runner` == Verzeichnisname (Verzeichnis existiert, `make validate-addons` listet es). Slug-Step erzeugt daraus `iac_runner`.                                                                                                                                                                                                                                                          |
| `build-iac-runner.yml` (`secrets:`)        | `.github/scripts/notify-ha.sh` (über das Template)          | Pass-through von 4 Secrets                     | ✓ WIRED | Alle vier (`HA_BASE_URL`, `HA_WEBHOOK_ID`, `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`) werden weitergegeben und sind im `workflow_call.secrets`-Block des Templates deklariert (`_build-template.yml:33-45`). Verifier-Assertionen für alle vier grün.                                                                                                                                           |

### Data-Flow Trace (Level 4)

| Artifact               | Wert                 | Quelle                                                    | Produziert echte Daten | Status    |
| ---------------------- | -------------------- | --------------------------------------------------------- | ---------------------- | --------- |
| `build-iac-runner.yml` | Image-Tag            | `_build-template.yml` slug-Step + `config.yaml` `version` | Ja                     | ✓ FLOWING |
| `build-iac-runner.yml` | Dockerfile-`VERSION` | `iac-runner/build.yaml` `args.VERSION` = `0.2.1`          | Ja                     | ✓ FLOWING |
| `build-iac-runner.yml` | `BUILD_FROM`         | `iac-runner/build.yaml` `build_from.amd64`                | Ja                     | ✓ FLOWING |
| `.github/RELEASE.md`   | Tabellenspalte "Tag" | Geparstes `on.push.tags` je Caller (Cross-Check)          | Ja                     | ✓ FLOWING |

Keine hardcodierten Platzhalter, keine statischen Rückfallwerte, keine Mocks im Datenpfad.

### Behavioral Spot-Checks

| Behavior                                       | Command                                                                  | Result                                                                   | Status |
| ---------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------ | ------ |
| Caller-Kontrakt strukturell korrekt            | Task-1-Verifier (`python3`, PyYAML) auf `iac-runner`                     | `OK: build-iac-runner.yml matches the caller contract` (exit 0)          | ✓ PASS |
| Verifier unterscheidet live vs. auskommentiert | derselbe Verifier auf `build-authentik.yml`                              | `FAIL: on.push.tags lacks live authentik/v* glob` (exit 1)               | ✓ PASS |
| Referenz-Analog verhält sich identisch         | derselbe Verifier auf `build-terraform-bridge.yml`                       | `OK` (exit 0)                                                            | ✓ PASS |
| actionlint-Gate                                | `pre-commit run actionlint --all-files`                                  | Passed, exit 0                                                           | ✓ PASS |
| yamllint auf der neuen Datei                   | `pre-commit run yamllint --files .github/workflows/build-iac-runner.yml` | Passed                                                                   | ✓ PASS |
| prettier idempotent auf RELEASE.md             | `pre-commit run prettier --files .github/RELEASE.md` (2×)                | Passed / Passed, Arbeitsbaum bleibt clean                                | ✓ PASS |
| RELEASE.md-Tabelle ↔ Trigger-Realität          | Task-2-Cross-Check                                                       | `OK: RELEASE.md table and prose match every build-*.yml trigger state`   | ✓ PASS |
| Add-on-Struktur unverändert gültig             | `make validate-addons`                                                   | 9/9 Add-ons passed, `iac-runner` inklusive                               | ✓ PASS |
| Nichts publiziert                              | `git rev-parse iac-runner/v0.2.1^{commit}`, `git tag -l '*/v*' \| wc -l` | `455920f…`, `39`                                                         | ✓ PASS |
| Ende-zu-Ende-Publish nach ghcr                 | —                                                                        | Nicht ausgeführt — laut Auftrag und Plan (Truth 7) explizit out of scope | ? SKIP |

Der SKIP begründet kein Human-Verification-Item: Truth 7 fordert ausdrücklich das Gegenteil (nicht triggern), und
`260908-pfp` liefert per Zieldefinition den Workflow, nicht das Image. Die Vertrauensbasis für den ersten echten Lauf
ist die Byte-Parität zum bereits erfolgreich publizierenden `build-terraform-bridge.yml` plus das grüne actionlint-Gate,
das lokale Reusable-Workflow-Calls samt Input-/Secret-Namen prüft.

### Probe Execution

| Probe | Command | Result | Status                                                                                                    |
| ----- | ------- | ------ | --------------------------------------------------------------------------------------------------------- |
| —     | —       | —      | SKIPPED — das Repo hat keine `scripts/*/tests/probe-*.sh`, und weder PLAN noch SUMMARY deklarieren Probes |

### Anti-Patterns Found

| File                                     | Line | Pattern | Severity | Impact                                                                                                      |
| ---------------------------------------- | ---- | ------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `.github/workflows/build-iac-runner.yml` | —    | keine   | —        | grep über `TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER\|placeholder\|coming soon\|not yet implemented` → clean |
| `.github/RELEASE.md`                     | —    | keine   | —        | derselbe grep → clean                                                                                       |

Keine Debt-Marker in den geänderten Dateien, also greift das Debt-Marker-Gate nicht.

### Bekannte, bewusst nicht gewertete Punkte

| Punkt                                                                                                           | Wertung                                                                                                                                                                                                                                                                                      |
| --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fehlendes `timeout-minutes` auf dem Caller-Job                                                                  | Akzeptierte Abweichung, kein Defekt. Der Key ist auf einem `jobs.<id>.uses`-Job illegal (actionlint v1.7.3 lehnt ihn ab); alle 9 Caller lassen ihn weg; die Intention wird von `_build-template.yml:56 timeout-minutes: 45` erfüllt. Truth 4 prüft genau diese Doppelbedingung und ist grün. |
| Neue `terraform-bridge`-Zeile in `.github/RELEASE.md`                                                           | Genehmigte Scope-Erweiterung. Schließt eine vorbestehende Doku-Lücke (liver Tag-Trigger, keine Tabellenzeile); im Commit-Body von `af3dda2` explizit als nicht angefordert ausgewiesen.                                                                                                      |
| `.github/RELEASE.md:82` "The seven callers carry the comment …" — es sind nur noch 6 (`grep -l … \| wc -l` = 6) | Vorbestehende Ungenauigkeit, out of scope. Verifiziert als _nicht_ durch dieses Item eingeführt; kein Gap.                                                                                                                                                                                   |
| `iac-runner/config.yaml` hat keinen `image:`-Key, HA baut lokal                                                 | ℹ️ Info. Exakte Präzedenz `terraform-bridge` (kein `image:`, liver Tag-Trigger, publiziertes ghcr-Image). Die Frage gehört zum Geschwister-Item `260908-pfq`.                                                                                                                                |
| Der bestehende Tag `iac-runner/v0.2.1` feuert nicht rückwirkend                                                 | ℹ️ Info, im PLAN-`follow_up` und im SUMMARY korrekt als Developer-Follow-up ausgewiesen. Kein Zielbestandteil dieses Items.                                                                                                                                                                  |

### Human Verification Required

Keine. Alle sieben Truths sind maschinell und unter dem vom Plan selbst gesetzten Beweisstandard (strukturelle
Assertions gegen geparstes YAML plus Negativkontrolle, Lint-Gates, Nicht-Publikations-Nachweis) verifiziert. Das
Ende-zu-Ende-Publish ist per Auftrag ausgeschlossen und daher kein offener Verifikationspunkt dieses Items.

### Gaps Summary

Keine. Der geforderte Caller existiert, ist substanziell, korrekt an `_build-template.yml` verdrahtet und feuert über
einen echten (nicht auskommentierten) Tag-Trigger; die Image-Benennung bleibt vollständig im Template; die
RELEASE.md-Doku ist jetzt strukturell wahr gegenüber allen 9 `build-*.yml`-Dateien; actionlint, yamllint, prettier und
`make validate-addons` sind grün; und es wurde nachweislich nichts publiziert (`iac-runner/v0.2.1` → `455920f`, 39
Add-on-Tags unverändert).

Zwei Abweichungen aus dem SUMMARY wurden gegengeprüft und bestätigt: das fehlende `timeout-minutes` ist die vorab
genehmigte, technisch erzwungene Abweichung, und die zusätzliche `terraform-bridge`-Zeile ist die genehmigte
Scope-Erweiterung. Beide sind keine Gaps.

---

_Verified: 2026-09-08_ _Verifier: Claude (gsd-verifier)_
