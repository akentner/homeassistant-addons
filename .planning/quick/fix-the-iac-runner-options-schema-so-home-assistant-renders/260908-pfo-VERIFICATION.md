---
phase: quick
plan: 260908-pfo
verified: 2026-09-08T17:20:00Z
status: human_needed
score: 5/6 must-haves verified
covered_files:
  - ".planning/REQUIREMENTS.md"
  - ".planning/quick/fix-the-iac-runner-options-schema-so-home-assistant-renders/260908-pfo-PLAN.md"
  - ".planning/quick/fix-the-iac-runner-options-schema-so-home-assistant-renders/260908-pfo-SUMMARY.md"
  - "iac-runner/DOCS.md"
  - "iac-runner/config.yaml"
covered_digest: "v1:sha256:32fb4eba7c452990c950ec5739d3014b20553566701dcc8fbb023f10e176aaa7"
behavior_unverified: 1
overrides_applied: 0
behavior_unverified_items:
  - truth:
      "Die HA Add-on Configuration-Seite rendert genau drei auswählbare state_backend-Werte: r2, s3, local — keines der
      drei Regex-Fragment-Artefakte aus dem Screenshot."
    test:
      "Settings -> Add-ons -> Add-on Store -> Drei-Punkt-Menü -> Check for updates; dann iac-runner -> Update auf
      0.2.1-1. Danach Settings -> Add-ons -> IaC Runner -> Configuration öffnen."
    expected:
      "Das state_backend-Control bietet exakt r2, s3 und local an; r2 ist auswählbar (heute ist es das nicht). Kein
      Eintrag lautet 'match(^(r2', 's3' als Fragment oder 'local)$)'."
    why_human:
      "Das Rendering-Verhalten lebt im HA Supervisor / Frontend, nicht im Repo. Der Supervisor muss das Add-on-Manifest
      neu einlesen, bevor der korrigierte Picker erscheint. Kein grep- oder Datei-Check kann diesen Zustand sehen; auf
      diesem Host läuft keine HA-Instanz."
human_verification:
  - test:
      "iac-runner Add-on auf 0.2.1-1 aktualisieren (Store neu laden), dann die Configuration-Seite des Add-ons öffnen."
    expected: "state_backend-Picker zeigt genau r2 / s3 / local; r2 ist auswählbar."
    why_human: "Live-HA-UI-Verhalten; aus dem Repository nicht beweisbar."
follow_ups:
  - item: "iac-runner/cmd/runner/main.go:28 — Doc-Kommentar zitiert weiterhin die alte Schema-Form."
    disposition:
      "Bewusst offen gelassen (kein Gap). Kein go-Toolchain auf diesem Host, reiner Kommentar ohne Runtime-Effekt."
    recommendation: "In den nächsten Phase-18/19-Plan falten, der ohnehin `go build ./...` ausführt."
  - item: ".planning/ROADMAP.md:409 und die Phase-16/17-PLAN.md-Kopien zitieren die alte Form."
    disposition: "Historische Ausführungsprotokolle, planmäßig out of scope."
---

# Quick 260908-pfo: iac-runner state_backend Options-Schema — Verifikationsbericht

**Ziel:** `iac-runner/config.yaml` soll `list(match(^(r2|s3|local)$))` durch `list(r2|s3|local)` ersetzen, damit der
HA-Options-Validator die drei Literale als Auswahlwerte liefert (statt der drei Regex-Fragmente), und im selben
Change-Set die `config.yaml`-Version auf `0.2.1-1` als Add-on-only-Subpatch setzen — `build.yaml` und `README.md`
bleiben auf `0.2.1` bzw. `v0.2.1`. `bind_address` bleibt unberührt.

**Verifiziert:** 2026-09-08 · **Status:** `human_needed` · **Re-Verifikation:** Nein — Erstverifikation

Verifiziert wurde der **gemergte Endzustand auf `main`** (`ca2e686`, `e01cb94`, Merge `3feb119`), nicht ein Worktree.
HEAD liegt bei `812f028`, also deutlich hinter den Item-Commits.

