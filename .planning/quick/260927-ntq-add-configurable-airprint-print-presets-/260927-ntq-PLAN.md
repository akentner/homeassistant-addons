---
quick_id: "260927-ntq"
slug: "add-configurable-airprint-print-presets-"
description: "cups: configurable AirPrint print presets (printers[].presets) via *APPrinterPreset PPD stanzas"
date: "2026-09-27"
status: planned
---

# Quick Task: Configurable AirPrint Print Presets (`printers[].presets`)

## Goal

Let an operator declare named AirPrint print presets per printer (e.g. "Duplex Fein", "Entwurf") so iOS's print
sheet shows a preset picker instead of only individual Duplex/Resolution controls nested under "Optionen". Each
preset bundles one or more of that printer's OWN already-existing PPD option/choice pairs into a single
`*APPrinterPreset` PPD stanza (Apple's AirPrint PPD extension, see https://www.cups.org/doc/spec-ppd.html),
injected into the printer's live PPD at add-on startup, after registration, idempotently across restarts.

**Schema-depth decision (resolved during planning, do not re-litigate):** the task brief asked to verify empirically
whether HA's add-on options schema micro-language supports a `presets[]` list-of-objects nested inside the existing
`printers[]` list-of-objects. `make validate-addons` (`internal/validate-addon-config.py`) does **not** check this —
it only validates `arch`/`startup`/`boot`/`ports`/`map`/required top-level fields, never the `schema:` block's own
micro-language rules — so it cannot answer this question, and there is no live HA Supervisor available in this repo
to test against directly. Instead this was resolved via HA's own developer documentation
(https://developers.home-assistant.io/docs/add-ons/configuration/), which states: **"Nested arrays and dictionaries
are supported with a maximum depth of two."** `printers[]` is already a depth-two list-of-objects (list -> object ->
scalar fields); a `presets[]` list-of-objects nested inside one of its entries would be a third level and is **not
representable**. Per the task brief's own fallback instruction, `presets` is therefore a single flattened `str?`
field (documented delimiter-based format below) — implement this directly, do not attempt the nested list form.

**Flattened format:** `presets` is a string of semicolon-separated preset entries, each shaped
`<display-name>|<Key1=Value1 Key2=Value2 ...>` — e.g.
`"Duplex Fein|Duplex=DuplexNoTumble Resolution=1200x600dpi;Entwurf|Duplex=None Resolution=600dpi"`. `|` and `;` are
safe delimiters because neither character is ever in `PRESET_NAME_RE`'s or `PRESET_OPTION_TOKEN_RE`'s allowed
character sets (validated below) — a valid name or option token can never itself contain one, so there is no
escaping ambiguity.

## Must-Haves

- [ ] `PRESET_NAME_RE` and `PRESET_OPTION_TOKEN_RE` exist in `cups/generate_config.py`, validating a preset's display
      name and each `Key=Value` options token per the spec below
- [ ] `slugify_preset_id(name, used_slugs)` derives a de-duplicated PPD keyword identifier from a preset's display
      name (never operator-authored directly)
- [ ] `build_preset_injection_snippet(name, presets_raw)` parses the flattened `presets` string, validates every
      preset (name + every options token), skips invalid presets individually with a `WARNING` (never aborting
      sibling presets or the printer's own registration), and — if at least one preset survives — renders a shell
      fragment that copies the printer's live PPD to a TEMP file, appends validated `*APPrinterPreset` stanzas via an
      unquoted-expansion-safe heredoc, and reloads it via `lpadmin -P`, guarded on `[ -f "$PPD_FILE" ]`
- [ ] Both driver branches in `build_printer_registration()` (`brlaser` and `generic`) call
      `build_preset_injection_snippet()` and append its output (if not `None`) to `lines`, only for printers that
      already passed `enabled`/`NAME_RE`/uri-scheme/driver validation
- [ ] `printers[].presets: str?` added to `cups/config.yaml`'s schema (flattened field, per the schema-depth decision
      above)
- [ ] An invalid preset (malformed options token) is skipped with a `WARNING`, without affecting its sibling presets
      or that printer's own `lpadmin` registration line
- [ ] Two presets that sanitize to the same slug get de-duplicated (`_2`, `_3`, ... suffix)
- [ ] `internal/verify-cups-scaffold.sh` empirically proves: positive case (stanza + option lines + `lpadmin -P`
      reload present, both in the generated script AND on the live on-disk PPD after cupsd starts), negative case
      (invalid preset skipped + `WARNING` logged + sibling preset unaffected), slug-collision case (`_2` suffix)
- [ ] `cups/DOCS.md` documents `printers[].presets` — shape, worked example reusing the real Brother-MFC-7460DN
      Duplex/Resolution combo, discovery via `lpoptions -p <printer> -l`, the schema-depth fallback rationale, and
      an attribution link to cups.org's PPD extensions spec
- [ ] `cups/README.md` Features list mentions the new capability
- [ ] `cups` version bumped by exactly one subpatch via `make update-version ADDON=cups VERSION=<next>` (never a bare
      `X.Y.Z`)
- [ ] `make lint` and `make validate-addons` pass
- [ ] No `Co-Authored-By` line in any commit (repo hard rule)

## Security Notes

This continues the same T-21-01 discipline already established in `cups/generate_config.py` (see the module
docstring and `LOCATION_RE`/`DRIVER_MODEL_RE`): every value that reaches the generated shell script is either
regex-validated before being embedded, or `shlex.quote()`'d. `PRESET_NAME_RE`/`PRESET_OPTION_TOKEN_RE` exclude
quotes, backticks, `$`, and newlines by construction (printable-ASCII allowlists), so the PPD stanza text embedded
into the `cat >> ... <<'PPD_PRESETS_EOF' ... PPD_PRESETS_EOF` heredoc cannot inject shell commands even though the
heredoc body itself is not separately escaped — validate-before-embed is the actual mitigation, the quoted heredoc
delimiter (which suppresses `$`/backtick expansion) is defense in depth on top of that. Printer `name` is already
`NAME_RE`-validated by the time `build_preset_injection_snippet()` runs (called only after the existing
enabled/name/uri/driver `continue` gates), so it is safe to interpolate into the `PPD_FILE`/`TMP_PPD` paths and
`lpadmin -p` argument (quoted via `shlex.quote()` regardless, matching this file's established style).

## Tasks

### T1: Core feature in `cups/generate_config.py` + `cups/config.yaml` schema

**Files:** `cups/generate_config.py`, `cups/config.yaml`

**Action:**

1. Add two new module-level regexes, placed right after `DRIVER_MODEL_RE` (~line 150), matching this file's existing
   comment-then-regex convention:

   ```python
   # Matches a preset's display-name text (the part after the slash in an
   # *APPrinterPreset <slug>/<display-name>: line). Same conservative
   # printable-ASCII-minus-quotes allowlist as LOCATION_RE, but PPD
   # "keyword/text:" line syntax reserves "/" and ":" as delimiters -- a
   # display name containing either would corrupt the stanza's own syntax,
   # so both are excluded here (on top of LOCATION_RE's existing exclusion
   # of quotes/control characters). Same 127-char cap as LOCATION_RE.
   PRESET_NAME_RE = re.compile(r"^[A-Za-z0-9 ,.\-_()]{1,127}$")

   # Matches one "Key=Value" token inside a printers[].presets options
   # string. Key: a PPD option keyword -- starts with a letter, then
   # letters/digits (PPD keyword-length convention, capped at 40 chars).
   # Value: a PPD choice keyword -- starts alphanumeric, then
   # alnum/dot/underscore/hyphen (covers DuplexNoTumble, 1200x600dpi,
   # 600dpi, Auto), capped at 64 chars. This add-on does NOT verify these
   # against the printer's actual live PPD option list (that would require
   # a runtime lpoptions query per printer, out of scope) -- operators
   # discover valid Key/Value pairs themselves via `lpoptions -p <printer>
   # -l` (see cups/DOCS.md), the same command this add-on's DOCS.md already
   # points operators at for the duplex option.
   PRESET_OPTION_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,39}=[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

   # Matches the run of characters slugify_preset_id() collapses to a
   # single underscore when deriving a PPD keyword identifier from a
   # preset's display name.
   _PRESET_SLUG_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_]+")
   ```

2. Add `slugify_preset_id(name: str, used_slugs: set[str]) -> str`, placed right after `parse_server_aliases()`
   (~line 353, before `build_cupsd_conf`):

   ```python
   def slugify_preset_id(name: str, used_slugs: set[str]) -> str:
       """Derive a PPD keyword identifier from a preset's display `name`.

       PPD keyword syntax (the slug half of `*APPrinterPreset <slug>/<name>:`)
       is stricter than PRESET_NAME_RE's display-text allowlist, so this is
       NEVER operator-authored directly: sanitizes to ASCII letters/digits/
       underscore only (any run of other characters -- spaces, commas,
       periods, hyphens, parentheses -- collapses to a single underscore),
       lowercased for consistency, capped at 40 chars (matching
       PRESET_OPTION_TOKEN_RE's own keyword-length convention). A result that
       doesn't start with a letter (all characters stripped, or a leading
       digit) is prefixed with `preset_` -- PPD keywords conventionally start
       with a letter. Collisions against `used_slugs` (already-seen slugs for
       THIS printer -- callers create a fresh set per printer, since PPD
       keyword uniqueness only matters within one printer's own PPD file) are
       de-duplicated by appending `_2`, `_3`, ... -- this is why this function
       takes and mutates a shared `used_slugs` set across every preset on one
       printer, not just a single name in isolation.
       """
       base = _PRESET_SLUG_SANITIZE_RE.sub("_", name.strip().lower()).strip("_")
       if not base or not base[0].isalpha():
           base = f"preset_{base}" if base else "preset"
       base = base[:40]
       slug = base
       suffix = 2
       while slug in used_slugs:
           slug = f"{base}_{suffix}"[:40]
           suffix += 1
       used_slugs.add(slug)
       return slug
   ```

3. Add `_parse_presets_field(raw: str) -> list[tuple[str, str]]` right after `slugify_preset_id()`:

   ```python
   def _parse_presets_field(raw: str) -> list[tuple[str, str]]:
       """Split a printers[].presets flattened string into (name, options) pairs.

       Format: semicolon-separated preset entries, each `<name>|<options>` --
       see PRESET_NAME_RE/PRESET_OPTION_TOKEN_RE's docstrings above for why
       `|` and `;` are safe delimiters (neither character is in either
       regex's allowed charset, so a VALID name/options value can never
       itself contain one). This flattened shape is a deliberate fallback:
       HA's add-on options schema micro-language caps nested list/dict depth
       at two (developers.home-assistant.io/docs/add-ons/configuration/) --
       printers[] is already a depth-two list-of-objects, so a nested
       presets[] list-of-objects would be a third level and cannot be
       expressed in `schema:`. Returns raw, UNVALIDATED pairs -- callers
       validate each half with PRESET_NAME_RE/PRESET_OPTION_TOKEN_RE. An
       entry with no `|` (no options half at all) is skipped here directly
       with a WARNING, since there is no options string left to validate.
       """
       pairs: list[tuple[str, str]] = []
       for chunk in raw.split(";"):
           chunk = chunk.strip()
           if not chunk:
               continue
           if "|" not in chunk:
               print(
                   f"WARNING: skipping malformed presets entry {chunk!r} -- expected "
                   "'<name>|<Key=Value ...>'",
                   flush=True,
               )
               continue
           preset_name, _, preset_options = chunk.partition("|")
           pairs.append((preset_name.strip(), preset_options.strip()))
       return pairs
   ```

4. Add `build_preset_injection_snippet(name: str, presets_raw: str) -> str | None` right after
   `_parse_presets_field()`:

   ```python
   def build_preset_injection_snippet(name: str, presets_raw: str) -> str | None:
       """Render sh that injects validated *APPrinterPreset stanzas into a
       printer's live PPD and reloads it into cupsd.

       Root cause this fixes: Apple's AirPrint PPD extension *APPrinterPreset
       (https://www.cups.org/doc/spec-ppd.html) lets a PPD declare named
       presets bundling several of that printer's OWN existing PPD
       option/choice pairs (e.g. Duplex + Resolution) into one entry iOS's
       print sheet shows as a "Preset"/"Vorlage" list -- without it, iOS only
       shows individual Duplex/Resolution controls nested under "Optionen".
       brlaser's own driver-generated PPDs (and the generic sample.drv PPD)
       ship with no such stanzas.

       Each preset in `presets_raw` (see _parse_presets_field for the
       flattened format) is validated independently: an invalid `name`
       (PRESET_NAME_RE) or any invalid options token (PRESET_OPTION_TOKEN_RE)
       skips THAT preset alone (WARNING, never a partial stanza) --
       validation failure on one preset never affects its siblings or the
       printer's own registration. Surviving presets get a de-duplicated slug
       via slugify_preset_id() (fresh `used_slugs` set per call -- PPD
       keyword uniqueness only matters within one printer's own PPD file)
       and are rendered into `*APPrinterPreset <slug>/<name>: "..." *End`
       stanzas per the extension's documented syntax.

       If at least one preset survives, returns a shell fragment that: guards
       on `[ -f "$PPD_FILE" ]` first -- the brlaser branch's own PPD
       registration is itself conditional on a runtime `lpinfo -m` match, so
       the PPD may legitimately not exist yet; copies the LIVE PPD to a TEMP
       file (never edits /etc/cups/ppd/<name>.ppd in place -- avoids a
       same-file read/write race and guarantees every run starts from the
       CURRENT on-disk PPD, so restarts never compound duplicate stanzas);
       appends the stanzas via a `cat >> "$TMP" <<'PPD_PRESETS_EOF' ...
       PPD_PRESETS_EOF` heredoc (quoted delimiter suppresses $/backtick
       expansion -- defense in depth on top of the regex validation above,
       which already excludes those characters by construction); reloads via
       `lpadmin -p <name> -P "$TMP"` wrapped in an if/else (this script runs
       under `set -e`, so a bare failing lpadmin would abort every
       subsequent printer's registration -- the if/else keeps a reload
       failure non-fatal and logged, matching this file's existing fail-open
       posture); removes the temp file; logs one INFO line naming the
       registered slugs, or WARNINGs for skipped presets.

       Returns None -- writing nothing -- when `presets_raw` is empty/absent,
       or when every preset in it failed validation.
       """
       presets_raw = str(presets_raw or "").strip()
       if not presets_raw:
           return None

       quoted_name = shlex.quote(name)
       used_slugs: set[str] = set()
       stanza_blocks: list[str] = []
       registered_slugs: list[str] = []

       for preset_name, preset_options in _parse_presets_field(presets_raw):
           if not PRESET_NAME_RE.match(preset_name):
               print(
                   f"WARNING: skipping preset for printer '{name}' -- invalid name "
                   f"{preset_name!r}, must match {PRESET_NAME_RE.pattern}",
                   flush=True,
               )
               continue

           tokens = preset_options.split()
           if not tokens or not all(PRESET_OPTION_TOKEN_RE.match(t) for t in tokens):
               print(
                   f"WARNING: skipping preset {preset_name!r} for printer '{name}' -- "
                   f"invalid or empty options {preset_options!r}, every token must match "
                   f"{PRESET_OPTION_TOKEN_RE.pattern}",
                   flush=True,
               )
               continue

           slug = slugify_preset_id(preset_name, used_slugs)
           option_lines = "\n".join(f"*{key} {value}" for key, value in (t.split("=", 1) for t in tokens))
           stanza_blocks.append(f'*APPrinterPreset {slug}/{preset_name}: "\n{option_lines}\n"\n*End')
           registered_slugs.append(slug)

       if not stanza_blocks:
           print(f"INFO: no valid presets for printer '{name}' -- skipping PPD preset injection", flush=True)
           return None

       stanza_text = "\n".join(stanza_blocks)
       slugs_joined = ", ".join(registered_slugs)
       return (
           f'PPD_FILE="/etc/cups/ppd/{name}.ppd"\n'
           f'if [ -f "$PPD_FILE" ]; then\n'
           f'  TMP_PPD="/tmp/{name}-presets.ppd"\n'
           f'  cp "$PPD_FILE" "$TMP_PPD"\n'
           f"  cat >> \"$TMP_PPD\" <<'PPD_PRESETS_EOF'\n"
           f"{stanza_text}\n"
           f"PPD_PRESETS_EOF\n"
           f'  if lpadmin -p {quoted_name} -P "$TMP_PPD"; then\n'
           f'    echo "registered presets for printer {name}: {slugs_joined}"\n'
           f"  else\n"
           f'    echo "WARNING: lpadmin -P failed while registering presets for printer {name}" >&2\n'
           f"  fi\n"
           f'  rm -f "$TMP_PPD"\n'
           f"else\n"
           f'  echo "WARNING: PPD file $PPD_FILE not found -- skipping preset registration for printer '
           f'{name}" >&2\n'
           f"fi"
       )
   ```

5. In `build_printer_registration()` (~line 689), wire the call into BOTH driver paths:
   - Directly after the existing `lines.append(build_brlaser_registration_snippet(name, uri, driver_model,
     location))` line (still before that branch's `continue`), add:
     ```python
     preset_snippet = build_preset_injection_snippet(name, str(entry.get("presets", "") or ""))
     if preset_snippet is not None:
         lines.append(preset_snippet)
     ```
   - Directly after the existing `lines.append(f'echo "registered printer: {name}"')` line at the end of the
     generic-driver branch, add the identical two-line block.

   Do this ONLY at these two call sites (both already reached only after the existing
   `enabled`/`NAME_RE`/uri-scheme/driver `continue` gates) — a printer entry that failed earlier validation never
   reaches either call site, so its `presets` are correctly never processed.

6. Update the module's top-of-file docstring (~line 33-49): in the `/tmp/register-printers.sh:` bullet, right after
   the existing sentence ending "...for Brother monochrome laser/LED printers with no real PostScript support.",
   append (same 4-space continuation indentation as the surrounding bullet text):

   ```
       Each entry's optional `presets` field injects Apple's AirPrint PPD
       extension `*APPrinterPreset <slug>/<display-name>: "..." *End` stanzas
       (see cups.org/doc/spec-ppd.html) into that printer's live PPD after its
       own registration line above -- bundling one or more of that printer's
       OWN already-existing PPD option/choice pairs (e.g. Duplex + Resolution)
       into a single named entry iOS's print sheet shows as a "Preset"/
       "Vorlage" list, instead of separate Duplex/Resolution controls nested
       under "Optionen". `presets` is a flattened `<name>|<Key=Value> ...;...`
       string, not a nested options-schema list -- HA's add-on options schema
       micro-language caps list/dict nesting at depth two
       (developers.home-assistant.io/docs/add-ons/configuration), and
       `printers[]` is already a depth-two list-of-objects, so a `presets[]`
       list-of-objects nested inside it would be a third level and cannot be
       expressed in `schema:` (see `build_preset_injection_snippet` for the
       parser). Injection always operates on a TEMP copy of the printer's
       CURRENT on-disk PPD (`cp` then `cat >>` then `lpadmin -P`, never
       editing `/etc/cups/ppd/<name>.ppd` in place), so this is idempotent
       across restarts exactly like the brlaser PPD resolution above: every
       start first (re)generates a fresh, preset-free PPD for that printer,
       and only then does this step append presets to that fresh copy --
       never compounding duplicate stanzas across restarts.
   ```

7. In `cups/config.yaml`, add `presets: str?` as the last field of the `printers:` schema list, right after
   `driver_model: str?`:
   ```yaml
     printers:
       - name: str
         uri: str
         enabled: bool?
         location: str?
         driver: "list(generic|brlaser)?"
         driver_model: str?
         presets: str?
   ```
   Do not add anything to the top-level `options:` block's `printers: []` default — no per-field default is needed
   for an item inside an empty list.

**Verify:**
```bash
cd cups && python3 -c "import ast; ast.parse(open('generate_config.py').read())"
python3 -c "
import yaml
d = yaml.safe_load(open('cups/config.yaml'))
assert d['schema']['printers'][0]['presets'] == 'str?', d['schema']['printers'][0]
print('config.yaml schema OK')
"
make validate-addons
```

**Done:** `generate_config.py` compiles; `PRESET_NAME_RE`, `PRESET_OPTION_TOKEN_RE`, `slugify_preset_id`,
`_parse_presets_field`, `build_preset_injection_snippet` all exist with the signatures/behavior above; both driver
branches in `build_printer_registration()` call `build_preset_injection_snippet()`; `config.yaml`'s `printers[]`
schema carries `presets: str?`; `make validate-addons` passes.

---

### T2: Empirical proof in `internal/verify-cups-scaffold.sh`

**Files:** `internal/verify-cups-scaffold.sh`

**Action:**

1. Extend the fixture `options.json` heredoc (near the top of the script) so the two existing printer entries carry
   a `presets` field:
   - `testprinter` (generic driver) — add `"presets": "Draft Mode|PageSize=A4 Duplex=None;Bad Preset|Duplex=None Resolution="`
     (first preset valid; second deliberately has a malformed `Resolution=` token with no value, to prove the
     negative/skip case without affecting the first).
   - `brlasertest` (brlaser driver, real Brother-MFC-7460DN PPD) — add `"presets": "Duplex Fein|Duplex=DuplexNoTumble Resolution=1200x600dpi;Test Preset|Duplex=None Resolution=600dpi;Test  Preset|Duplex=DuplexTumble Resolution=600dpi"`
     (first preset is the real worked-example combo from cups/DOCS.md; the second and third — "Test Preset" and
     "Test  Preset", note the double space in the third — sanitize to the identical slug `test_preset`, proving the
     collision-dedup case).

2. After the existing "Checking brlaser driver registration (D-14)..." block (which already reads
   `/etc/cups/ppd/brlasertest.ppd` into `BRLASER_PPD`) and before "Checking for legacy-unicast reflector slot
   exhaustion (D-08)...", insert a new section:

   ```bash
   yellow "Checking AirPrint preset injection (printers[].presets)..."
   REGISTER_SCRIPT=$(docker exec "${CONTAINER_NAME}" cat /tmp/register-printers.sh)
   PRESET_LOGS=$(docker logs "${CONTAINER_NAME}" 2>&1)

   # Positive case: brlasertest's "Duplex Fein" preset survives validation and
   # is rendered into a *APPrinterPreset stanza with its Duplex/Resolution
   # *Key lines, plus a lpadmin -P reload call -- all inside the GENERATED
   # script (proves generate_config.py's own output).
   if echo "${REGISTER_SCRIPT}" | grep -qF '*APPrinterPreset duplex_fein/Duplex Fein: "'; then
       green "   PASS: *APPrinterPreset stanza generated for 'Duplex Fein'"
   else
       red "   FAIL: missing *APPrinterPreset stanza for 'Duplex Fein'"
       FAIL=1
   fi
   if echo "${REGISTER_SCRIPT}" | grep -qF '*Duplex DuplexNoTumble' \
       && echo "${REGISTER_SCRIPT}" | grep -qF '*Resolution 1200x600dpi'; then
       green "   PASS: preset option lines present (*Duplex/*Resolution)"
   else
       red "   FAIL: missing preset *Duplex/*Resolution option lines"
       FAIL=1
   fi
   if echo "${REGISTER_SCRIPT}" | grep -qE 'lpadmin -p brlasertest -P '; then
       green "   PASS: lpadmin -P reload call present for brlasertest"
   else
       red "   FAIL: missing lpadmin -P reload call for brlasertest"
       FAIL=1
   fi

   # Slug collision: "Test Preset" and "Test  Preset" (double space) sanitize
   # to the same base slug -- the second must get a de-duplicated _2 suffix,
   # never silently overwrite or drop the first.
   if echo "${REGISTER_SCRIPT}" | grep -qF '*APPrinterPreset test_preset/Test Preset: "' \
       && echo "${REGISTER_SCRIPT}" | grep -qF '*APPrinterPreset test_preset_2/Test  Preset: "'; then
       green "   PASS: slug collision de-duplicated (test_preset / test_preset_2)"
   else
       red "   FAIL: slug collision not de-duplicated as expected"
       FAIL=1
   fi

   # Negative case: testprinter's "Bad Preset" has an invalid options token
   # (Resolution= with no value) and must be skipped entirely -- its sibling
   # "Draft Mode" preset must still register, proving one bad preset does not
   # take down the others, and a WARNING is logged.
   if echo "${REGISTER_SCRIPT}" | grep -qF '*APPrinterPreset draft_mode/Draft Mode: "'; then
       green "   PASS: valid sibling preset 'Draft Mode' still registered"
   else
       red "   FAIL: 'Draft Mode' preset missing -- a sibling invalid preset should not affect it"
       FAIL=1
   fi
   if echo "${REGISTER_SCRIPT}" | grep -qF 'Bad Preset'; then
       red "   FAIL: invalid 'Bad Preset' (malformed options token) was NOT skipped from the generated script"
       FAIL=1
   else
       green "   PASS: invalid 'Bad Preset' skipped from the generated script"
   fi
   if echo "${PRESET_LOGS}" | grep -qF "invalid or empty options"; then
       green "   PASS: WARNING logged for the skipped invalid preset"
   else
       red "   FAIL: no WARNING logged for the skipped invalid preset"
       FAIL=1
   fi

   # End-to-end proof: the live PPD files on disk actually carry the injected
   # stanzas after lpadmin -P reloaded them -- not just present in the
   # generated script, but proven to have actually run.
   LIVE_BRLASER_PPD="${BRLASER_PPD}"
   if echo "${LIVE_BRLASER_PPD}" | grep -qF '*APPrinterPreset duplex_fein/Duplex Fein: "'; then
       green "   PASS: brlasertest.ppd carries the injected preset stanza on disk"
   else
       red "   FAIL: brlasertest.ppd does not carry the injected preset stanza"
       FAIL=1
   fi
   LIVE_GENERIC_PPD=$(docker exec "${CONTAINER_NAME}" cat /etc/cups/ppd/testprinter.ppd 2>/dev/null || true)
   if echo "${LIVE_GENERIC_PPD}" | grep -qF '*APPrinterPreset draft_mode/Draft Mode: "'; then
       green "   PASS: testprinter.ppd carries the injected preset stanza on disk"
   else
       red "   FAIL: testprinter.ppd does not carry the injected preset stanza"
       FAIL=1
   fi
   ```

   Note: `BRLASER_PPD` is already populated earlier in the script (the existing D-14 block reads
   `/etc/cups/ppd/brlasertest.ppd` into it) — reuse it via `LIVE_BRLASER_PPD="${BRLASER_PPD}"` rather than a second
   `docker exec`.

3. Do not touch any of the script's pre-existing assertions (Location, ServerAlias, admin provisioning, D-08, etc.)
   — this is purely additive.

**Verify:**
```bash
bash -n internal/verify-cups-scaffold.sh
```
Full empirical run requires Docker (~2-3 min) and is the actual proof of this feature — run it for real:
```bash
bash internal/verify-cups-scaffold.sh
```

**Done:** `bash -n` passes; the script contains the new preset-related assertions described above; a full
`internal/verify-cups-scaffold.sh` run (Docker available) prints `ALL CHECKS PASSED` with every new preset assertion
green.

---

### T3: Docs + version bump

**Files:** `cups/DOCS.md`, `cups/README.md`, `cups/config.yaml`, `cups/build.yaml`

**Action:**

1. **`cups/DOCS.md`** — in the `## Printers` table (the one listing `name`/`uri`/`enabled`/`location`/`driver`/
   `driver_model`), add a row:
   `| \`presets\` | \`str?\` | — | Optional AirPrint print presets bundling this printer's own PPD option/choice pairs into named entries iOS's print sheet shows as a picker. See [Printer presets](#printer-presets) below. |`

   Add a new `### Printer presets` subsection right after the existing `### Printer driver` subsection and before
   `## Design notes`:

   ```markdown
   ### Printer presets

   `presets` (optional) declares named AirPrint print presets for a printer, using Apple's `*APPrinterPreset` PPD
   extension (see [cups.org's PPD extensions spec](https://www.cups.org/doc/spec-ppd.html)). Each preset bundles one
   or more of that printer's OWN existing PPD option/choice pairs (e.g. Duplex + Resolution) into a single named
   entry iOS's print sheet shows as a "Preset"/"Vorlage" picker — instead of separate Duplex/Resolution controls
   nested under "Optionen".

   Format: a single string of semicolon-separated presets, each shaped `<display-name>|<Key1=Value1 Key2=Value2 ...>`:

   ```yaml
   printers:
     - name: "Brother-MFC-7460DN"
       uri: "socket://192.168.178.44:9100"
       driver: "brlaser"
       driver_model: "MFC-7460DN"
       presets: "Duplex Fein|Duplex=DuplexNoTumble Resolution=1200x600dpi;Entwurf|Duplex=None Resolution=600dpi"
   ```

   **Discovering valid Key/Value pairs:** run `lpoptions -p <printer-name> -l` against the running add-on (the same
   command the [duplex design note](#design-notes) already points operators at) — each line is
   `Keyword/Display Text: choice1 *default-choice choice2 ...`; use the `Keyword` and one of its `choice` values as
   one `Key=Value` token. Only reference option/choice pairs that already exist in THAT printer's own generated PPD
   — this add-on does not verify presets against the live PPD at generate time.

   **Why a flattened string, not a nested options list:** Home Assistant's add-on options schema micro-language caps
   nested list/dict depth at two (see the [add-on configuration docs](https://developers.home-assistant.io/docs/add-ons/configuration/)).
   `printers[]` is already a depth-two list-of-objects, so a `presets[]` list-of-objects nested inside one of its
   entries would be a third level and cannot be expressed in `schema:`.

   Invalid presets (a malformed name or an options token that doesn't look like `Key=Value`) are skipped
   individually, logged as a `WARNING`, and never affect sibling presets or that printer's own registration.
   Presets are injected into the printer's live PPD (a TEMP copy, never in place) and reloaded via `lpadmin -P` at
   every add-on start — idempotent across restarts, same as the rest of this add-on's generated configuration.
   ```

   Add one more paragraph to `## Design notes` (after the existing "Printer `location`..." paragraph and before the
   "Generic PostScript over a raw socket..." paragraph, or at the end of the section — match the file's existing
   flow), documenting the schema-depth decision:

   ```markdown
   **AirPrint print presets via `*APPrinterPreset` (`printers[].presets`).** iOS's print sheet only shows individual
   Duplex/Resolution/etc. controls nested under "Optionen" unless a printer's PPD declares named presets via Apple's
   `*APPrinterPreset` extension — neither brlaser's driver-generated PPDs nor the generic `sample.drv` PPD ship any.
   `generate_config.py`'s `build_preset_injection_snippet()` validates each configured preset (display name against
   `PRESET_NAME_RE`, every `Key=Value` options token against `PRESET_OPTION_TOKEN_RE`) and, for every printer with at
   least one valid preset, appends the resulting stanzas to a TEMP copy of that printer's live PPD and reloads it via
   `lpadmin -P` — never editing the live PPD in place, so this is idempotent across restarts exactly like the
   brlaser PPD resolution above. `presets` is a flattened string (`<name>|<Key=Value> ...;...`), not a nested
   options-schema list, because HA's schema micro-language caps list/dict nesting at depth two and `printers[]`
   already uses both levels.
   ```

