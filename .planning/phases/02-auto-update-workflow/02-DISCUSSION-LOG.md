# Phase 2: Auto-Update Workflow - Discussion Log

**Session:** 2026-04-04 **Participants:** User, Claude

---

## Area 1: Add-on Discovery

**Question:** Wie soll der Workflow die zu prüfenden Add-ons finden?

| Option               | Description                                                                              |
| -------------------- | ---------------------------------------------------------------------------------------- |
| Dynamisch via find ✓ | `find . -maxdepth 2 -name .upstream.yaml` — auto-entdeckt alle Add-ons                   |
| Hardcodierte Liste   | `ADDONS=(fritz-callmonitor2mqtt phone-logger)` — explizit, muss manuell erweitert werden |

**Selected:** Dynamisch via find

---

## Area 2: Commit-Granularität

**Question 1:** Ein Commit pro Add-on oder ein Batch-Commit?

| Option                  | Description                                   |
| ----------------------- | --------------------------------------------- |
| Ein Commit pro Add-on ✓ | Saubere History, einfaches Revert             |
| Ein Batch-Commit        | Einfacherer Code, aber kein granulares Revert |

**Selected:** Ein Commit pro Add-on

**Question 2:** Commit-Message-Format?

| Option                                      | Description                           |
| ------------------------------------------- | ------------------------------------- |
| `chore(addon): update to X.Y.Z` ✓           | Passt zu Conventional Commits im Repo |
| `chore: update {addon} from A.B.C to X.Y.Z` | Zeigt alte Version, aber länger       |
| Du entscheidest                             | Claude wählt                          |

**Selected:** `chore(addon): update to X.Y.Z`

---

## Area 3: Fehlerbehandlung

**Question:** Was passiert wenn der Upstream-Check fehlschlägt?

| Option                      | Description                                         |
| --------------------------- | --------------------------------------------------- |
| Fail-safe: weitermachen ✓   | Fehler ins Log, weitermachen, Job endet als failure |
| Fail-fast: sofort abbrechen | Einfacher Code, aber blockiert alle anderen Updates |
| Fail-safe: Job als success  | Fehler könnte unbemerkt bleiben                     |

**Selected:** Fail-safe, Job endet als failure

---

## Area 4: Workflow-Permissions

**Question 1:** Wer soll als Commit-Author erscheinen?

| Option                  | Description                |
| ----------------------- | -------------------------- |
| `github-actions[bot]` ✓ | Standard, kein Setup nötig |
| Dein GitHub-Account     | Erfordert Konfiguration    |

**Selected:** `github-actions[bot]`

**Question 2:** Soll lint.yml auf auto-update Commits laufen?

| Option                 | Description                                                       |
| ---------------------- | ----------------------------------------------------------------- |
| Ja, lint soll laufen ✓ | Keine Extrasetup nötig — lint.yml push-Trigger greift automatisch |
| Nein                   | Spart CI-Minuten, keine Validierung                               |
| Du entscheidest        | Claude wählt                                                      |

**Selected:** Ja — lint.yml wird durch push auf main getriggert, auch für auto-update Commits