## Zielerreichung

### Observable Truths

| #   | Truth                                                                                                                             | Status                         | Evidenz                                                                                                                                                                                                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | HA-Configuration-Seite rendert genau drei auswählbare `state_backend`-Werte (r2/s3/local), keine Regex-Fragmente                  | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Schema-String ist korrekt und wirksam im Manifest (`iac-runner/config.yaml:35`), aber das Rendering ist Supervisor-/Frontend-Verhalten. Kein HA-Host verfügbar. Siehe Human Verification.                                                                                                          |
| 2   | Der dokumentierte Default `r2` ist tatsächlich schema-valide                                                                      | ✓ VERIFIED                     | `schema.state_backend == "list(r2                                                                                                                                                                                                                                                                  | s3  | local)"`(PyYAML-Roundtrip). Die akzeptierte Menge ist jetzt der Token-Split auf`\|`=`r2`, `s3`, `local`; `options.state_backend: "r2"` (Zeile 22) liegt exakt darin. Identische Form wie 6 funktionierende Sibling-Add-ons (Tabelle unten). |
| 3   | Validierung ist nicht aufgeweitet — genau drei Literale, zweite Schicht intakt                                                    | ✓ VERIFIED                     | Kein trailing `?` am `list(...)` → Feld bleibt required. `iac-runner/internal/statebackend/factory.go:16-27` schaltet auf exakt `r2`/`s3`/`local`, `default:` gibt `ErrUnsupported` (`backend.go:84`); `cmd/runner/main.go:167` ruft `statebackend.New`, `:175` loggt `state_backend_init_failed`. |
| 4   | `bind_address` ist byte-identisch vor und nach der Änderung                                                                       | ✓ VERIFIED                     | Byte-exakter Grep bestanden; im Diff `457e675..HEAD` erscheint Zeile 32 nur als **Kontextzeile** (unverändert). Identisch zu `terraform-bridge/config.yaml:32`.                                                                                                                                    |
| 5   | `internal/validate-versions.sh` besteht mit dem Tripel config `0.2.1-1` / build `0.2.1` / README `v0.2.1`                         | ✓ VERIFIED                     | `make validate-versions` exit 0, druckt für iac-runner `config.yaml: 0.2.1-1 / build.yaml: 0.2.1 / README.md: 0.2.1` und `Version validation passed for all add-ons!`.                                                                                                                             |
| 6   | Keine lebende (nicht-historische) Referenz auf die verschachtelte `list/match`-Form unter `iac-runner/` oder in `REQUIREMENTS.md` | ✓ VERIFIED                     | `grep -rF 'list(match(' iac-runner/ --include='*.yaml' --include='*.md'` → 0 Treffer. `grep -F ... .planning/REQUIREMENTS.md` → 0 Treffer. Positiv-Greps auf `list(r2\|s3\|local)` treffen `DOCS.md:79` und `REQUIREMENTS.md:264`.                                                                 |

**Score:** 5/6 Truths verifiziert (1 vorhanden + verdrahtet, Verhalten nicht ausgeführt)

### Required Artifacts