2. **`cups/README.md`** — add one bullet to the `## Features` list (after the existing "Multiple printers
   configurable..." bullet):
   ```markdown
   - Optional named AirPrint print presets per printer (`printers[].presets`) — bundles existing option/choice pairs
     (e.g. Duplex + Resolution) into a single named entry iOS's print sheet shows as a picker, via Apple's
     `*APPrinterPreset` PPD extension
   ```

3. **Version bump** — current version in `cups/config.yaml` is `0.1.0-8`; bump exactly one subpatch to `0.1.0-9`.
   Run:
   ```bash
   make update-version ADDON=cups VERSION=0.1.0-9
   ```
   Always pass the explicit full `X.Y.Z-N` string, never a bare `X.Y.Z` — a bare version resets the subpatch and has
   previously corrupted a release tag in this repo (root CLAUDE.md hard rule). If the command also creates/pushes a
   git tag and the push step fails (no remote credentials in this environment), that is non-fatal — the three
   version files being correctly updated on disk is what matters; note the skipped/failed tag push in the SUMMARY.

**Verify:**
```bash
grep -c 'presets' cups/DOCS.md            # expect > 0
grep -c 'presets' cups/README.md          # expect > 0
grep 'version:' cups/config.yaml          # expect "0.1.0-9"
grep 'VERSION:' cups/build.yaml           # expect "0.1.0"
make lint
make validate-addons
```

**Done:** `cups/DOCS.md` documents `printers[].presets` with the worked example, discovery instructions, and
schema-depth rationale; `cups/README.md` Features list mentions the capability; `cups/config.yaml` reports
`0.1.0-9`; `cups/build.yaml`'s `VERSION` arg reports `0.1.0`; `make lint` and `make validate-addons` pass.

## Files Changed

- `cups/generate_config.py` (2 new regexes, `slugify_preset_id`, `_parse_presets_field`,
  `build_preset_injection_snippet`, 2 call sites in `build_printer_registration`, module docstring paragraph)
- `cups/config.yaml` (`printers[].presets: str?` schema field, version bump)
- `cups/build.yaml` (`VERSION` arg, updated by `make update-version`, base version unchanged — subpatch bump only)
- `internal/verify-cups-scaffold.sh` (fixture `presets` fields on both existing printer entries + new assertion
  block: positive, negative, slug-collision, live-PPD end-to-end proof)
- `cups/DOCS.md` (new `### Printer presets` subsection + table row + Design notes paragraph)
- `cups/README.md` (Features bullet)

## Out of Scope

- The nested `presets[]` list-of-objects schema form — confirmed unsupported by HA's own docs (max nesting depth
  two), not attempted
- `network-tools/` — untouched
- Phase 21's still-pending old-add-on removal (Task 4 of `21-03-PLAN.md`) — untouched
- Deploying this add-on to `haos-op3050-1` — deployment happens separately, later, not part of this task
- Live validation of preset Key/Value pairs against a printer's actual PPD option list at generate time (operators
  are responsible for using real values discovered via `lpoptions -p <printer> -l`)
