See https://docs.goauthentik.io/docs/releases/2026.8#fixed-in-202681

See <https://docs.goauthentik.io/docs/releases/2026.8>

## What's Changed

- blueprints: emit draft-07 definitions instead of $defs (cherry-pick #24981 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24985>
- website/docs: add object attributes doc (cherry-pick #24437 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/24988>
- providers/oauth2: fix dcr missing csrf_exempt (cherry-pick #24983 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/24989>
- web/admin: fix missing preview banner for object attributes (cherry-pick #24982 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24990>
- enterprise/requests: optimize db for requestable apps (cherry-pick #24984 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24992>
- enterprise/endpoints/connectors/fleet: decrease page size (cherry-pick #24995 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24997>
- web/elements: fix prioritization in form serialization for dotted input-fields (cherry-pick #24987 to version-2026.8)
  by @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24996>
- tasks: aggregate status from logs instead of legacy field (cherry-pick #24792 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25004>
- enterprise/stages/source: configurable failure action (cherry-pick #24963 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25027>
- endpoints: handle error in facts (cherry-pick #25028 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/25032>
- sources/saml: add audience override field for SAML sources (cherry-pick #25029 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25033>
- web: Fix content_left/right layouts. (cherry-pick #25025 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/25030>
- website/docs: add 2026.8 release note for task status change (cherry-pick #25044 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25045>
- outposts/proxy: include query string in post-authentication redirect (cherry-pick #25043 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25058>
- website/docs: preserve host and port in proxy provider nginx redirects (cherry-pick #24991 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25000>
- core: bump goauthentik/fips-python from 3.14.6-slim-trixie-fips to 3.14.7-slim-trixie-fips in /lifecycle/container
  (cherry-pick #25049 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/25060>
- web: Fix mangled nested CSS in compatibility mode. (cherry-pick #25053 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25063>
- ci: require test-rust to pass (cherry-pick #25066 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/25068>
- providers/scim: fix group membership removals (cherry-pick #25024 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/25067>
- website/docs: correct proxy unauthenticated path regex reference (cherry-pick #25077 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25082>
- website/docs: match UI label capitalization and add a style rule (cherry-pick #25080 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25084>
- website/docs: update source field labels renamed in 2026.8 (cherry-pick #25072 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25085>
- packages/django-dramatiq-postgres/broker: chunked purge queryset (cherry-pick #25102 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25106>
- enterprise/requests: fix API schema for grant requests (cherry-pick #25111 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25114>
- web/user: fix request access URL from agent not working (cherry-pick #25113 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25118>
- providers/oauth2: fix token exchange provider lookup for actor/subject (cherry-pick #25110 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25116>
- enterprise/endpoints/connectors/agent: add login_hint to auth_ia (cherry-pick #25122 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25124>
- core: scope user path_startswith filter to the path subtree (cherry-pick #25093 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25145>
- website/docs: agents: add doc (cherry-pick #24826 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/25150>
- sources/telegram: restore next= redirect after pre_authentication_flow (cherry-pick #22762 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25152>
- core: delete all user sessions when user is deactivated (cherry-pick #25088 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25104>
- website/docs: mark deprecated PostgreSQL options and fix listen settings (cherry-pick #25074 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25083>
- web: bump dompurify from 3.4.12 to 3.4.13 in /web (cherry-pick #24892 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25002>
- website/docs: add access requests doc (cherry-pick #24457 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/25161>
- providers/oauth2: send back-channel logout requests when a user is deactivated (cherry-pick #24718 to version-2026.8)
  by @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25109>
- core: bump h2 from 0.4.15 to 0.4.16 (cherry-pick #25183 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/25186>
- stages/email: fix test_email ignoring the given stage (cherry-pick #25166 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25190>
- providers/radius: allow empty message authenticator (cherry-pick #25097 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25197>
- website/docs: add OBO (cherry-pick #25149 to version-2026.8) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/25192>
- enterprise: increase cache duration and ensure summary is cached (cherry-pick #25187 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25199>
- website/docs: 2026.8 release notes: add features and links to docs (cherry-pick #25194 to version-2026.8) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/25201>

**Full Changelog**: <https://github.com/goauthentik/authentik/compare/version/2026.8.0-rc7...version/2026.8.0>

See <https://docs.goauthentik.io/docs/releases/2026.5#fixed-in-202656>

## What's Changed

- web/flow: revert locale-driven flow re-request from FlowExecutor (cherry-pick #24050 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24068>
- lifecycle/container: drop curl and runit (cherry-pick #24008 to version-2026.5) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/24114>
- enterprise/endpoints/connectors/fleet: pass populate_policies (cherry-pick #24108 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24112>
- packages/django-dramatiq-postgres/broker: use positive state filter for pending messages (cherry-pick #24074 to
  version-2026.5) by @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24166>
- endpoints/connectors/agent: fix auth schema for device endpoints (cherry-pick #24164 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24167>
- policies: filter policy engine (cherry-pick #24025 to version-2026.5) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/24168>
- website/docs: cleanup 07-12: refresh contributor guidance (cherry-pick #23969 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24157>
- internal/config: make storage file paths overwritable via env vars (cherry-pick #24177 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24220>
- stages/captcha: fix hcaptcha height (#20901) by @gergosimonyi in <https://github.com/goauthentik/authentik/pull/24216>
- providers/scim: exclude read-only id from group PATCH payload and fix null-members add check (cherry-pick #23950 to
  version-2026.5) by @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24227>
- providers/scim: fix enum warning when de-serializing (cherry-pick #23553 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24231>
- providers/scim: fix non-schema compliant group member removal (cherry-pick #23800 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24229>
- root: fix make gen-diff command (cherry-pick #22548 to version-2026.5) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/24121>
- core: bump pyjwt from 2.11.0 to 2.13.0 (cherry-pick #22562 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/22570>
- core: Form friendly error on uniqueness constraint. (cherry-pick #23864 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23881>
- web/admin: fix app view failing when no events permissions (cherry-pick #24131 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24252>
- root: fix make gen-changelog (cherry-pick #24122 to version-2026.5) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/24260>
- root: in-process per-IP rate throttle (#23015) by @gergosimonyi in
  <https://github.com/goauthentik/authentik/pull/24217>

**Full Changelog**: <https://github.com/goauthentik/authentik/compare/version/2026.5.5...version/2026.5.6>

See <https://docs.goauthentik.io/docs/releases/2026.5#fixed-in-202655>

## What's Changed

- tests/openid_conformance: migrate to upstream images (cherry-pick #23828 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23834>
- endpoints: handle exception in connector controller sync setup (cherry-pick #23852 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23854>
- web/flows: fix race condition in continuous login and support source stages in authentication flows (cherry-pick
  #23049 to version-2026.5) by @GirlBossRush in <https://github.com/goauthentik/authentik/pull/23558>
- web: fix table refresh button not refreshing table data (cherry-pick #23780 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23878>
- web/admin: licensing: add usage totals (cherry-pick #23665 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23668>
- web: Fix Log Viewer Intersection Observer. (cherry-pick #23861 to version-2026.5) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/23949>
- stages/email: fix ungrammatical expiry time in password reset templates (cherry-pick #22758 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23952>
- website/docs: cleanup 07-12: update integration routes (cherry-pick #23960 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23975>
- website/docs: cleanup 07-12: update documentation URLs (cherry-pick #23961 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23976>
- website/docs: cleanup 07-12: fix Admin interface tab label (cherry-pick #23965 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23982>
- providers/scim: improve error display when error doesn't conform to scim schema (cherry-pick #23955 to version-2026.5)
  by @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23957>
- lib/sync/outgoing: fix discover running for each page (cherry-pick #24016 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24019>
- website/docs: 2026.5: remove preview tag from mtls stage doc by @dominic-r in
  <https://github.com/goauthentik/authentik/pull/23981>
- api/search: add number and boolean support in AKQL queries on JSON fields (#23418) (cherry-pick #24028 to
  version-2026.5) by @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24033>
- sources/oauth: improve id_token validation for apple source (cherry-pick #24017 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24020>
- packages/django-dramatiq-postgres/broker: close unusable PostgreSQL connections (cherry-pick #24023 to version-2026.5)
  by @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/24035>
- security: automated internal backport of patch 1822.sec.patch to authentik-2026.5 by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/24059>
- security: automated internal backport of patch 1817.sec.patch to authentik-2026.5 by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/24058>
- security: automated internal backport of patch 1887.sec.patch to authentik-2026.5 by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/24060>
- security: automated internal backport of patch 1919.sec.patch to authentik-2026.5 by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/24061>
- security: automated internal backport of patch 1934.sec.patch to authentik-2026.5 by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/24062>
- website/docs: release notes for 2026.2.6 (cherry-pick #24069 to version-2026.5) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/24071>
- website/docs: release notes for 2026.5.5 (cherry-pick #24070 to version-2026.5) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/24073>

**Full Changelog**: <https://github.com/goauthentik/authentik/compare/version/2026.5.4...version/2026.5.5>

See <https://docs.goauthentik.io/docs/releases/2026.5#fixed-in-202654>

## What's Changed

- website/integrations: dokuwiki: add post logout and logout urls (cherry-pick #22984 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/22985>
- website/docs: additional scim provider docs (cherry-pick #22135 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23003>
- root: bump pyo3 (cherry-pick #23036 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23038>
- website/docs: document SCIM source trust model and security implications (cherry-pick #22535 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23125>
- web: Fix user list default paths. (cherry-pick #23062 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23127>
- web/i18n: Fix stale flow locale, unsynchronized locale selector options (cherry-pick #23007 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23148>
- web: Fix stale clipboard tokens, untranslated labels (cherry-pick #23063 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23143>
- website/docs: add Splunk event forwarding docs (cherry-pick #22938 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23163>
- core: fix Invitation Emails Ignoring Selected Template (cherry-pick #23122 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23133>
- packages/django-dramatiq-postgres/broker: purge at start of loop to ensure it runs (cherry-pick #23185 to
  version-2026.5) by @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23188>
- web/stages/identification: Fix passkey autofill dropdown not showing on the identification stage (cherry-pick #23187
  to version-2026.5) by @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23189>
- website/docs: fix broken custom email template example (cherry-pick #23191 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23192>
- packages/django-postgres-cache: remove custom get_or_set implementation (cherry-pick #23182 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23213>
- website: migrate brand assets to pkg (cherry-pick #22336 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23222>
- packages/django-postgres-cache: fix naive datetime warning (cherry-pick #23033 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23235>
- packages/django-dramatiq-postgres/broker: fix race condition in broker causing completed tasks to be repeated
  (cherry-pick #23218 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23257>
- website/docs: improve email authenticator docs (cherry-pick #23226 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23263>
- website/docs: remove colons from release notes (cherry-pick #23311 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23312>
- website/docs: clarify user and group filtering on scim provider (cherry-pick #22502 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23358>
- root: Fix SECURITY.md versions (cherry-pick #23370 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23372>
- website/docs: sources: remove support_level labels from docs (cherry-pick #23389 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23391>
- core: bump goauthentik/fips-debian and fips-python in /lifecycle/container (cherry-pick #23362 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23384>
- website/docs: fix 2026.5 release notes mentioning docker-compose.yml (cherry-pick #23385 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23400>
- providers/scim: allow failures during discovery (cherry-pick #23357 to version-2026.5) by @authentik-automation[bot]
  in <https://github.com/goauthentik/authentik/pull/23365>
- website/docs: Add improved akql docs (cherry-pick #22693 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23497>
- providers/scim: account for users with no email during discovery (cherry-pick #23417 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23485>
- web/admin: fix spacing issues in wizard (cherry-pick #23484 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23488>
- policies: skip cache invalidation on User last_login update (cherry-pick #23159 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23421>
- tasks: avoid useless query on monitoring_set (cherry-pick #23161 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23424>
- packages/django-postgres-cache: avoid regex queries when listing keys if possible (cherry-pick #23160 to
  version-2026.5) by @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23423>
- brands: select_related models accessed in the hot path (cherry-pick #23162 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23524>
- sources/ldap: avoid re-creating connections to LDAP server (cherry-pick #23520 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23525>
- tasks/schedules: fix paused schedules getting unpaused on startup (cherry-pick #23521 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23527>
- core: preserve encoded avatar URLs (cherry-pick #23225 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23394>
- providers/\*: fix missing declaration for can_discover for outgoing sync providers (cherry-pick #23035 to
  version-2026.5) by @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23233>
- website/docs: improve service account docs (cherry-pick #22145 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/22885>
- website: upgrade postman dep to fix pipeline by @PeshekDotDev in <https://github.com/goauthentik/authentik/pull/23571>
- core: bump pydantic from 2.13.3 to 2.13.4 (cherry-pick #22207 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23570>
- providers/oauth: Properly return error via post and for request objects (cherry-pick #23037 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23529>
- docs: Americanize and minor fixes (cherry-pick #22600 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/22604>
- website/docs: clean up source docs (cherry-pick #23374 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23397>
- website/docs: add expression policy example for welcome emails on user creation (cherry-pick #23486 to version-2026.5)
  by @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23579>
- website/docs: update release notes for 2026.5.4 (cherry-pick #23576 to version-2026.5) by @authentik-automation[bot]
  in <https://github.com/goauthentik/authentik/pull/23586>
- tasks: add pre_delete for TasksModel to avoid OOM when deleting object with many tasks linked (cherry-pick #23664 to
  version-2026.5) by @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23666>
- packages/ak-common/config: coerce file:// and env:// values to their native type (cherry-pick #23758 to
  version-2026.5) by @rissson in <https://github.com/goauthentik/authentik/pull/23759>
- core: handle missing tenant in setup migration (cherry-pick #23034 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23762>
- sources/ldap: optimize the connection endpoints (cherry-pick #23761 to version-2026.5) by @authentik-automation[bot]
  in <https://github.com/goauthentik/authentik/pull/23765>
- providers/ldap: remove incorrect validation for code authenticator extraction (cherry-pick #23006 to version-2026.5)
  by @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23767>
- root: update crossbeam-epoch (cherry-pick #23794 to version-2026.5) by @authentik-automation[bot] in
  <https://github.com/goauthentik/authentik/pull/23795>
- ci: remove GHA-based cherry-pick (cherry-pick #23801 to version-2026.5) by @authentik-cherry-pick[bot] in
  <https://github.com/goauthentik/authentik/pull/23803>
- website/docs: add release notes for `2026.2.5` (cherry-pick #23816 to version-2026.5) by @authentik-cherry-pick[bot]
  in <https://github.com/goauthentik/authentik/pull/23820>
- website: upgrade postman again to fix pipeline by @PeshekDotDev in
  <https://github.com/goauthentik/authentik/pull/23824>
- web: Fix outline selector, lack of outline on focused checkboxes. (cherry-pick #23260 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23825>
- stages/authenticator_webauthn: disable prevent_duplicate_devices by default (cherry-pick #23823 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23826>
- web, core: Fix server-side message race condition, type mismatch. (cherry-pick #23151 to version-2026.5) by
  @authentik-automation[bot] in <https://github.com/goauthentik/authentik/pull/23584>
- web: Invitation Wizard Clean Up, Form Validation Fixes (cherry-pick #23316 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23811>
- website/docs: update release notes for 2026.5.4 again (cherry-pick #23836 to version-2026.5) by
  @authentik-cherry-pick[bot] in <https://github.com/goauthentik/authentik/pull/23838>

**Full Changelog**: <https://github.com/goauthentik/authentik/compare/version/2026.5.3...version/2026.5.4>