| Artifact                                       | Erwartet                                                | Status     | Details                                                                                                                                     |
| ---------------------------------------------- | ------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `iac-runner/config.yaml`                       | `schema.state_backend`-Zeile + `version`-Zeile geändert | ✓ VERIFIED | Zeile 3 `version: "0.2.1-1"`, Zeile 35 `state_backend: "list(r2\|s3\|local)"`. Diff-Residuum null — nur diese zwei Body-Zeilen im Commit.   |
| `iac-runner/DOCS.md`                           | Schema-Satz im `state_backend`-Abschnitt korrigiert     | ✓ VERIFIED | Zeile 79 zitiert `list(r2\|s3\|local)`; die `statebackend.New` / `ErrUnsupported`-Klausel ist wörtlich erhalten (Defense-in-Depth-Aussage). |
| `.planning/REQUIREMENTS.md`                    | STBK-01-Bullet korrigiert                               | ✓ VERIFIED | Zeile 264 zitiert `list(r2\|s3\|local)`, Checkbox bleibt `[x]`. Der Revert-Pfad einer späteren Gap-Closure-Runde ist damit geschlossen.     |
| `iac-runner/build.yaml` (unverändert erwartet) | `VERSION` und `RUNNER_VERSION` bleiben `0.2.1`          | ✓ VERIFIED | Zeilen 5-6 unverändert `"0.2.1"`; Datei erscheint in keinem der beiden Item-Commits.                                                        |
| `iac-runner/README.md` (unverändert erwartet)  | Badges bleiben `v0.2.1`                                 | ✓ VERIFIED | Zeilen 62-63 `v0.2.1`; Datei erscheint in keinem der beiden Item-Commits.                                                                   |

### Key Link Verification

| From                               | To                                            | Via                                                          | Status  | Details                                                                                                                                          |
| ---------------------------------- | --------------------------------------------- | ------------------------------------------------------------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `config.yaml schema.state_backend` | `statebackend.New` (`cmd/runner/main.go:167`) | `/data/options.json` → `Options.StateBackend` (`main.go:74`) | ✓ WIRED | JSON-Tag `json:"state_backend"` matcht den Schema-Key; Default `defaultStateBackend = "r2"` (`main.go:29`, gesetzt in `:115`).                   |
| `config.yaml version`              | `build.yaml args.VERSION` + `README.md`-Badge | `internal/validate-versions.sh` Stable-Format-Branch         | ✓ WIRED | Validator liest alle drei Dateien, akzeptiert `-1` als Subpatch und vergleicht Basis `0.2.1`. Läuft zusätzlich als `always_run` Pre-Commit-Hook. |
| `iac-runner/DOCS.md:79`            | `.planning/REQUIREMENTS.md:264`               | Prose-Kopien der Schema-Spezifikation                        | ✓ WIRED | Beide Kopien zitieren jetzt denselben String wie das Manifest. Kein Spec/Impl-Widerspruch mehr, der einen Revert legitimieren könnte.            |

### Data-Flow Trace (Level 4)

| Artifact                 | Wert                   | Quelle                                        | Liefert echte Daten | Status    |
| ------------------------ | ---------------------- | --------------------------------------------- | ------------------- | --------- |
| `iac-runner/config.yaml` | `schema.state_backend` | HA Supervisor liest Manifest → Options-UI     | ja (Manifest-Feld)  | ✓ FLOWING |
| `cmd/runner/main.go`     | `opts.StateBackend`    | `/data/options.json` (Supervisor-geschrieben) | ja                  | ✓ FLOWING |

Keine Hardcoded-Literale, keine Static-Fallbacks, keine Mocks im Pfad. `defaultStateBackend = "r2"` ist ein
dokumentierter Fallback für ein fehlendes `options.json`, kein Stub.

### Behavioral Spot-Checks

| Behavior                                         | Command                                                                                                | Result                                                                  | Status         |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- | -------------- |
| Manifest parst und trägt beide Zielwerte         | `python3 -c "import yaml; d=yaml.safe_load(open('iac-runner/config.yaml')); ..."`                      | `state_backend='list(r2\|s3\|local)'`, `version='0.2.1-1'` → exit 0     | ✓ PASS         |
| `bind_address` byte-exakt                        | `grep -Fq 'bind_address: "match(^auto$\|^(([0-9]{1,3}\\\\.){3}[0-9]{1,3})$)?"' iac-runner/config.yaml` | exit 0                                                                  | ✓ PASS         |
| Add-on-Struktur/Schema-Validator ohne Regression | `python3 internal/validate-addon-config.py iac-runner`                                                 | `Add-on config validation passed.` exit 0                               | ✓ PASS         |
| 3-Datei-Versionsschema                           | `make validate-versions`                                                                               | `Version validation passed for all add-ons!` exit 0                     | ✓ PASS         |
| Repo-weites Lint-Gate                            | `make lint`                                                                                            | exit 0, alle 21 Hooks `Passed` (inkl. prettier, markdownlint, yamllint) | ✓ PASS         |
| Kein lebender Rest der alten Form                | `! grep -rF 'list(match(' iac-runner/ --include='*.yaml' --include='*.md'`                             | 0 Treffer                                                               | ✓ PASS         |
| Diff-Residuum in `config.yaml`                   | `git diff 457e675..HEAD -- iac-runner/config.yaml` inspiziert                                          | genau 2 Body-Zeilen (`version:`, `state_backend:`), sonst Kontext       | ✓ PASS         |
| UI-Rendering des Pickers                         | —                                                                                                      | kein HA-Host verfügbar                                                  | ? SKIP → Human |

