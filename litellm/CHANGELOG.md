## Verify Docker Image Signature

All LiteLLM Docker images are signed with [cosign](https://docs.sigstore.dev/cosign/overview/). Every release is signed
with the same key introduced in
[commit `0112e53`](https://github.com/BerriAI/litellm/commit/0112e53046018d726492c814b3644b7d376029d0).

**Verify using the pinned commit hash (recommended):**

A commit hash is cryptographically immutable, so this is the strongest way to ensure you are using the original signing
key:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/0112e53046018d726492c814b3644b7d376029d0/cosign.pub \
  ghcr.io/berriai/litellm:v1.102.1
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.102.1/cosign.pub \
  ghcr.io/berriai/litellm:v1.102.1
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

## What's Changed

- fix(anthropic): backport #42152 and #42288 to stable/1.102.x for v1.102.1 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42538
- feat(typesafe): backport the jev change set to stable/1.102.x for v1.102.1 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42595
- chore(release): backport #42388 and #41462 to stable/1.102.x by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42618

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.102.0...v1.102.1

## Verify Docker Image Signature

All LiteLLM Docker images are signed with [cosign](https://docs.sigstore.dev/cosign/overview/). Every release is signed
with the same key introduced in
[commit `0112e53`](https://github.com/BerriAI/litellm/commit/0112e53046018d726492c814b3644b7d376029d0).

**Verify using the pinned commit hash (recommended):**

A commit hash is cryptographically immutable, so this is the strongest way to ensure you are using the original signing
key:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/0112e53046018d726492c814b3644b7d376029d0/cosign.pub \
  ghcr.io/berriai/litellm:v1.101.0
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.101.0/cosign.pub \
  ghcr.io/berriai/litellm:v1.101.0
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

## What's Changed

- fix(proxy): emit timing headers and overhead for /v1/messages and /v1/responses by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/38840
- fix(tests): derive the no-cache-read-rate savings baseline from the model map by @tin-berri in
  https://github.com/BerriAI/litellm/pull/38863
- chore(typing): clear Any seams across 47 files, ratchet basedpyright ceilings -3,302 by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/37778
- chore(typing): clear 1.2k basedpyright Any errors across 16 hotspot files by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/36722
- feat(bedrock): honor streaming buffer/sampling config for unbuffered post_call scans by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38722
- feat(cli): set ENABLE_TOOL_SEARCH=true for lite claude by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38942
- fix(proxy): deliver budget alerts on webhook-only alerting and accept ALERTING_WEBHOOK_URL by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/38441
- docs(claude.md): require tests to check behavior, not code structure by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/38772
- chore(newrelic): cover static default_team_settings per-team routing by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/38857
- fix: update stale source URLs and deprecation dates in model cost map by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38801
- feat(ci): close duplicate issues after a 3-day grace period by @mubashir1osmani in
  https://github.com/BerriAI/litellm/pull/38381
- docs(proxy): clarify spend semantics on /v2/user/info and /user/daily/activity by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38883
- fix(guardrails): configure Prompt Security file timeout policy by @davida-ps in
  https://github.com/BerriAI/litellm/pull/38083
- fix(bedrock): stop duplicating Converse config blocks inside inferenceConfig by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38993
- fix(guardrails): exclude images from HiddenLayer v1 scans by @Ashton-Sidhu in
  https://github.com/BerriAI/litellm/pull/29210
- feat(spend_tracking): persist router metadata in spend logs for internal router models by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39001
- fix(vertex_ai): graft default vertex path when api_base has a version-only path by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38986
- fix(proxy): allow unblocking customers via /customer/update by @cat0825 in
  https://github.com/BerriAI/litellm/pull/34696
- feat(openai): support workload identity federation (OIDC token exchange) by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38995
- fix(otel): emit cache token counts on OTel v2 LLM spans by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38716
- feat(proxy): add /v1/responses/input_tokens token counting endpoint by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38997
- fix(docker): bump wolfi-base for glibc 2.44 and pin apk python to 3.13 by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38917
- fix(docker): bump wolfi-base for glibc 2.44 and pin apk python to 3.13 in migrations image by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38973
- feat(friendli): add zai-org/GLM-5.3-Flash model pricing by @Lee-Si-Yoon in
  https://github.com/BerriAI/litellm/pull/38880
- chore(techdebt): clear fresh debt from the 2026-08-29 and 2026-08-30 windows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38884
- fix(bedrock): surface Nova Sonic user transcripts, speech events, and usage in realtime API by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/38597
- fix(guardrails): carry Anthropic url image sources through to guardrails by @samtsai15 in
  https://github.com/BerriAI/litellm/pull/38940
- feat(friendli): add zai-org/GLM-5.3 model pricing by @Lee-Si-Yoon in https://github.com/BerriAI/litellm/pull/38881
- fix(router): apply model renames to the in-memory deployment list by @yatishgoel in
  https://github.com/BerriAI/litellm/pull/38479
- test(e2e): cover SCIM token creation and SCIM API auth in the Admin UI suite by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39027
- feat(gigachat): add native API passthrough routes with spend logging by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38913
- feat(gigachat): add passthrough gigachat route by @KnyazSh in https://github.com/BerriAI/litellm/pull/25886
- feat(complexity-router): add classification_mode to skip classifier on continuation turns by @tin-berri in
  https://github.com/BerriAI/litellm/pull/38861
- fix(proxy): preserve model table columns on master key rotation by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38878
- fix(speech): stop forwarding response_format as a chat param for Gemini TTS by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38819
- fix(proxy): return 200 from /model/block and /model/unblock instead of 500 by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38873
- feat(complexity_router): escalate oversized prompts to a tier that fits before dispatch by @tin-berri in
  https://github.com/BerriAI/litellm/pull/38844
- feat(shadow_eval): target teams and users so JWT-auth traffic can be evaluated by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39015
- fix(anthropic_messages): drain upstream in a detached pump so client … by @nuernber in
  https://github.com/BerriAI/litellm/pull/36008
- refactor(proxy): bound the budget window seed by time instead of request ids by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/38851
- fix(proxy): ship psycopg so partitioned SpendLogs detection actually runs by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/38994
- test(e2e): assert user-observable behavior instead of DOM structure by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39016
- build(rust): configure native extension profiles by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39020
- fix(ui): keep litellm_credential_name from LiteLLM Params JSON when no credential is selected by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39005
- Revert "fix(ui): keep litellm_credential_name from LiteLLM Params JSON when no credential is selected" by
  @yassin-berriai in https://github.com/BerriAI/litellm/pull/39046
- fix(auth): quiet malformed virtual key rejections to stdout by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/38838
- fix(proxy): wire team-level logging callbacks into passthrough endpoints by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/38979
- feat(complexity_router): opt-in modality-based capability routing for image requests by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39032
- fix(ui): let the auto-router scoring tier list follow the theme by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39040
- feat(ui): auto-router controls for context-window escalation by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39054
- fix(redis): coerce env var string types and fix param discovery through decorator wrappers by @koladefaj in
  https://github.com/BerriAI/litellm/pull/30644
- feat(key management): show budget window usage on /key/info by @Thijmen in
  https://github.com/BerriAI/litellm/pull/37044
- fix(websearch): reject invalid explicit search tool selections by @georgeatparallel in
  https://github.com/BerriAI/litellm/pull/38113
- feat(shadow_eval): compare several auto-routers on one job's sampled traffic by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39028
- fix(speech): honor pcm/wav response_format for Gemini TTS and reject unsupported containers by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38868
- fix(proxy): match /v1/audio/speech content-type to the returned audio format by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38798
- test(e2e): drop the two mgmt registry cells no shared-proxy test can cover by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39055
- feat(ui): one classification frequency picker for complexity auto-routers by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39042
- test(e2e/ui): automate 8 manual QA checklist flows by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39025
- fix(key_management): allow non-admin key_type preset transitions on /key/update by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39051
- chore(typing): clear 1.1k basedpyright Any errors across 53 backend files by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38796
- fix(openai): forward reasoning_effort for unknown model aliases instead of failing closed by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39065
- test(e2e-ui): poll credential availability before Test Connect to deflake multi-instance runs by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39073
- feat(ui): modality routing toggle on the auto-router create and edit forms by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39059
- fix(proxy): include litellm_model_table in GET /v2/team/list by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/39045
- fix(bedrock): mask signed request headers in guardrail debug log by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39044
- fix(bedrock): forward aws_external_id in files and batches credential loading by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39066
- fix(mcp): persist alias MCP grants verbatim instead of rewriting to local server ids by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39119
- fix(responses): json-encode object tool call arguments in the chat completions bridge by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/35417
- fix(cost): bill OCR annotation pages via annotation_cost_per_page by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38985
- fix(policy_engine): restore request guardrails list after pipeline allow by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39038
- fix(embeddings): omit encoding_format when the client omits it on OpenAI-compatible calls by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38774
- test: deflake MCP registry state, savings cost map, and MCP identity env reload tests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38891
- feat(helm): add Argo CD PreSync hook and rollout strategy knobs to the componentized chart by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39112
- fix(registry): veo 3.1 pricing tiers + roll up open registry PRs (glm-5.2, Qwen3.8-Flash, gemma-4-31b, scribe_v2,
  fireworks/databricks deepseek v4) + deprecation dates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38990
- test(ui): budget DOM-structure assertions in dashboard tests by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39082
- test(ui): assert DataTable behavior instead of DOM structure by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39084
- test(ui): query the screen instead of the render result by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39085
- fix(ui): stop checkboxes stretching to the full width of a form field by @yatishgoel in
  https://github.com/BerriAI/litellm/pull/39108
- chore: bump litellm-enterprise 0.1.62 -> 0.1.63, litellm-proxy-extras 0.4.91 -> 0.4.92, litellm 1.100.0 -> 1.101.0 by
  @yuneng-berri in https://github.com/BerriAI/litellm/pull/39140
- revert: restore search tool fallback when no router is configured by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39146
- test(websearch): register configured search tool in pre-request hook test by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39074
- feat(proxy): default to the v2 migration resolver, keep v1 as an opt-out by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/31125
- build(deps): bump browserslist to 4.28.8 to clear osv-scan by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39142
- fix(ui): render the skill detail page with theme tokens by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39130
- feat: add Azure AI DeepSeek V4 Flash 0731 pricing by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39023
- fix(streaming): keep response id stable across streamed chunks by @Timik232 in
  https://github.com/BerriAI/litellm/pull/38106
- test(e2e/ui): cover the Budgets page create, edit and delete flows by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39052
- feat(dashscope): add QwenCloud and Qwen AI Platform provider aliases by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39149
- fix(bedrock): forward native structured outputs on Invoke instead of silently inlining the schema by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39070
- test(e2e/ui): cover creating, testing and deleting a guardrail by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39053
- refactor(types): replace Any with precise types across 73 modules by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39104
- feat(models): add Claude Fable 5.1 across Anthropic, Bedrock, Vertex AI, and Azure AI by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39148
- feat(guardrails): add Alice guardrail by @seanyasno-af in https://github.com/BerriAI/litellm/pull/38898
- test(e2e/ui): cover the Logs page filter drawer by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39056
- test(e2e/ui): stop the suite failing on things that are not regressions by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39063
- test(e2e/ui): cover the team Settings tab by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39058
- test(e2e/ui): cover the Usage page activity tabs by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39061
- fix(ui): render the guardrail garden detail page with theme tokens by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39131
- fix(responses): tool call id shape breaks gpt-5 -> claude fallback conversations by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39144
- fix(openai): drop tool_choice when request has no tools on chat completions by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39147
- chore(ci): promote internal staging to main by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39141
- test(ui): pick select options by role instead of by text by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39175
- feat(cost): support time-based off-peak pricing in cost calculation by @Srivatsa03 in
  https://github.com/BerriAI/litellm/pull/31725
- fix(openai): flatten top-level tool schema combinators on chat completions by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38839
- fix(s3): bound s3 object keys and download filenames for long Responses API ids by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39164
- revert: default the proxy back to the v1 migration resolver by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39178
- fix(prometheus): bound requested_model label cardinality on client failure paths by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39136
- feat(ui): add search to the Agent Hub tab and admin agents table by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39155
- fix(anthropic): fix response_format for claude-fable-5-1 on Vertex AI and Bedrock by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39184
- fix: keep litellm_credential_name from LiteLLM Params JSON and gate stored credential attach to proxy admins by
  @yassin-berriai in https://github.com/BerriAI/litellm/pull/39047
- chore(ci): promote internal staging to main by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39186
- test: exempt MockTransport request-shape embedding tests from VCR replay by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39185
- fix(ui): render the logs Tools panel with theme tokens by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39129
- fix(proxy): default max_idle_connection_lifetime to 60s on DB URLs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39134
- fix(mcp): follow tools/list pagination from upstream servers by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39172
- fix(proxy): resolve router model aliases in /utils/supported_openai_params by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39000
- fix(azure): flatten top-level tool schema combinators on Azure chat completions by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38870
- fix(bedrock): route streamed responses-API output through the unified guardrail by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38734
- fix(ui): hide model write affordances from view-only admin sessions by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38872
- fix(cli): quote the Claude Code apiKeyHelper for cmd.exe on Windows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39174
- fix(logging): guarantee max_parallel_requests slot release when streaming logging fails by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/39093
- feat(alerting): slack alerts for per-user daily/monthly spend thresholds and spend anomaly detection by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/38438
- fix(docker): add public Wolfi apk repo to runtime image by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39033
- fix(router): keep order fallback on the requested order level by @emerzon in
  https://github.com/BerriAI/litellm/pull/38969
- test(e2e): cover retry-on-timeout and the context-window fallback by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39197
- fix(budget): reject known estimates over remaining budget under fail_closed_budget_enforcement by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39214
- fix: stop a cleared Team field from blocking personal key creation by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39206
- test: record each e2e test's source location in the JUnit report by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39209
- feat(router): fall back on anthropic safeguard refusals on /v1/messages by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39157
- fix(proxy): report requested model on Anthropic streaming message_start by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/35816
- fix(helm): reuse the generated master key Secret on helm upgrade by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39219
- fix(mcp): report per-server outcomes in aggregate REST tools/list by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39232
- fix(cost-map): retry transient boot fetch failures and recover config deployments dropped by a stale cost map by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39230
- perf(scim): resolve group members with one user table read per member by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39228
- fix(docker): install bedrock-realtime extra in monolith proxy images by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39223
- fix(aiohttp_transport): map transport-internal CancelledError to a retryable ConnectError by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39240
- fix(bedrock): gate Converse cachePoint emission on model prompt caching support by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39210
- fix(datadog_llm_obs): send tool calls, tool results and cache tokens in DD's own fields by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39222
- feat(prometheus): expose per-key and per-team rate limit allowed and used gauges by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39236
- feat(scim): add placeholder listing and merge so a shadowed account can be healed by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39231
- fix: normalize provider-specific cache token fields in OTel v2 usage by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39202
- fix: stop deployment default API key limits leaking into provider requests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39211
- fix(proxy): keep passthrough logging metadata and model_info dicts when team callbacks are wired by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39216
- fix(guardrails): deliver modify_response block as valid SSE on streaming chat and Responses by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39036
- fix(search): forward search-tool params through the router, complete Parallel AI v1 param mapping by @jliounis in
  https://github.com/BerriAI/litellm/pull/37883
- fix(bedrock): stop Converse crashing on bearer-token auth without SigV4 credentials by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39166
- fix(docker): install saml extra in litellm-backend image by @ojensen-berri in
  https://github.com/BerriAI/litellm/pull/39291
- fix(guardrails): run apply_guardrail-only providers in logging_only mode by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39297
- feat(gemini): day-0 pricing for gemini-3.8-flash by @mateo-berri in https://github.com/BerriAI/litellm/pull/39340
- fix(vertex): avoid duplicate DeepSeek OCR model namespace by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39194
- feat(streaming): carry final response cost on streamed usage by default by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39069
- fix(rerank): map provider errors with the resolved provider on sync and async paths by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39176
- test(e2e): read JUnit properties off the real collected pytest Item by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39246
- feat(proxy): configurable display_name for the Anthropic-shaped /v1/models listing by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39238
- fix(helm): scale the classic chart's HPA out at the documented 60 percent CPU by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/35975
- fix(gemini): return enabled thinking content by default by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39160
- fix: run access group key sync UPDATEs on the writer, not the read replica by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39128
- fix(models): registry audit 2026-09-01: openai realtime and long-context tiers, mistral aliases, voyage, xai,
  fireworks, together, scaleway, azure ai, govcloud, azure gov, cloudflare whisper, deprecation dates by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39170
- fix: apply optional_pre_call_checks and reject unsupported router settings on /config/update by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39249
- fix(vector_stores): s3 vectors search router bypass + rag query config drop + ui error swallow by @michelligabriele in
  https://github.com/BerriAI/litellm/pull/34788
- fix(models): key Azure DeepSeek V4 Flash 0731 by its Foundry catalog id by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39341
- fix(deps): raise the tornado and pypdf floors for six new advisories by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39188
- fix(headroom): stop re-compressing retrieved CCR content in client tool loops by @QuantumBreakz in
  https://github.com/BerriAI/litellm/pull/38591
- feat(agentcore-a2a): derive runtime session id from A2A message.contextId by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39371
- fix(proxy): share per-model budget counters across replicas through the spend counter cache by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39375
- fix(proxy-extras): give prisma migrate deploy its own timeout budget by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39365
- fix(proxy): route container create and list through model_list deployments by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39220
- test(build): validate release wheel contracts by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39021
- refactor(rust): extract domain-neutral Python interop by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39026
- refactor(rust): standardize the core Error type by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39331
- fix(ui): preserve full AgentCore runtime ARN in agent edit form by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/39382
- feat(ui): update OpenAI preset model tiers by @tin-berri in https://github.com/BerriAI/litellm/pull/39396
- fix(router): resolve realtime session model to routed deployment by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/36811
- fix(security): restrict and validate file uploads at /v1/files and /upload/logo by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/39379
- feat(auth): enforce configurable password policy and SSO-only login by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/39381
- fix(agents): redact secret litellm_params fields from all /v1/agents responses by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/39389
- fix(otel): stamp Langfuse root observation input and output from the request task by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39369
- fix(guardrails): track and tear down presidio sibling callbacks on delete and update by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39271
- fix(spend): keep every-deployment scope on gateway cache-injection marks by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39241
- fix(proxy/db): keep prisma predicates from raising TypeError under a mocked prisma module by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39253
- fix(proxy): word database 503s by whether the fault is transient by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39256
- refactor(utils): remove the dead get_api_key provider-key resolver by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39260
- feat(mcp): semantic tool search for the native MCP Gateway by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39404
- fix(logging): redact credential query params from the uvicorn access log by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39293
- feat(model_prices): add meta/muse-spark-1.3 and its contributor tier by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39417
- refactor(core): move audio transcription into core by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39126
- fix(proxy): build coordination Redis from REDIS_* env vars unconditionally by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/39410
- test: add interactive Rust Python parity harness by @ishaan-berri in https://github.com/BerriAI/litellm/pull/39419
- test(proxy): verify NO_DOCS/NO_REDOC/NO_OPENAPI restrict every doc surface by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/39378
- test(bedrock): accept the router kwarg in the knowledge base search fake by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39420
- refactor(python-bridge): split routes and add shared function tracing by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39031
- fix(python-bridge): harden sync and async execution boundaries by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39332
- refactor(python-bridge): declare sync and async routes once by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39333
- feat(python): unify Rust opt-in and bridge policy by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39334
- feat(router): add heuristic v2 complexity routing by @tin-berri in https://github.com/BerriAI/litellm/pull/39276
- fix(anthropic): upgrade legacy thinking to adaptive on adaptive-only Claude models for chat, Bedrock Converse, Invoke,
  Vertex AI, and Databricks by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39159
- fix(proxy): mark session/SSO/SAML cookies Secure behind a TLS-terminating reverse proxy by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/39391
- fix(bedrock): honor BEDROCK_MANTLE_API_BASE on bedrock/mantle messages and chat URLs by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39364
- fix(bedrock): strip client_metadata from converse additionalModelRequestFields by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/35967
- chore(techdebt): clear fresh debt from the 2026-08-31 and 2026-09-01 windows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39091
- fix(mcp): cap tools preview and test-connection at the listing timeout and name the unreachable upstream by
  @mateo-berri in https://github.com/BerriAI/litellm/pull/38791
- fix(hosted_vllm): forward truncate_prompt_tokens on rerank requests by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39363
- fix(messages): drop cache_control ttl on non-Anthropic /v1/messages passthrough by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39355
- fix(bedrock_mantle): carry per-request AWS credentials into chat completions SigV4 signing by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39362
- feat(router): add a hybrid classifier that defers near tier boundaries by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39403
- fix: recover the v2 migration resolver from concurrent migrate deploy deadlocks by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39187
- fix(ollama_chat): stamp finish_reason tool_calls when tool calls streamed before the done chunk by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39010
- fix(router): route Claude Code subagents through session router by @moe-berri in
  https://github.com/BerriAI/litellm/pull/39239
- fix(responses): keep namespace tools intact when a guardrail returns them unchanged by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39366
- fix(vector-store): resolve embedding credentials per request by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/38936
- test(e2e/ui): give the seeded users passwords that pass the default password policy by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39442
- fix(http_handler): honor HTTP(S)_PROXY / NO_PROXY when force_ipv4 uses the httpx transport by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39443
- fix(proxy): stop leaking internal exception details to clients by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/39380
- fix(guardrails): forward mode and streaming params to crowdstrike_aidr handler by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39317
- fix(mcp): gate the connect-time OBO pre-flight on the key's allowed servers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39447
- fix(responses): keep provider response headers in streaming logging callbacks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38131
- fix(mcp): fence an outbound-token write against an overlapping invalidation by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/35398
- feat(cli): pre-fill the SSO verification code in the browser when the proxy allows it by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39428
- fix(ui): paginate request logs by session groups server-side by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39257
- feat(proxy): serve the auto-router preset catalog at runtime by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39412
- docs: define Rust Python harness structure by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39456
- fix(guardrails): apply PUT /guardrails/{id} to the serving worker immediately and reject invalid configs with 422 by
  @mateo-berri in https://github.com/BerriAI/litellm/pull/38877
- test(responses): expect the 404 OpenAI now returns for an unknown model by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39457
- fix(guardrails): skip streaming guardrail rounds that re-scan cleared output by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39386
- fix: keep litellm importable on Python 3.10 and guard 3.11-only typing imports in CI by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39448
- fix(proxy): keep SpendLogs and callback session ids in sync when the request has none by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39450
- feat(router): arm safeguard-refusal fallback on generic chains when no content-policy list exists by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39274
- feat(azure): support credential chain for storage by @yucheng-berri in https://github.com/BerriAI/litellm/pull/39229
- chore(crowdstrike): expect the deduped end-of-stream scan in crowdstrike cadence test by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39467
- fix(model_armor): handle Anthropic Messages and Responses streams in post_call by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39181
- test: add OCR python-to-rust test parity ledger (WIP) by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/39434
- feat(complexity_router): opt-in modality override of a kept session-affinity pin by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39454
- feat(datadog_llm_obs): cost tag dimensions, router decision fields, reasoning token metric, redaction gating by
  @yucheng-berri in https://github.com/BerriAI/litellm/pull/39402
- test(rust-python-harness): wire existing e2e SDK tests into the matrix by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/39463
- fix(mcp): never exchange the LiteLLM virtual key as the upstream subject token by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39446
- test: add mistral ocr transformation parity coverage by @ishaan-berri in https://github.com/BerriAI/litellm/pull/39482
- test(vector-store): accept embedding_executor in the Bedrock KB hook fake handler by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39472
- refactor(s3_vectors): embed search queries through the shared vector store executor by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39474
- fix(xai): bill from the cost xAI reports instead of recomputing it (internal copy of #36281) by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39441
- feat(ui): add 1M context auto-router preset by @tin-berri in https://github.com/BerriAI/litellm/pull/39490
- fix(ui): stop the create team form resetting organization and models by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39476
- fix(ui): read the preset catalog at runtime in the dashboard tests by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39478
- fix(sso): resolve multi-valued role claims to the highest privilege role by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39480
- fix(guardrail): hide-secrets playground redaction and guardrail telemetry by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39398
- fix(test): drop the duplicate embedding_executor arg in the Bedrock KB fake handler by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39502
- fix(ui): keep Virtual Keys list state in the URL so it survives leaving the page by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39481
- fix(proxy): 404 a credential delete that matched nothing, and raise instead of return by @eeshsaxena in
  https://github.com/BerriAI/litellm/pull/36260
- fix(proxy-extras): only spend a migrate-deploy attempt when a pass made no progress by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39506
- feat(cli): enable Claude Code gateway model discovery by default in lite claude by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39445
- fix(docker): bump nginx runtime to 1.31.5-alpine3.24 and pin digest by @rakeshrepository in
  https://github.com/BerriAI/litellm/pull/39561
- fix: 1.99.0-rc2 UI bug batch (empty org on key create, session pagination, access group rename/delete) by @mateo-berri
  in https://github.com/BerriAI/litellm/pull/39436
- feat(auto-router): support classifier reasoning effort by @moe-berri in https://github.com/BerriAI/litellm/pull/39372
- fix(ui): replace the key detail URL entry when a virtual key is rotated by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39471
- test(timeout): time out against the local fake endpoint instead of api.openai.com by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39583
- test(harness): add OCR parity with migration strategy runners by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/38765
- fix(databricks): strip thinking_blocks and reasoning_content from outbound messages by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39409
- test(ocr): record provider fixtures in the migration harness by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39425
- feat(ui): keyset-paginate request logs by session trace by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38794
- fix(proxy/db): translate libpq sslrootcert and verify-* into Prisma's strict TLS params by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/39563
- fix(agents): keep the published agent in public_agent_groups by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39554
- fix(mcp): scope allow-all servers to virtual keys by @tin-berri in https://github.com/BerriAI/litellm/pull/39531
- fix(team): generate team IDs for blank input by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39571
- fix(bedrock_mantle): stop dropping the web_search tool on /v1/responses by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/35987
- chore: bump litellm-enterprise 0.1.63 -> 0.1.64, litellm-proxy-extras 0.4.92 -> 0.4.93 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39595
- fix(images): forward gpt-image supported params like background to OpenAI and Azure by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39525
- fix(proxy): return persisted team memberships from /user/new so first CLI login gets the default team by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39545
- fix(spend_tracking): add missing_session_id: omit to leave SpendLogs.session_id null without a client session by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39458
- fix: stop a cleared Organization field from failing key creation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39316
- fix(ui): show MCP servers and agents inherited from access groups on team overview by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39215
- fix(proxy): expose configured mode for auto-router models by @moe-berri in
  https://github.com/BerriAI/litellm/pull/39619
- fix(ui): aggregate session token usage in the logs table by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39598
- fix(cost): apply off_peak_pricing in the dashscope cost calculator by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39592
- test(bedrock): drop EOL cohere.command-r-plus-v1:0 from local_testing by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39608
- fix(openai): default stream usage on PrivateLink and regional api.openai.com hosts by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39614
- fix(proxy): drop anthropic-beta on the Vertex passthrough count-tokens route by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39597
- fix(headroom): resolve CCR retrieval on streaming /v1/responses by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38808
- fix(openai): bridge gpt-5.4+ tool calls to /v1/responses on every api.openai.com host by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39587
- fix(router): pin JWT-authenticated callers by user id in deployment_affinity by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39594
- fix(cost): bill bedrock_mantle web search at $12 per 1k queries using Bedrock's reported count by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39610
- fix(azure_ai): don't reclassify Foundry deployments as azure provider by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38975
- fix(vector_stores): only list vector stores the caller was granted by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39612
- feat(models): add gpt-6-astra pricing and metadata by @mateo-berri in https://github.com/BerriAI/litellm/pull/39622
- chore(ci): promote internal staging to main by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39593
- feat(router): limit heuristic_v2 auto-routers to one without the auto_router license feature by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39468
- fix(ui): clear agents when updating team permissions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39600
- fix(auto_router): bill the routing embedding to the caller's key and team by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39532
- test(router): cover get_configured_mode so router_code_coverage passes by @mubashir1osmani in
  https://github.com/BerriAI/litellm/pull/39630
- fix: treat gpt-6 names as the gpt-5 request family in OpenAI and Azure configs by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39631
- fix(prompts): key the in-memory prompt registry by environment by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38440
- fix(ui): let the Internal Users search box match user_id as well as email by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39604
- test(responses): bound the background stream cancel e2e so an upstream stall skips fast by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39617
- fix(vertex): add the API version to versionless project routes on the Vertex passthrough by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39625
- chore(ci): promote internal staging to main by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39648
- fix(spend_tracking): key /v1/messages spend rows on the msg_ id the client received by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39511
- ci(rust): build and test the ai-gateway server feature by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39493
- ci(ui): run the UI build check through the image's ui-builder stage by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39496
- fix(proxy): parse numeric multipart fields on /v1/images/edits back into numbers by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39510
- fix(guardrails): remove the module-global translation mapping that leaked between tests by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39543
- feat(azure_ai): add grok-4.6 to the model cost map by @mateo-berri in https://github.com/BerriAI/litellm/pull/39426
- fix: attach vector store search_results when a guardrail is registered by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38984
- fix(proxy): stop putting the literal string "None" in error payloads by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39521
- fix(router): keep retry breadcrumbs per request and out of the request snapshot by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39491
- fix(vector-stores): survive a failing vector store search in the chat completions hook by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39495
- fix(utils): redact credential kwargs from the set_verbose request line by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39526
- fix(bedrock): skip the SigV4 credential chain when a bearer token is configured by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39411
- fix(proxy-extras): kill the whole Prisma process group when a command times out by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39466
- fix(rag): forward the managed vector store's params to the search call by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39452
- fix(utils): redact credentials nested in extra_body on the verbose optional-params line by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39538
- fix(containers): pass upstream error status through and forward list pagination params by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39464
- fix(anthropic_messages): key bridged streaming spend rows on the streamed msg_ id by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39541
- fix(helm): render ingress-nginx compatible path types via ingress.controller by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39465
- fix(cache): use sync Redis batch reads by @yucheng-berri in https://github.com/BerriAI/litellm/pull/39358
- fix(guardrails): rebuild the serving worker guardrail on PUT instead of patching it in place by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39243
- test(team-race): wait on pg_locks instead of a fixed sleep by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39611
- fix(agents): hide agents from non-admins who were never granted them by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39636
- fix(team_endpoints): stop partial /team/update from wiping team metadata by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/36328
- test(router): cover configured mode lookup by @moe-berri in https://github.com/BerriAI/litellm/pull/39634
- fix(responses): encrypt the response id on every streamed event by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39534
- fix(mcp): resolve OAuth broker endpoints by server_id with IP access checks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39432
- feat(proxy): enforce team isolation for provider-format batch ids and output files by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/33536
- fix(mcp): strip inbound auth scheme case-insensitively before token exchange by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39346
- fix(mcp): normalize a schemed authentication_token on the v2 and OpenAPI static paths by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39345
- fix(docker): match USE_DDTRACE case-insensitively and route build_from_pip through prod_entrypoint.sh by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39344
- perf(auth): skip object permission DB lookup when no vector stores requested by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39347
- fix(caching): don't trip redis circuit breaker on short timeout bursts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38999
- fix(access_groups): derive attached teams from the team table and reject unknown team ids by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39218
- test(router): drop duplicate get_configured_mode test failing ruff F811 by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39659
- feat(cost): honor off_peak_pricing reasoning and cache-creation rates by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39635
- fix(openai): mint workload identity tokens for PrivateLink and regional api.openai.com hosts by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39652
- feat(ui): find rows by a pasted ID on keys, agents, memory, audit, and request logs by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39661
- test(proxy-extras): fake run_prisma instead of subprocess.run in the migrate deploy harness by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39669
- fix(scim): default-team fallback on create and keep memberships when PUT /Users has no groups by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39623
- fix(router): count tools and Anthropic system prompt in context-window pre-call check by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39663
- test(proxy-extras): repoint the migrate-deploy harness at the run_prisma seam by @mubashir1osmani in
  https://github.com/BerriAI/litellm/pull/39673
- perf(spend): group /spend/logs summary by day in Postgres instead of per-row Prisma group_by by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39351
- fix(proxy): apply default_vertex_config location before building the Vertex passthrough base URL by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39662
- fix(anthropic_endpoints): return Anthropic type:error envelope for /v1/messages errors by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39037
- feat(ui): configure auto-router session affinity TTL by @tin-berri in https://github.com/BerriAI/litellm/pull/39679
- perf(mcp): cache SSO identity assertion reads on the ID-JAG path by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39348
- test(e2e): match the Internal Users search placeholder shipped by #39604 by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39678
- fix(ui): scroll admin table rows inside the table instead of the page by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39684
- fix(router): evict stale global pattern_router entries on upsert/delete by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39664
- fix(caching): keep a node timeout from forcing a cluster-wide topology reinit on redis-py 8.x by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39349
- fix(logging): blocked requests no longer report guardrail_status=success in multi-guardrail configs by @yucheng-berri
  in https://github.com/BerriAI/litellm/pull/39596
- fix(snowflake): normalize Cortex Claude request shapes by @tin-berri in https://github.com/BerriAI/litellm/pull/39453
- feat(proxy): per-worker admission control that rejects excess requests with 503 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39352
- fix(proxy): emit SSE keepalives on queue, rag, azure passthrough, usage chat and policy enrich streams by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39273
- fix(azure): restrict the storage credential chain to deployment identities by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39637
- fix(model_checks): drop wildcard routes like bedrock/* from /v1/models by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/31731
- fix(mcp): pre-flight the ID-JAG credential at the transport edge by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/35392
- feat(caching): add semantic_cache_scope to isolate semantic cache hits per end user by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39590
- feat(ui): add one-click Auto Router setup by @moe-berri in https://github.com/BerriAI/litellm/pull/39693
- fix(ci): pin setup-uv to v10.0.1 by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39111
- refactor(tests): restructure rust python harness around strategy definitions by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39628
- test(ocr): complete Rust unit test parity by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39689
- feat: page the public model hub table off /public/v1/model_hub, keeping every filter by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39691
- refactor(rust): extract config crate by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39706
- feat(python): rename Rust rollout API by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/39704
- fix: restore Python compatibility and test 3.10 through 3.14 by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/39399
- fix(spend-tracking): keep batch spend keys joinable after v1.99 provenance gate by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39568
- test: repair four chronically failing CI tests by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39770
- feat(team): report per-user spend within a team for JWT traffic by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39771
- feat(router): add classifier circuit breaker by @moe-berri in https://github.com/BerriAI/litellm/pull/39701
- ci: report every failing test in a job instead of stopping at the first by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39772
- test(caching): drive the redis stall burst off the clock, not asyncio.wait_for by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39773
- fix(ui): clamp server-paginated DataTable page index when rowCount shrinks by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39776
- feat(mcp): use x-mcp-<access_group>-* headers as default upstream credentials for group members by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39717
- fix(ui): paginate per-user usage with the shared server-side DataTable footer by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39682
- fix(proxy): log mid-stream /v1/messages failures as failures with partial usage by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39589
- fix(cost): honor off_peak_pricing in the fireworks_ai and perplexity cost calculators by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39632
- fix(organization): clear org budget limits when PATCH /organization/update sends null by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39670
- fix(organization): reject negative limits and unparseable budget_duration on PATCH /v2/organization by
  @ryan-crabbe-berri in https://github.com/BerriAI/litellm/pull/39793
- feat(organization): expose PATCH /v2/organization/{organization_id} in the OpenAPI schema by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39794
- fix(auto-router): route 1M complex tier to GPT Sol by @tin-berri in https://github.com/BerriAI/litellm/pull/39797
- fix(bedrock_mantle): anchor MANTLE_HOST_RE so custom Mantle hosts are honored by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39361
- fix(health): probe test_connection with the credential the request names by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39801
- fix(router): bound auto-router classifier latency by @moe-berri in https://github.com/BerriAI/litellm/pull/39696
- fix(ui): accept any routing group name the backend accepts by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39807
- fix(model_prices): verified registry audit, Databricks Sep-2026 catalog, realtime image pricing, deprecation dates by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39388
- fix(jwt): invalidate JWT key mapping cache on /key/regenerate by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39808
- fix(complexity_router): fall back to a live peer when the decided tier model is fully cooled down by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39675
- feat(guardrails): roll up Bedrock guardrail cost per usage counter by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39196
- fix(auto_router): derive tier definitions in prompt editor by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39688
- fix(proxy): recognize opencode's bare x-session-id header for session affinity by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39802
- feat(cli): sync OpenCode models from /v1/models in lite opencode by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39789
- fix(spend-tracking): keep internal service-account key names readable in spend logs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39572
- fix(anthropic): never carry cache_control on translated thinking blocks by @moe-berri in
  https://github.com/BerriAI/litellm/pull/39815
- fix(responses/mcp): keep follow-up calls stateless when store=false by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/36575
- fix(router): resolve retry_policy by exception hierarchy, add ServiceUnavailableErrorRetries and DefaultRetries by
  @shivamrawat1 in https://github.com/BerriAI/litellm/pull/35853
- fix(headroom): bound the /v1/compress and /v1/retrieve calls with a timeout by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39527
- feat(vector_stores): add a MongoDB vector store provider for Atlas and self-managed deployments by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39811
- fix(fireworks_ai): resolve tool_choice and reasoning support for short model names by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39763
- fix(datadog_llm_obs): keep the guardrail audit record under message redaction by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39702
- fix(proxy): invalidate end-user spend counter and cache on budget reset (#39726) by @amasen02 in
  https://github.com/BerriAI/litellm/pull/39729
- fix(proxy): strip every TypedDict qualifier before numeric form-field detection by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39780
- fix(bedrock): stop sending toolConfig tool definitions to guardrails on passthrough converse by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39281
- feat(shadow_eval): judge tool-call turns instead of dropping or erroring on them by @moe-berri in
  https://github.com/BerriAI/litellm/pull/39818
- feat(router): auto-escalate stalled complexity-router tasks by @moe-berri in
  https://github.com/BerriAI/litellm/pull/39809
- fix(team_endpoints): let member_delete clear a team left on the user row by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38703
- feat(cost-map): add azure/gpt-6-astra and azure/us/gpt-6-astra Foundry pricing by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39827
- feat(complexity_router): let the LLM classifier see request images by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39825
- feat(access-groups): resolve resource names on access group responses by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39822
- fix(datadog_llm_obs): keep guardrail_cost_by_unit on redacted spans by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39848
- test(store_model_in_db): assert the 400 contract in the unknown-model spend log test by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39842
- feat(cli): add `lite debug claude` session report and /debug-lite slash command by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39435
- test: deflake JWT tamper, fuzzy picker, tag routing, liveliness, redis stall burst, and pre-commit interrupt tests by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39306
- feat(otel): stamp litellm.request.route on the LLM call span by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39698
- feat(shadow_eval): scope a job to model groups, ANDed with its key, team, and user targets by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39828
- test(e2e/batches): assert Bedrock batch cancel and list in the lifecycle by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39847
- refactor: clear fresh tech debt from the last 24 hours (2026-09-03, 2026-09-04) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39518
- refactor(typing): cut 1,397 Any errors across 183 backend files by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39461
- fix(responses): decode JSON-string tool schemas before sending to the provider by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39844
- feat(helm): render nodeSelector, tolerations, and affinity on the componentized chart migrations Job by @mateo-berri
  in https://github.com/BerriAI/litellm/pull/39843
- fix(mcp): let config.yaml MCP servers pin server_id by @yucheng-berri in https://github.com/BerriAI/litellm/pull/39286
- feat(dashboard): configure classifier vision input by @tin-berri in https://github.com/BerriAI/litellm/pull/39840
- fix(batches): register ownership for every batch create path by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39810
- fix(proxy): gate the OpenAI websocket passthrough behind an explicit opt-in by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39841
- fix(ui): bring the inline-object lint budget back under its ceiling by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39856
- fix(realtime): relay the upstream websocket close to the client instead of hanging by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39851
- feat(router): meter auto-router tier and prompt customization against the auto_router license feature by @tin-berri in
  https://github.com/BerriAI/litellm/pull/39674
- fix(shadow_eval): size the judge output cap for a judge that reasons by @moe-berri in
  https://github.com/BerriAI/litellm/pull/39817
- feat(organization): expose PATCH /v2/organization/{organization_id} in the OpenAPI spec by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/39672
- fix(ui): make Admin UI table pagination honor the selected page size by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39680
- chore: bump litellm-enterprise 0.1.64 -> 0.1.65, litellm-proxy-extras 0.4.93 -> 0.4.94 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39912
- test(e2e): repair the wildcard readiness probe and the semantic auto-router spend assertion by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39804
- fix(guardrails): record guardrail information for undecorated custom apply_guardrail overrides by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39727
- feat(responses): honor supported_endpoints /v1/responses opt-in for OpenAI-compatible deployments by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39725
- fix(router): hold max_parallel_requests slot until streaming response is exhausted or closed by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39859
- fix(proxy): retry deadlocks and requeue spend logs on any DB write error by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39883
- fix(mcp): reject URL credentials for none auth by @tin-berri in https://github.com/BerriAI/litellm/pull/39926
- fix(hide-secrets): stop redacting benign identifiers by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39879
- perf(logging): scan large base64 payloads for log truncation off the event loop by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39890
- fix(proxy): make the invalid-model 403 path cheap under a burst of rejections by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39892
- test(e2e): cover Anthropic /chat/completions streaming and tool calls by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39916
- fix(router): coordinate async and sync failure handlers at remaining router call sites by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/39887
- fix(cloudzero): infer daily batch schema from every row by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39871
- fix(cloudzero): preserve late resource tags by @yucheng-berri in https://github.com/BerriAI/litellm/pull/39873
- feat(ui): deep link guardrail detail with ?guardrail= on guardrails pages by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39930
- test: repair two CI tests broken by intentional changes by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39932
- feat(terraform/gcp): dependencies-only mode and bring-your-own-network for GKE by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39695
- test(e2e): cover Anthropic and OpenAI prompt caching, Cohere embeddings, and costed /openai chat passthrough by
  @yuneng-berri in https://github.com/BerriAI/litellm/pull/39920
- test(e2e): cover key spend reset, regenerate grace period, and the llm_api_routes grant by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39917
- test(e2e/ui): select 50 rows per page before asserting the Tags and Model Hub tables overflow by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39934
- feat(auto-router): decouple compression between the routing decision and the model call by @moe-berri in
  https://github.com/BerriAI/litellm/pull/39823
- feat(mcp): renew the stored SSO identity assertion behind ID-JAG by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/35401
- feat(mcp): warn when an oauth2_id_jag server outruns the SSO provider's assertion capture by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/35394
- perf: lazy-load SDK symbols so import litellm stays under 60 MB RSS by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39121
- test(e2e): cover presidio post_call, tool_permission, and weave logging cells by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39279
- fix(ci): grant pull_requests write for release wheel reporter by @cursor[bot] in
  https://github.com/BerriAI/litellm/pull/39922
- feat(guardrails): add non-blocking flag() verdict to custom code guardrails by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39728
- feat(proxy): serve Prometheus /metrics from a separate process via --prometheus_metrics_port by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39889
- fix(mcp): scan and mask MCP tool call arguments in unified guardrails by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/35142
- fix(proxy): reject ambiguous name or alias keys in mcp_tool_permissions on write by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39947
- test(e2e): stream a longer /v1/messages reply so the delta-count pin has margin by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39946
- feat(ui): show guardrail usage units and cost on the Guardrails Monitor by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39853
- fix(ui): show indirectly granted and name-keyed MCP servers in the tool matrix by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/35154
- test(e2e): prove Vertex context caching on the first cold call and on the spend row by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39938
- feat(ocr): add Cohere Parse support for cohere and azure_ai by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39862
- fix(proxy): keep guardrail cost in spend on cache hits by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39960
- test(e2e): judge /v1/messages streaming on the clock, not on the provider's delta count by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39953
- fix(ui): remove unreachable AI Hub dialog that put the session key in a URL by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39968
- fix(ui): read Usage Total Requests tile from gateway request counts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39963
- revert: perf: lazy-load SDK symbols so import litellm stays under 60 MB RSS (#39121) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39969
- chore: rebuild Admin UI bundle for the next release by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39959
- chore(ci): promote internal staging to main by @yuneng-berri in https://github.com/BerriAI/litellm/pull/39849
- fix(docker): ship pymongo in the proxy images for the MongoDB vector store by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/39994
- feat: backport MongoDB sidecar to rc/1.101.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/40316
- feat(otel): backport tenant trace destinations to rc/1.101.0 (#39654) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/40321
- chore(ui): backport dashboard dependencies to rc/1.101.0 (#40312) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/40324
- feat(team): backport team admin callbacks to rc/1.101.0 (#37667) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/40325
- fix(otel): backport auth spans and callback merge to rc/1.101.0 (#40335) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/40346
- fix(redis): backport Redis chaos fixes and load gate to rc/1.101.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/40886

## New Contributors

- @cat0825 made their first contribution in https://github.com/BerriAI/litellm/pull/34696
- @samtsai15 made their first contribution in https://github.com/BerriAI/litellm/pull/38940
- @yatishgoel made their first contribution in https://github.com/BerriAI/litellm/pull/38479
- @koladefaj made their first contribution in https://github.com/BerriAI/litellm/pull/30644
- @georgeatparallel made their first contribution in https://github.com/BerriAI/litellm/pull/38113
- @Timik232 made their first contribution in https://github.com/BerriAI/litellm/pull/38106
- @seanyasno-af made their first contribution in https://github.com/BerriAI/litellm/pull/38898
- @jliounis made their first contribution in https://github.com/BerriAI/litellm/pull/37883
- @QuantumBreakz made their first contribution in https://github.com/BerriAI/litellm/pull/38591
- @eeshsaxena made their first contribution in https://github.com/BerriAI/litellm/pull/36260
- @rakeshrepository made their first contribution in https://github.com/BerriAI/litellm/pull/39561
- @amasen02 made their first contribution in https://github.com/BerriAI/litellm/pull/39729

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.100.0...v1.101.0