`make lint` lief hier **ohne** Prettier-Re-Run: die im SUMMARY beschriebene erste Nicht-Null-Runde war der Autofix
während der Ausführung; auf dem committeten Baum ist alles idempotent grün. Damit ist die SUMMARY-Behauptung unabhängig
reproduziert, nicht nur übernommen.

Es wurden **keine** Go-Tests ausgeführt und keine Go-Datei angefasst — auf diesem Host existiert kein `go`-Binary. Das
ist konsistent mit den Plan-Constraints.

### Requirements Coverage

| Requirement | Source Plan  | Beschreibung                                                                                                         | Status      | Evidenz                                                                                                             |
| ----------- | ------------ | -------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------- |
| STBK-01     | `260908-pfo` | Options-Schema exponiert `state_backend: list(r2\|s3\|local)` mit Default `r2`; gewähltes Backend treibt Credentials | ✓ SATISFIED | `config.yaml:22` (`options.state_backend: "r2"`) + `:35` (Schema); Spec-Text bei `REQUIREMENTS.md:264` nachgezogen. |

Keine orphaned Requirements: `.planning/REQUIREMENTS.md` mappt für dieses Quick-Item nur STBK-01, und der Plan
deklariert genau STBK-01.

### Vergleich mit den Sibling-Add-ons (Konsistenz-Evidenz für Truth 2)

`iac-runner` war der einzige Ausreißer. Alle anderen Add-ons benutzen bereits die reine Literal-Form, und deren
Options-UIs funktionieren:

| Add-on              | Zeile | Schema-String                                                     |
| ------------------- | ----- | ----------------------------------------------------------------- |
| `authentik`         | 34    | `"list(debug\|info\|warning\|error)?"`                            |
| `coding-assistants` | 51    | `"list(opencode\|pi\|crush\|droid\|passthrough)"`                 |
| `gatus`             | 36-37 | `"list(debug\|info\|warning\|error)?"`, `"list(memory\|sqlite)?"` |
| `meridian`          | 40    | `list(debug\|info\|warning\|error)`                               |
| `network-tools`     | 75    | `list(debug\|info\|warning\|error)`                               |
| `phone-logger`      | 107   | `list(DEBUG\|INFO\|WARNING\|ERROR\|CRITICAL)`                     |
| `iac-runner` (neu)  | 35    | `"list(r2\|s3\|local)"` — jetzt gleiche Form                      |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| —    | —    | —       | —        | Keine  |

Kein `TBD`/`FIXME`/`XXX` in den geänderten Dateien, keine Stubs, keine leeren Implementierungen, keine
Hardcoded-Empty-Werte. Debt-Marker-Gate: bestanden.

### Scope-Additionen (geprüft, kein Scope Creep)

Beide Erweiterungen über `iac-runner/config.yaml` hinaus waren user-approved und sind im Endzustand tatsächlich
korrigiert:

- `iac-runner/DOCS.md:79` — korrigiert; der `statebackend.New`/`ErrUnsupported`-Nebensatz ist erhalten geblieben.
- `.planning/REQUIREMENTS.md:264` (STBK-01) — korrigiert. Das ist die sicherheitsrelevante der beiden: STBK-01 ist
  `[x]`, ein späterer Gap-Closure-Pass hätte den alten Spec-Text als Autorität gelesen und die gefixte `config.yaml` als
  non-compliant zurückgedreht.

### Bewusst stehengelassen (kein Gap)

- `iac-runner/cmd/runner/main.go:28` — Doc-Kommentar zitiert weiterhin `list(match(^(r2|s3|local)$))`. Reiner Kommentar,
  null Runtime-Effekt, kein `go`-Binary auf diesem Host → nicht compile-verifizierbar. Als Follow-up erfasst. Das
  Grep-Gate war bewusst per `--include='*.yaml' --include='*.md'` region-limitiert, damit dieser bekannte Rest keine
  künftige Verifikation fälschlich rot färbt.
- `.planning/ROADMAP.md:409`, `16-01-PLAN.md`, `16-03-PLAN.md`, `17-01-PLAN.md` — historische Ausführungsprotokolle.

### Abweichung: zwei Commits statt einem

Der Plan-`<success_criteria>`-Punkt „exactly three files changed, in one atomic commit" wurde als zwei Commits umgesetzt
(`ca2e686` = `config.yaml`, `e01cb94` = `DOCS.md` + `REQUIREMENTS.md`), weil der Batch-Dispatch Per-Task-Atomizität
vorschreibt. **Bewertet wurde der Endzustand:** `git show --name-only ca2e686 e01cb94` listet exakt die drei geplanten
Dateien, der kumulierte Diff ist byte-identisch mit dem, was ein Einzel-Commit erzeugt hätte. Kein Gap.

### Human Verification Required

#### 1. state_backend-Picker in der HA-UI

**Test:** Settings → Add-ons → Add-on Store → Drei-Punkt-Menü → _Check for updates_, dann **iac-runner → Update** auf
`0.2.1-1`. Anschließend Settings → Add-ons → IaC Runner → **Configuration** öffnen.

**Erwartet:** Das `state_backend`-Control bietet genau `r2`, `s3` und `local` an, und `r2` ist auswählbar. Keine der
drei Fragment-Optionen `match(^(r2`, `s3`, `local)$)` aus dem ursprünglichen Screenshot.

**Warum Human:** Das Rendering ist Supervisor-/Frontend-Verhalten. Der Supervisor muss das Add-on-Manifest neu einlesen,
bevor der korrigierte Picker erscheint — die Repo-Änderung allein ist in der UI nicht beobachtbar. Auf diesem Host läuft
keine HA-Instanz, und kein Datei- oder grep-Check kann diesen Zustand sehen.

**Hinweis:** `iac-runner/config.yaml` hat keinen `image:`-Key — der Supervisor baut lokal. Das Update hängt also weder
an einem ghcr-Artifact noch am offenen `iac-runner/v0.2.1`-Tag.

### Gaps Summary

**Keine Gaps.** Alle automatisiert prüfbaren Must-Haves sind im gemergten Endzustand auf `main` bestätigt — unabhängig
nachgerechnet, nicht aus dem SUMMARY übernommen: Schema-String, Subpatch-Version, unangetastetes
`build.yaml`/`README.md`, byte-identisches `bind_address`, beide Prose-Kopien korrigiert, `make validate-versions` /
`validate-addon-config.py` / `make lint` alle exit 0.

Der Status ist `human_needed` statt `passed` aus genau einem Grund: das eigentliche Endziel — „der Operator sieht drei
saubere Optionen und kann `r2` wählen" — ist ein Live-HA-UI-Verhalten. Code und Manifest sind vorhanden und verdrahtet,
das Verhalten ist unbewiesen. Der Plan hatte diesen Check selbst als `<human-check>` deklariert, das SUMMARY als
`D5 / human_judgment: true`; diese Verifikation bestätigt die Einordnung, statt sie wegzudrücken.

---

_Verifiziert: 2026-09-08_ _Verifier: Claude (gsd-verifier)_
