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
  ghcr.io/berriai/litellm:v1.106.0
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.106.0/cosign.pub \
  ghcr.io/berriai/litellm:v1.106.0
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

## What's Changed

- test(mcp): fire MCP client test deadlines on conditions instead of wall-clock time by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44166
- fix(cost-map): add OpenAI TTS and GPT-5.x deprecation dates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44175
- fix(tracing): unify ClickHouse storage configuration by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/43941
- feat(docker): one-command quickstart that starts the gateway, Postgres, and the admin UI by @misbahsy in
  https://github.com/BerriAI/litellm/pull/43673
- fix(lens): simplify the example investigation preview by @moe-berri in https://github.com/BerriAI/litellm/pull/44123
- chore(helm): drop migrationJob values the chart never reads by @Bernedotcom2312 in
  https://github.com/BerriAI/litellm/pull/42141
- fix(ui): register tencent in the Add Model provider dropdown by @jimaldon in
  https://github.com/BerriAI/litellm/pull/40924
- test: remove 130 legacy tests owned by stronger unit proofs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44157
- feat(mcp)!: disable stdio MCP servers by default by @yuneng-berri in https://github.com/BerriAI/litellm/pull/44066
- fix(proxy): exit when DATABASE_URL is set but the Prisma toolchain is missing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44207
- fix(proxy): preserve lifespan state across all entrypoints by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44214
- fix(oci): resolve the GenAI endpoint realm from the compartment OCID instead of hardcoding oraclecloud.com by
  @fede-kamel in https://github.com/BerriAI/litellm/pull/43180
- fix(chatgpt): preserve requested service tier in Responses calls by @SteffanWolter in
  https://github.com/BerriAI/litellm/pull/40108
- fix(ui): leave unset callback select params out of the save payload by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44213
- fix(proxy-extras): hand libpq a root cert, not Prisma's sslcert, when the migration job builds indexes by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44203
- feat: add Laya gateway and OSS classifier providers by @tin-berri in https://github.com/BerriAI/litellm/pull/43626
- fix(auto-router): count usage savings by selected UTC request day by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44115
- fix(lens): preserve framework agent names and GenAI message content by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44218
- feat(jwt): auto_register_map_existing_key maps JWT to the user's existing virtual key by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42375
- feat(ui): select Laya for OSS classification by @tin-berri in https://github.com/BerriAI/litellm/pull/43768
- fix(otel): tolerate non-dict callback_settings.otel and ignore bare EXCLUDED_SERVICES env by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44086
- fix(proxy): carry key, team and project tags into pass-through spend logs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42662
- feat(ui): add System One (Jev) tab to the playground by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44043
- chore: bump litellm-proxy-extras 0.4.104 -> 0.4.105 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44234
- chore(prices): add xAI grok-voice-transcribe-1.0 deprecation date by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44237
- fix(exa): fall back to highlights/summary when text is missing by @wakqasahmed in
  https://github.com/BerriAI/litellm/pull/42213
- fix(scim): apply path-less group PATCH ops instead of storing them under an empty metadata key by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43978
- fix(lens): run investigations with configured wildcard models by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44233
- fix(ui): shrink the sidebar logo so it stops outweighing page titles by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44247
- feat(tracing): support claude agent sdk traces with agent name, logo and chat content by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44248
- fix(ui): make model leaderboard chart bars wide and readable by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44249
- test: repair stale and polluting tests red on scheduled main CI by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44229
- feat(traces): type queries and align read access with log visibility by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/44228
- chore(ui): untrack tsconfig.tsbuildinfo and gitignore *.tsbuildinfo by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44261
- refactor(mcp): extract upstream preparation and support modern clients by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/44232
- fix(lens): default to traces and reopen span details by @moe-berri in https://github.com/BerriAI/litellm/pull/44260
- fix(bedrock): surface unrecognized converse-stream event frames instead of an empty turn by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/44112
- perf(proxy): batch daily model usage writes instead of upserting per request by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44243
- test(integration): opt the config pass-through spend-log case into auth by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44265
- test: fix three order-dependent and timing-flaky tests by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44271
- fix(ui): make the Lens traces refresh button always clickable by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44252
- feat(lens): add sample previews and improve setup and worker feedback by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44268
- chore(openrouter): sync prices, limits and deprecation dates from the models API by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44287
- refactor(traces): type the ClickHouse query help response by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44285
- fix(proxy): stop queued registry read-throughs spending the resync budget by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44277
- feat(lens): show investigation progress as one staged bar with time left by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44301
- refactor(ui): compose dashboard pages with shared layouts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44306
- fix(proxy): share ownership permissions for spend logs and traces by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/44239
- fix(proxy-extras): retry P3009 when a peer already recovered the named migration row by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44283
- fix(bedrock): price amazon nova 2 pro preview at the standard tier by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44302
- feat: add Bespoke Nimble gateway and OSS classifier support by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44246
- fix(anthropic): stop repeating streamed thinking text in the signature chunk by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44127
- fix(responses): drop bridge-minted reasoning items from OpenAI replays by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44132
- feat(bedrock): drop lookaround regex patterns from tool schemas for Converse models that reject them by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44138
- feat(bedrock): serve gpt-5.6+ chat completions natively by default, with chat_completions/ opt-in for gpt-oss and grok
  by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44307
- feat(lens): issue briefs with problem, user goal, outcome and test cases by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44311
- fix(responses): keep gpt-5.4/5.5 tool calls on chat and merge bridged tool calls into one choice by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44295
- fix(cost): price rule-only model names at the deployment's rate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44144
- fix(auto-router): attribute router-day savings without spend logs or a session by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44226
- test(integration): let run.py select cells by pytest node id by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44319
- fix(bedrock): honor unsupported reasoning effort levels for OpenAI GPT models by @Aasif-Multani in
  https://github.com/BerriAI/litellm/pull/44183
- feat(lens): add preset watch-for checks to investigation setup by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44313
- fix(proxy): use OpenAI workload identity federation tokens on /openai_passthrough by @6matt in
  https://github.com/BerriAI/litellm/pull/44140
- feat(interactions): durable cross-pod settlement for background interaction billing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41955
- fix(streaming): keep the finish_reason of the provider's last content chunk in the logged response by @joeym82956 in
  https://github.com/BerriAI/litellm/pull/44318
- fix(bedrock): send the anthropic-workspace-id header to Bedrock Mantle by @kohjunhao in
  https://github.com/BerriAI/litellm/pull/44173
- fix(guardrails): run unified guardrails on /v1/images/edits by @michelligabriele in
  https://github.com/BerriAI/litellm/pull/44195
- feat(scaleway): add rerank support by @ankit373 in https://github.com/BerriAI/litellm/pull/44160
- fix(vector_stores): return managed file ids from vector store file list by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43800
- fix(proxy): return 4xx instead of 500 for missing required params, invalid pagination and unknown ids by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43787
- fix(guardrails): encrypt guardrail litellm_params secrets at rest by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/43627
- fix(search_tools): encrypt search tool litellm_params at rest by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/43631
- feat(roi): add GitLab sources and branch cost attribution by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44324
- fix(model-prices): mark azure us/eu responses-only models as mode responses by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44323
- revert(cost): revert "fix(cost): price rule-only model names at the deployment's rate" (#44144) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44335
- fix(proxy): stamp the client alias on a copy of each streamed chunk so pricing sees the deployment model by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44341
- revert(responses): revert "fix(responses): keep gpt-5.4/5.5 tool calls on chat and merge bridged tool calls into one
  choice" (#44295) by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44344
- refactor(dashboard): migrate to zod 4 and openai 6 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44345
- feat(ui): move LiteAdmin into the header with a docked side panel by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44293
- fix(responses): merge bridged tool calls into the same choice as the text by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44346
- feat(ui): improve trace inspection and ROI estimation by @moe-berri in https://github.com/BerriAI/litellm/pull/44351
- refactor(ui): reorganize Lens dashboard components by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44354
- refactor(ui): inject Lens backends as services instead of a fake HTTP client by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44369
- refactor: clean up fresh tech debt from 2026-10-02 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44362
- feat(traces): tracing development seed by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44363
- refactor(types): replace Any with proven types in 4 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44370
- build(deps): suppress unfixed braces GHSA-vfj7-8cjw-p6xm to clear osv-scan by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44347
- fix(azure): add MAI-Image max_input_tokens from models sold directly page by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/44375
- fix(proxy): emit postgres service spans only on real DB reads in auth cache helpers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44148
- fix(otel): nest cache spans under their operation and name service spans by purpose by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44150
- fix(otel): name postgres service spans by operation and table by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44240
- perf(proxy): stop prompt-cache eligibility from tokenizing the whole conversation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44221
- fix(proxy): keep the database error when the log_db_metrics failure hook raises by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44383
- feat(azure): add azure_ai/kimi-k2-thinking from Azure Kimi pricing page by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44382
- feat(harness): add Harness.TOOL_LOOP, a minimal in-process tool-calling loop by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44391
- feat(decisions): add unified /v1/decisions endpoint for Jev-compatible providers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44236
- fix(lens): paginate trace reads within ClickHouse limits by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44384
- feat(lens): live dot field timeline and full-screen traces view by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44390
- feat(ui): make LiteAdmin enterprise-only by @tin-berri in https://github.com/BerriAI/litellm/pull/44399
- fix(bedrock): stop emitting Converse cachePoint blocks for Kimi K3 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44292
- test(cost): pin OpenAI reported web search count with mixed actions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44414
- fix(ci): give the pass-through auth regression test a real FastAPI app by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44403
- fix(azure): add azure_ai/flux.2-pro input token limit from the models sold directly page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44405
- fix(lens): batch run reads and reset trace pagination by @moe-berri in https://github.com/BerriAI/litellm/pull/44398
- fix(lens): preserve full trace access and expose investigation failures by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44406
- feat: add make lens-dev for one-command lens local dev by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44413
- fix(bedrock): honor the per-request timeout on Converse and Invoke streaming (internal copy of #38210) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44134
- feat(traces): render curated SQL examples from shared files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44388
- fix(model_prices): registry audit 2026-10-03, add cohere embed v5, grok-imagine-video-1.5-lite and openrouter
  gpt-image rows by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44376
- refactor(traces): extract snapshot cache by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44424
- feat(lens): always-on investigations with findings and investigations tables by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44418
- feat(docker): add a Windows quickstart in PowerShell, and a styled terminal for both quickstarts by @misbahsy in
  https://github.com/BerriAI/litellm/pull/44310
- feat(proxy): serve a Codex-native model catalog with per-model service_tiers from /v1/models by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44136
- refactor(types): replace Any with proven types in 9 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44389
- fix(proxy): treat Postgres connection exhaustion as DB unavailable, not poison spend-log rows by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44270
- fix(proxy): treat Postgres connection exhaustion as backpressure, not poison rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44266
- fix(lens): release budget reservations when the analysis model call fails by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44431
- fix(mcp): preserve upstream tool schemas and parameter headers by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/44425
- fix(bedrock_mantle): route Claude chat completions to the native Messages endpoint by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43646
- fix(tracing): preserve spend identity and gateway correlation by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/44421
- feat(roi): measure shipping velocity, quality, and recorded spend by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44426
- fix(azure): set text-embedding max input to 8192 from the models sold directly page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44449
- feat(ui): show invitation and reset password links in a copyable field by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44454
- feat(lens): coordinate worker releases and bundled installs by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44428
- fix(auth): resolve hidden model_group_alias entries in the zero-cost budget check by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43741
- fix(vertex_ai): forward system and tools to partner model count_tokens by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43900
- fix(traces): reject conflicting spend aliases and unrelated HTTP siblings by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44456
- chore(cost-map): add azure_ai/kimi-k2-thinking retirement date from the Azure retired models page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44455
- fix(health): probe Bedrock Mantle Claude deployments over the Anthropic Messages API by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44419
- fix(tests): match the OS bind error in the owned-proxy port-race retry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44462
- feat(anthropic): workload identity federation and pluggable identity sources by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44448
- test(integration): exact four-part translation cases on a shared fake provider and shared YAML deployment by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44451
- feat(roi): default people and branch lists to matched accounts by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44465
- feat(enterprise): bundle LiteAdmin Slack with native gateway login by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44444
- fix(caching): count tool_call cache_control marks in the injection census by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43556
- chore(cost-map): sync openrouter prices from the models API by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44466
- fix(lens): preserve approved worker digests and harden its image by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44467
- feat: improve Lens dev seeding and live UI by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44468
- test(ui): wait for step search value to settle in TraceDrawer test by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44470
- feat(ui): share trace drawer as a closable SidePanel and polish Lens by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44473
- fix(lens): align source setup with available worker images by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44476
- feat(sdk): add run_tool_loop and arun_tool_loop helpers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44381
- feat(lens): guide setup through the first investigation by @moe-berri in https://github.com/BerriAI/litellm/pull/44475
- test(ci): fix six CircleCI test regressions on main by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44429
- fix(proxy-extras): log v1 migration failures at ERROR so LITELLM_LOG=ERROR shows them by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44202
- feat(ui): inline Lens settings tab and investigation editor by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44479
- feat(mcp): hand listed-tool description and input schema to pre-call hooks per caller by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41162
- refactor: clean up fresh tech debt from 2026-10-03 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44484
- fix(otel): read the registered v2 logger without importing the proxy by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44485
- test(mcp): keep the SSO assertion round trip from matching its refresh token inside random ciphertext by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44494
- test(ci): pin the ROI estimator flag and the prompt-cache counter in two drifted tests by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/44499
- refactor(ui): move TraceView into components/lens/traces by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44501
- refactor(ui): rename view_logs to logs and split request, audit and detail by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44505
- refactor(ui): share CopyButton between Lens traces and logs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44513
- refactor(lens): storage-independent trace reads, shared keyset pager, typed read failures by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44422
- fix(ci): send the Lens preview body as selection in the tracing endpoint tests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44525
- fix(azure): set gpt-realtime-2.1 retirement dates from the retirement schedule by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44526
- fix(ci): repair the security sweep and Lens billing integration tests for ROI, JWKS, and release identity changes by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44529
- fix(dashboard): route dev API calls on Accept and fail fast on non-JSON 2xx by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44528
- chore(cost-map): sync openrouter prices from the models API by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44533
- refactor(ui): route dashboard URL state through nuqs parsers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44537
- fix(logging): deduplicate streaming failure callbacks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44442
- feat(proxy): add LITELLM_FIPS_MODE startup gate with provider assertion and loud password migration failure by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42700
- fix(guardrails): run the end-of-stream post_call scan when the client disconnects mid-stream by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43839
- refactor(mcp): fix Sequence/list return mismatch and collapse record_listed_tools wrapper by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44556
- chore(cost-map): add azure retirement dates for gpt-4o-realtime-preview-2024-10-01 and jamba-instruct by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44567
- feat(ui): add persistent columns and loading skeletons to Lens runs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44579
- fix(ui): remove Top models by task card from Model Leaderboard by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44502
- refactor(rust): track ClickHouse migrations in a checksummed ledger by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44580
- refactor(ui): extract shared timeline and time-range controls by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44584
- fix(azure): set gpt-4o-transcribe retirement date from the retirement schedule by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44585
- ci: move Postgres, MCP and Redis suites to CircleCI integration by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44453
- chore!: retire the integrated ROI calculator by @moe-berri in https://github.com/BerriAI/litellm/pull/44477
- fix(caching): key response cache by router model group in litellm_metadata by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44542
- fix(auto-router): align preview and serving default resolution by @moyai-berriai[bot] in
  https://github.com/BerriAI/litellm/pull/44436
- fix(mcp): bind OAuth clients to their upstream issuer by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/37777
- feat(guardrails): add llm shield pii redaction and rehydration guardrail by @ninadphalak in
  https://github.com/BerriAI/litellm/pull/42645
- refactor(tracing): generate existing HTTP request models from Rust schemas by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44591
- ci: run unit selections from GHA test-path and drop the CircleCI unit jobs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44461
- fix(ui): make mobile sidebar and top bar responsive by @moe-berri in https://github.com/BerriAI/litellm/pull/44603
- refactor(types): replace Any with proven types in 137 files by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/44478
- fix(ui): restore inline Lens onboarding and responsive layout by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44604
- test(integration): anthropic-route basic translation cases for six Claude models on messages, chat completions and
  responses by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44607
- fix(responses): report truncated bridged output as incomplete and echo request params by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44460
- fix(proxy): enforce internal-user model creation prohibition by @moyai-berriai[bot] in
  https://github.com/BerriAI/litellm/pull/44438
- chore(harness): drop the unused Any import left in harness options by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44625
- fix(harness): drop the unused Any import that fails ruff on main by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44627
- refactor(proxy): rename management/teams/access.py to authz.py by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44624
- feat(tracing)!: return only data from SQL queries by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44609
- fix(openai/realtime): drop model from upstream URL for intent=transcription by @michelligabriele in
  https://github.com/BerriAI/litellm/pull/43854
- fix(gemini): add priority tier audio input price to three Gemini rows by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44632
- fix(cost): bill per-second transcription models outside chat modes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44458
- fix(ui): explain why team member reset spend is unavailable instead of hiding it by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44629
- test(integration): bedrock_converse-route basic translation cases for six Claude models on messages, chat completions
  and responses by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44646
- test(integration): run the anthropic /v1/responses basic translation cases now that the bridge echoes request params
  by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44615
- feat(lens): restore compact navigation with live investigation review by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44472
- feat(proxy): limit which models an end user can call by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43904
- fix(sso): let CLI and Claude Code gateway sign-in through on DISABLE_ADMIN_UI nodes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44620
- feat(ui): declare shared search operators and flush queries on blur by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44665
- fix(lens): make tool steps and conversations readable by @moe-berri in https://github.com/BerriAI/litellm/pull/44645
- fix(ui): send null instead of $0 when a team's member default budget is cleared by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44644
- test(integration): azure_ai-route basic translation cases for six Claude models on messages, chat completions and
  responses by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44658
- test(integration): basic translation cases for the openai_responses route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44663
- feat(lens): analyze trace workspaces with confined Python and compaction by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44640
- fix(vertex-ai): add deprecation_date to gemini-3.1-flash-lite-image by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44639
- fix(bedrock): add priority and flex prices for Grok 4.3, 4.6, 4.7 and Kimi K3 by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44670
- test(integration): pin the Claude-tokenizer recount for streamed claude-sonnet-5 no-usage cases by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44643
- feat(proxy): embed enterprise LiteAdmin MCP in LiteLLM images by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44610
- test(integration): basic translation cases for the azure route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44672
- test(integration): assert the Messages API health probe on Mantle Claude by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44612
- refactor(rust): rename litellm-framing crate to litellm-framer by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44683
- test(integration): basic translation cases for the gemini route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44662
- test(integration): basic translation cases for the openai route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44667
- refactor(rust): derive string enum serde through strum and serde_with by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44675
- fix(spend-tracking): stop caching failed spend-log metadata lookups as confirmed misses by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43560
- fix(proxy): let a listed team alias win over a same-named key alias in the customer model check by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44677
- chore: move PR template to PULL_REQUEST_TEMPLATE/general.md, add rust.md by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44693
- fix(router): retry a /v1/messages stream the provider drops before the first content chunk by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44276
- fix(lens): persist final coverage with source diagnostics by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44682
- test(integration): point the scratch upgraded proxy's read replica at the scratch database by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44613
- fix(lens): show investigation findings for agent traces by @moe-berri in https://github.com/BerriAI/litellm/pull/44696
- fix(build): rebuild the Rust bridge when uv sync sees Rust sources change by @nate-berri in
  https://github.com/BerriAI/litellm/pull/44708
- fix(lens): preserve span timestamps in investigation evidence by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44702
- ci: split slow unit shards and build the Rust bridge once per run by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44622
- test(rust_bridge): expect PartRow start_time and end_time as required LENS_CONTENT fields by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44719
- chore(deps): bump langgraph-sdk from 0.4.2 to 0.4.4 by @dependabot[bot] in
  https://github.com/BerriAI/litellm/pull/44713
- feat: add Reka as an OpenAI-compatible provider by @anniejeng in https://github.com/BerriAI/litellm/pull/44278
- feat(ui): support native decisions endpoint in decision playground by @moyai-berriai[bot] in
  https://github.com/BerriAI/litellm/pull/44664
- fix(lens): reconstruct native coding agent conversations by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44711
- fix(responses): honor request cache controls on chat completions bridged to the Responses API by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44676
- fix(deps): bump source-map-js, smol-toml, mako, multidict and werkzeug for OSV advisories by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44728
- test(integration): rename translation runner run to assert_translation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44741
- feat(lens): show investigation names in findings table by @moe-berri in https://github.com/BerriAI/litellm/pull/44753
- feat(ui): configure cache-aware auto routing by @tin-berri in https://github.com/BerriAI/litellm/pull/43396
- fix(lens): bound result recovery and preserve partial results by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44692
- feat(prometheus): cap series per metric for every labeled metric by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44420
- feat(lens): type to filter the traces agent dropdown by @ishaan-berri in https://github.com/BerriAI/litellm/pull/44745
- test(lens): use current worker protocol in billing integration by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44760
- feat(model_prices): add chatgpt subscription rows for the gpt-6 family by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44758
- test(e2e): assert the sibling-replica cooldown through the router by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44706
- test(integration): basic translation cases for the bedrock_invoke route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44752
- fix(gemini): stop replaying thinking block signatures to Gemini by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44661
- fix(ci): namespace claude session ids in tracing seeds and allowlist /v1/logs on backend by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/44761
- fix(proxy): judge the free-model budget waiver by the group an alias routes to by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44638
- test(integration): basic translation cases for the vertex_ai route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44751
- fix(vertex_ai): apply regional endpoint uplift on image generation cost path by @nate-berri in
  https://github.com/BerriAI/litellm/pull/44679
- refactor(tests): extract Rust cache test split from #44714 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44780
- feat(proxy): cap batch file records, daily batch uploads, and per-file downloads by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43632
- feat(lens): add copy link button to trace header by @ishaan-berri in https://github.com/BerriAI/litellm/pull/44749
- test(integration): keep scripted upstream connections open past the proxy's keepalive by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44695
- test(integration): basic translation cases for the bedrock_mantle route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44750
- fix(chatgpt,github_copilot): refuse device-code login inside an event loop or worker thread by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/39585
- feat(bedrock): add glm 5.3 cross-region rows and nova 2.5 sonic by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44710
- fix(responses): honor caller stream flag when provider forces SSE (internal copy of #34095) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41235
- refactor(cache): remove dead Cache._native_cache runtime path by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44785
- fix(vertex_ai): add regional endpoint uplift to gemini-3.1-flash-image by @nate-berri in
  https://github.com/BerriAI/litellm/pull/44673
- feat(ui): lead the Lens investigation detail with a run report by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44786
- fix(ui): polish Lens runs loading, reload, and time range menu by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44789
- refactor(types): move SpanAttributes, SpecialHeaders and AllowedModelRegion out of proxy._types by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44717
- refactor(types): import proxy-only types under TYPE_CHECKING in SDK modules by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44740
- refactor(logging): load enterprise alerting loggers lazily so import litellm skips proxy types by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44762
- perf(types): defer pydantic schema builds via shared LiteLLMBaseModel by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44720
- fix(router): price a model group from the deployments that serve it by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44732
- refactor: remove fresh tech debt from the 2026-10-05 window by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44821
- fix(azure): add gpt-6-sol priority processing prices by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44829
- refactor(types): replace Any with proven types in 6 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44491
- test: deflake the JEV classifier select and two router tests that inherited leaked state by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/44840
- refactor(rust): rename litellm-core to litellm-inference by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44802
- refactor(rust): extract inference-transcription crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44809
- refactor(rust): extract inference-responses crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44811
- refactor(rust): extract inference-messages crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44818
- refactor(rust): extract inference-chat crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44827
- refactor(rust): extract inference-ocr crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44832
- chore(rust): prune inference deps and rewrite layering docs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44836
- fix(otel): name an Arize project on every OTel v2 Arize export by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44605
- fix(otel): gate the Arize OTel v2 exporter on operator credentials by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44596
- fix(otel): honor per-team Arize sampling rates in OTel v2 fan-out by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44595
- fix(model_prices): gemini deep research input limits, vertex flash retirement dates, azure data zone gpt-6.1-sol
  pricing by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44633
- refactor(types): replace Any with proven types in 157 files by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/44798
- fix(sap): correctly handle cache_control by @yamaceay in https://github.com/BerriAI/litellm/pull/39122
- fix(responses): stop SDK retries nesting under router retries, and unbreak CircleCI integration tests by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44791
- fix(cost-map): update together_ai Kimi-K3 and Qwen3.8-Flash prices to published rates by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44864
- fix(ui): restore key activity search to the top of the tab and add model activity search by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/44521
- refactor(rust): extract inference-testing crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44873
- fix(ui): read MCP submission rules from bare-array /config/list response by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44648
- chore(model_prices): remove malformed, duplicate and decommissioned palm cost map entries by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44880
- fix(azure): add model router flat fee to azure provider cost tracking by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44876
- chore(pricing): add azure model-router and whisper rows by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44872
- fix(security): remove the publicly known master key from the repo by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44718
- chore(prices): add gemini/gemini-nano-banana-2.1 from the Gemini pricing page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44868
- fix(ci): skip the generated dashboard bundle in the master key guard by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44890
- fix(model_prices): correct supported_endpoints on gemini and vertex image rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44891
- feat(vertex-ai): add gemini-nano-banana-2.1 and Nano Banana 2 priority pricing by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44892
- fix(lens): reuse trace reviews and consolidate findings across runs by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44778
- fix(lens): paginate visible conversation entries by @moe-berri in https://github.com/BerriAI/litellm/pull/44878
- refactor(rust_bridge): remove rule-gated native secret-manager selection by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44906
- feat(otel): let team and key Arize callbacks choose the OTLP transport by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44492
- feat(proxy): add opt-in vector_store_deny_by_default for least-privilege vector store access by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44244
- feat(auth): deny search tools by default when search_tool_deny_by_default is set by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44490
- fix(lens): correlate native gateway spend with exact call evidence by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44738
- fix(caching): never store or serve a chat completion with no choices by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44709
- fix(auto-router): separate tuning and select chained heuristic by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44928
- fix(lens): copy supported trace and span content requests by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44902
- fix(tracing): retain native logs and headless tool results by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44894
- fix(lens): preserve chronological order when grouping trace steps by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44895
- fix(tracing): preserve optional provider evidence in fixture replay by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44930
- fix(lens): use async-timeout on python 3.10 for budget reservation timeouts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44911
- perf(lens): reduce rendering on live investigations by @moe-berri in https://github.com/BerriAI/litellm/pull/44935
- fix(logging): log spend once for large non-streaming requests on the chat to Responses bridge by @hektorjg in
  https://github.com/BerriAI/litellm/pull/44508
- feat(azure): add azure_ai/grok-4.7 and update grok-4.6 input price by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44937
- fix(projects): show Projects to team and org admins and scope it correctly by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41325
- fix(model_prices): drop /v1/batch from gemini/gemini-nano-banana-2.1 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44940
- chore: bump litellm-enterprise 0.1.73 -> 0.1.74, litellm-proxy-extras 0.4.105 -> 0.4.106, litellm 1.105.0 -> 1.106.0
  by @yuneng-berri in https://github.com/BerriAI/litellm/pull/44942
- fix(cost): price batch image output tokens at the batch image rate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44897
- fix(lens): refresh open traces without claiming session completion by @moe-berri in
  https://github.com/BerriAI/litellm/pull/44900
- fix(proxy): bound daily spend rollup row-lock waits with lock_timeout and requeue 55P03 by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/44450
- feat(otel): trace auto-router configuration and classifier failures by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44926
- feat(lens): add Copy for agent to investigation details by @moyai-berriai[bot] in
  https://github.com/BerriAI/litellm/pull/44945
- fix(proxy): resolve oidc/ pass-through credentials on every request by @nilpntr in
  https://github.com/BerriAI/litellm/pull/44577
- feat(lens): add datasets built from real traces by @ishaan-berri in https://github.com/BerriAI/litellm/pull/44765
- feat(lens-ui): replace the conversation view with a thread view by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44947
- fix(cli): show full-session auto-router cost comparison by @tin-berri in https://github.com/BerriAI/litellm/pull/44959
- fix(lens): show the first user message as the run input by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44958
- fix(terraform): keep unconfigured allowed_routes plan-known and unsent by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/44487
- test(e2e): add enum values, auto-discovering label gates and secret hiding for e2e metadata by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44949
- fix(proxy): stop logging license values during verification by @moyai-berriai[bot] in
  https://github.com/BerriAI/litellm/pull/44956
- refactor: expose core private helpers under public names by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44871
- test: fix shared-provider discovery, Codex catalog size and generated master key mismatches in CircleCI suites by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44905
- chore(cost-map): sync openrouter prices from the models API by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44975
- feat(mistral): add Mistral Large 4 (Le Chonk) support by @moyai-berriai[bot] in
  https://github.com/BerriAI/litellm/pull/44870
- fix(responses): preserve prompt cache reuse in chat bridge by @sorgfresser in
  https://github.com/BerriAI/litellm/pull/42281
- fix(mcp): keep worker MCP configurations consistent via a catalog revision by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/42568
- fix(ui): give Lens traces a flush toolbar layout by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44972
- fix(ci): generate a master key for the migration startup jobs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44978
- feat(mcp): add portable catalog pagination by @joshua-berri in https://github.com/BerriAI/litellm/pull/44446
- fix(exceptions): map upstream 402 to PaymentRequiredError and cool down 402 deployments by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/44879
- feat(claude_code_gateway): issue rotating refresh tokens and a revocation endpoint by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44635
- fix(azure): set kimi-k2.7-code deprecation date from the models list API by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/44986
- fix(docker): pin openssl-3.6-dev in the pgbouncer-builder stage by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44991
- feat(bedrock): add kimi k3 india cross-region row by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44990
- fix(azure): sync azure openai audio, realtime and image prices with azure pricing page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44992
- test: move whole-unit legacy test files into tests/unit and delete dead skips by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44807
- fix(bedrock): forward each Nova Sonic assistant sentence once over the realtime API by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44987
- test(mcp): run the static root path issuer discovery test in-process by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44988
- fix(realtime): skip guardrail VAD session.update injection for transcription sessions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44843
- fix(ci): stop deferred pydantic builds leaking caller locals and add the missing Lens FK migration by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44981
- fix(ui): render team_metadata_schema keys as fixed labels by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41482
- fix(vertex-ai): correct input_cost_per_second on gemini-3.5 transcribe-live and live-translate by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45002
- revert(docker): unpin openssl-3.6-dev in the pgbouncer-builder stage by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44997
- test(mcp): set server_id on openapi local fake tools by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44998
- ci: run integration-mcp on an xlarge machine by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44608
- refactor: expose public hidden_params accessors by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44668
- fix(azure): date claude-opus-5-5 and sonnet-5-5 and fill azure/eu/gpt-6-astra limits by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45018
- refactor: remove fresh tech debt from the 2026-10-06 window by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45017
- ci: give the database-backed CircleCI jobs their own Postgres by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45007
- test(proxy): make the stagger-offset and linear-dedup guards independent of runner identity and load by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45031
- refactor(types): replace Any with proven types in 16 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45029
- fix(auth): clear the recent-miss user memo when /user/new creates the user by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45020
- fix(health): attribute background health check results to their own deployment by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44982
- fix(ollama): turn streamed prompt-based JSON tool calls into real tool calls by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45053
- fix(bedrock): update GovCloud OpenAI prices, add GPT-6 Astra ultrafast tier and Titan Image v2 EOL by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45077
- fix(cost-map): add us data residency multiplier to anthropic claude-opus-5-5 by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45078
- refactor(llms): expose public names for private provider helpers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45037
- fix(bedrock): add 2027-03-30 deprecation date to DeepSeek R1 and Qwen3 Coder rows by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45089
- fix(proxy): opt-in Redis hash-tag grouping for v3 rate limiter by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45085
- fix(bedrock): take context and output limits from the Bedrock model cards by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/45091
- fix(tests): match the lowercased bind error in the owned-proxy port-race retry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45097
- test(e2e): tag llm_translation tests with Subject metadata and record harness steps by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44950
- test(e2e): tag claude_code cells with Subject metadata and record CLI driver steps by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44961
- test(e2e): tag management tests with Subject metadata and record management client steps by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44962
- test(e2e): tag guardrails and logging tests with Subject metadata and record client steps by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44963
- fix(caching): skip the cache past max_messages and keep tool_result text in semantic prompts by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43878
- test(e2e): tag router, batches and mcp tests with Subject metadata and record client steps by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44964
- test(e2e): tag the remaining quota_management tests and record budget and spend client steps by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44966
- fix(router): preserve native baseline identity and accounting by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44960
- test(integration): scope the team-scoped models upstream check to its own model by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45106
- fix(prometheus): add model_group label to end-to-end latency metrics by @ahamedshaik16 in
  https://github.com/BerriAI/litellm/pull/44860
- test(mcp): fix stale bridge-hook, applied-guardrails and pagination-revoke integration tests by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45008
- test(observability): wait for warm-up spend rows in capped and count only the post-wipe half in X4 by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45006
- fix(cost-map): lower anthropic claude-sonnet-5-5 cache read price by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/45113
- fix(prompt-caching): default injected /v1/messages breakpoints to implicit lookup by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/45121
- test(integration): turn the model-info refresh off in every integration proxy config by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45104
- test(e2e): let the realtime send step accept input audio buffer frames by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/45127
- feat(model_prices): add claude-haiku-5-5 model pricing by @krrish-berri-2 in
  https://github.com/BerriAI/litellm/pull/45108
- fix(realtime): run transcript guardrails on raw-path transcription sessions with a transcription-safe block by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44844
- test(integration): hold the wire barrier until the test releases it or the wire closes by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/45124
- fix(vertex-ai): correct claude-haiku-5-5 thinking and forced tool flags by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/45116
- feat(helm): allow custom labels, annotations, command and args on migrationJob by @ankitasahni511 in
  https://github.com/BerriAI/litellm/pull/42242
- test(e2e): tag a2a, access_control, other, secret_manager and migrations tests with Subject metadata by
  @ryan-crabbe-berri in https://github.com/BerriAI/litellm/pull/44965
- fix(azure): correct azure_ai/claude-haiku-5-5 forced tool use and thinking flags by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45114
- perf(lens): claim worker jobs from an indexed due queue instead of scanning every lens by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/45095
- perf(lens): prune ClickHouse partitions when sampling and sample in one pass by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45087
- fix(logging): bound data URI regex so base64 truncation stays linear by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45132
- perf(lens): bound single trace reads by the sampled start time by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45088
- feat(lens-ui): show findings ranked by priority with frequency and highlighted evidence by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45143
- fix(ollama): answer in text after a tool result and cover ollama e2e on all three endpoints by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45079
- fix(openai-compat): send provider attribution headers on the default SDK path (+ Perplexity) by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/44291
- ci(codeql): run the default suite on full scans and security-extended on PRs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45149
- feat(lens): flag traces with global System 1 signals by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45094
- feat(ui): configure Anthropic workload identity federation from the dashboard by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44889
- feat(guardrails): add logging_only_scope to observe input, output, or both by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43695
- test: move the unit half of 126 mixed legacy files into tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45090
- fix(model_prices): consolidate claude-haiku-5-5 over-100k pricing and capability flags by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/45151
- feat(ui): add auto-router usage and savings table by @tin-berri in https://github.com/BerriAI/litellm/pull/45152
- refactor(rust-bridge): unify native call inputs and Messages settings by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/45126
- test(e2e): move the harness self-tests out of tests/e2e by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/45172
- test(e2e): record steps for raw transport calls and poll helpers by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/45150
- feat(lens): link traces to the conversation that started them by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45169
- fix(router): resume sync streaming fallbacks without retrying primary by @amarrtech in
  https://github.com/BerriAI/litellm/pull/43959
- feat(guardrails): extend Akto guardrail to responses, MCP tools, attachments and masking by @rohan-akto in
  https://github.com/BerriAI/litellm/pull/44343
- fix(streaming): stop re-wrapping a bridged stream's MidStreamFallbackError by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44989
- fix(proxy): evict cached user on every proxy for tpm/rpm updates and edit limits in the users UI by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44130
- perf(lens): classify signals within seconds of a trace finishing by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45186
- feat(proxy): add denied_passthrough_routes deny list for custom pass-through endpoints by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/44924
- fix(responses): keep prompt_cache_breakpoint markers in the chat to responses bridge by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44119
- fix(mcp): preserve client application type during registration by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/45159
- feat(mcp): rate limit all MCP operations and add server-level rpm by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44600
- fix(ci): align misc unit tests with NativeCall bridge and widened e2e diff gates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45180
- fix(types): serialize deferred pydantic schema builds across threads by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45034
- fix(anthropic): normalize images for provider token counting by @tin-berri in
  https://github.com/BerriAI/litellm/pull/45185
- feat(lens): scope traces to one agent with a header picker by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45202
- chore(codeowners): replace kerry-berri with kerrylu-berri by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45173
- test: delete 73 legacy tests covered by e2e, unable to fail, or dead in CI by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45195
- feat(lens): isolate ingestion and investigations in a Rust service by @moe-berri in
  https://github.com/BerriAI/litellm/pull/45148
- fix(mcp): honor scoped cache freshness by @joshua-berri in https://github.com/BerriAI/litellm/pull/45165
- chore(ui): bump next to 16.3.8 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/45207
- refactor(rust-bridge): share field and response marshaling by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/45187
- fix(lens): preserve numeric tags and report OTLP error codes by @moe-berri in
  https://github.com/BerriAI/litellm/pull/45206
- fix(scheduler): remove a request's queue entry once it stops waiting by @RachelHuangZW in
  https://github.com/BerriAI/litellm/pull/43061
- fix(vertex_ai): dial the multi-region Live API host for realtime sessions by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45166
- feat(proxy,ui): add Moyai to the view switcher with quick connect by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45196
- fix(ci): restore vertex model sets mutated by get_optional_params tests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45209
- feat(decisions): add the OpenAI Decisions spec types and the System One translation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45129
- fix(anthropic): let /v1/messages mid-stream failures reach the proxy failure boundary by @Winoren in
  https://github.com/BerriAI/litellm/pull/44800
- test: remove dead imports and helpers left behind by legacy test deletion by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45208
- fix(vertex-ai): halve claude-sonnet-5-5 cache read price by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/45217
- fix(anthropic): fail closed when a token-file or inline-token federation credential is missing a rule or organization
  id by @mateo-berri in https://github.com/BerriAI/litellm/pull/45178
- fix(bedrock): map Scheduled batch jobs to in_progress on retrieve by @mrinal-berri in
  https://github.com/BerriAI/litellm/pull/45157
- feat(ui): redesign usage page with stacked model and agent charts by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45221
- fix(bedrock): lower claude sonnet 5.5 cache read price to the aws offer index by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45216
- fix(responses): keep cache breakpoints on blocks the bridge stringifies by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/40032
- fix(bedrock_mantle): lower claude sonnet 5.5 cache read price to match bedrock runtime by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45223
- fix(ui): address usage redesign review findings by @ishaan-berri in https://github.com/BerriAI/litellm/pull/45229
- perf(lens): faster trace opens and list pages at scale by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45228
- refactor(proxy): expose public names for private proxy helpers by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45170
- fix(ollama): one stream id, 400 on non-text tool content, separated tool results, no empty message item by
  @mateo-berri in https://github.com/BerriAI/litellm/pull/45177
- feat(lens): simplify deployment and first trace setup by @moe-berri in https://github.com/BerriAI/litellm/pull/45230
- fix(proxy): traceparent/baggage fallback must not override caller metadata by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43688
- fix(proxy): accept router-wide default_litellm_params in required-param validation by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/44483
- fix(proxy): keep idle responses websockets open until a configurable session limit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44433
- fix(lens-ui): open traces on the top-level step and stop showing model names as input by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45254
- refactor(decisions): dispatch /v1/decisions through provider configs and the shared HTTP handler by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45130
- feat(lens): show agent, user and slack thread first in the run header by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45261
- fix(proxy): declare the Moyai settings write's service target and allowlist its routes by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/45220
- feat(lens): show end-user feedback on traces, stored in ClickHouse by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45171
- fix(proxy): admit litellm_proxy/hosted_vllm in provider-endpoint discovery by @mayuriphad in
  https://github.com/BerriAI/litellm/pull/38617
- feat(decisions): serve System One format at /v1/systemone and OpenAI format at /v1/decisions by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45184
- feat(decisions): add OpenAI as a Decisions provider behind a shared decisions format by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45214
- feat(lint): add LIT015 requiring pydantic models to be frozen by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42348
- fix(router): keep include_fallback_errors off the provider call on the sync Router path by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45218
- fix(router): honor a per-request fallbacks list on a mid-stream fallback by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45227
- fix(responses): map input_audio blocks in the chat-to-Responses bridge by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45224
- fix(proxy): answer a rejected websocket handshake without crashing the HTTP exception handler by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45251
- ci(lint): gate every rule on its merge-base count and cap Anys at a fixed total by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40193
- test(e2e): cover responses API gaps on gemini, azure, compact and context management by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45248
- chore: bump litellm-proxy-extras to 0.4.107 and litellm-enterprise to 0.1.75 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45291
- test(integration): boot owned proxies with a readiness-sized worker healthcheck budget by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/45292
- fix(utils): make supports_audio_output read the supports_audio_output cost-map key by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45294
- fix(lens): refresh runs until gateway costs are complete by @tin-berri in
  https://github.com/BerriAI/litellm/pull/45105
- fix(lint-gates): fail on an empty base scan instead of blaming the change for every violation by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45314
- refactor(proxy): type fresh Moyai connect helpers and drop MCP rpm getattr by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45315
- revert(lint-gates): accept an empty base scan again, since zero violations is a legitimate count by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45319
- fix(bedrock_mantle): send OpenAI explicit prompt cache breakpoints for GPT-5.6 and newer by @msdianprince-7 in
  https://github.com/BerriAI/litellm/pull/38729
- test: make 77 legacy live tests offline in litellm_utils, router_unit and responses dirs by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/45298
- test: move 81 legacy live tests in pass-through, spend, batches, audio, search, guardrails, image and ocr dirs offline
  by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45288
- feat(ui): add TypeSafe and Strands Decider to the Add Model provider list by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45335
- feat(mcp): support upstream OAuth client metadata identities by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/45231
- fix(proxy-extras): name the database error when the Lens rename check cannot run by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45341
- test(integration): run the response cache tool-call tests on a proxy without the message cap by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45350
- fix(logging): skip sync success callbacks for internal sub-calls, deflake RAG and Langfuse tests by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45345
- fix(azure): move sora-2 retirement date to the later Models API date by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/45355
- fix(lens): block teamless feedback writes and fix retention test by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/45266
- fix(ci): trim rust-test debuginfo so the job fits on the runner disk by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45318
- fix(ui): list only catalog models in the Add Model picker by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44877
- feat(rust): add standalone typed LLM wire contracts by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/45188
- test: delete 34 legacy tests already covered by e2e by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45340
- fix(responses): keep tool_result next to tool_use on Anthropic previous_response_id continuations by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45322
- test: realign stale decisions and lens tests with merged behaviour by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45346
- feat(prometheus): expose per-project per-model rate limit allowed and used gauges by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43561
- fix(mcp): preserve elicitation context and report relay failures by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/45255
- docs(rust): add ADRs for the Rust core by @nate-berri in https://github.com/BerriAI/litellm/pull/45205
- test: move 76 live top-level tests to offline unit and integration coverage by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45352
- fix(proxy): mark background responses stale_expired when provider returns 404 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41724
- fix(bedrock): take context, output limits and EOL dates from the Bedrock model cards by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45409
- chore(cost-map): add openai gpt-6.1-sol ultrafast tier prices from the pricing page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45408
- fix(bedrock_mantle): take gpt-oss output limits and EOL dates from the Bedrock model cards by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45417
- fix(rust): path-qualify attribute aliases so rust-analyzer resolves them by @nate-berri in
  https://github.com/BerriAI/litellm/pull/45416
- fix(proxy): use budget reset window for projected spend alerts by @Solomon-mithra in
  https://github.com/BerriAI/litellm/pull/31942
- test(proxy): audit the websocket rejection log on every live route by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45293
- fix(proxy): retry lock-timed-out daily spend batches in place so the shutdown flush keeps them by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45273
- fix(vertex_ai): forward the inline-tools-2026-09-15 beta to Vertex and Anthropic by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45297
- feat(fireworks_ai): forward the LiteLLM user id as user behind fireworks_forward_user_id by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/45265
- fix(model_prices): add Bedrock flex prices, Anthropic web search flags, Gemini shutdown dates, OpenRouter alias drift,
  Mistral Large 4 context by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44910
- feat(voyage): rebrand to VoyageAI by MongoDB and route MongoDB keys to ai.mongodb.com by @fzowl in
  https://github.com/BerriAI/litellm/pull/41812
- feat(gemini): accept file content blocks with video_metadata on multimodal embeddings by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45305
- feat(rust): add the Anthropic beta header policy by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/45419
- test(decisions): post System One bodies to /v1/systemone in the translation bases by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/45327
- fix(ci): drop the publicly known master key prefix from the voyage routing test by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45431
- feat(guardrails): per-mode stream_scope with bedrock stream and pass-through fixes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43801
- refactor(python-bridge): take NativeCall directly and fold routes into per-route folders by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/45413
- fix(lens): prevent progress updates from starving analysis budget reservations by @moe-berri in
  https://github.com/BerriAI/litellm/pull/45432
- refactor(rust): derive strum VariantArray and string conversions by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/45434
- chore(decisions): remove the System One converters and OpenAI spec types left dead by #45214 by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45442
- feat(spend_logs): configure which metadata fields are stored in LiteLLM_SpendLogs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44659
- fix(ui): show the Add Model picker once the model catalog loads after a provider is picked by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/45426
- fix(rust): add the inline-tools-2026-09-15 beta to AnthropicBeta by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45439
- fix(bedrock): count tokens on bedrock-mantle when bedrock-runtime cannot count a Claude model by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45317
- fix(ui): link model access group chips to the access group filter by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45402
- fix(proxy): accept team-scoped models by their public name on POST /fallback by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45455
- fix(otel): emit OpenInference tool calls and metadata on Arize OTel v2 spans by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43698
- test(ui-e2e): update usage page selectors after the #45221 redesign by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45347
- test: replace 61 live logging and otel tests with offline unit and integration coverage by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/45362
- fix(bedrock): remove the bare xai.grok-4.7 cost-map row that AWS cannot invoke by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45460
- test: make 38 legacy live base-class translation tests offline by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45351
- fix(bedrock): split the <reasoning> tag for gpt-oss only on native Chat Completions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44432
- feat(ui): add Cmd+K command palette with key search by @ishaan-berri in https://github.com/BerriAI/litellm/pull/45456
- test(streaming): expect the unwrapped provider error in bridged /v1/messages error frames by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45465
- refactor(python-bridge): derive NativeCall extraction by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/45449
- refactor(python-bridge): ship a signature base and read the resolved call by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/45450
- fix(cost-map): update baseten DeepSeek-V4.1-Flash-Fast cache read price and max output by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45468
- ci(unit): add unit passed collector job and fold proxy-db shards into test-unit.yml by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45466
- feat(guardrails): support logging_only mode for the Akto guardrail by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/45461
- fix(router): drop the encrypted reasoning a fallback hop's target cannot decrypt by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45393
- chore(cost-map): sync openrouter prices from the models API by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/45469
- fix(cli): pin pi compat flags so lite pi stops sending store to Anthropic models by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40739
- feat(bedrock): add twelvelabs pegasus 1.5 inference profiles by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/45477
- feat(sdk): build core from an independent packaging manifest by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/44340
- fix(proxy): save file details for every batch output file so they list and retrieve by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41761
- fix(bedrock): remove the bare openai.gpt-6.1-sol cost-map row that AWS cannot invoke by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45479
- refactor(sdk): separate core AWS and tokenizer dependencies by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/44447
- fix(router): match deployment pricing ids against the cost map only within the deployment's provider by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45472
- fix(bedrock): add gpt-6.1-sol ultrafast tier prices from the Bedrock model card by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45482
- fix(ci): import seed_tracing_fixtures from the pytest scripts path in rust trace tests by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/45485
- fix(bedrock): take gpt-6.1-sol context window from the Bedrock model card by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/45488
- feat(ui): add the evaluation mode to the Add Model form by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45481
- feat(mcp): translate input requests and bind continuations by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/45464
- fix(bedrock): add the claude-sonnet-4-5 EOL date from the Bedrock model card by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/45496
- fix(token_counter): price a base64 PDF document per page instead of as one image by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45301
- ci: render lint, unit and smoke checks as <tier> / <job> with one collector per tier by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45480
- test(routing): wait on deployment registration instead of boot model-info traffic by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/45267
- fix(anthropic): count a leading system run through count_tokens' system parameter by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45463
- ci: run only integration jobs on PR CircleCI pipelines and move router and guardrails suites to GHA by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45509
- test: update stale MCP call_tool and usage card assertions, add timeout headroom to request-log index boot test by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45523
- feat(credentials): add display_name and make credential_name immutable on PATCH by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43148
- fix(ui): let the model picker remove selections that are no longer available by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43944
- refactor(proxy): inject one UTC clock read per operation into gateway tracking, PTU rollup and Mavvrik export by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45520
- refactor(proxy): inject the clock into the v1 parallel request limiter and pin it in its tests by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45522
- chore: bump litellm-enterprise 0.1.75 -> 0.1.76, litellm-proxy-extras 0.4.107 -> 0.4.108 by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/45534
- feat(ui): configure OpenAI workload identity federation from the LLM Credentials and Add Model forms by @mateo-berri
  in https://github.com/BerriAI/litellm/pull/45528
- fix(mcp): never forward the caller's LiteLLM key to MCP servers by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/45401
- ci: run every build_and_test job in every CircleCI pipeline (#43152) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/45651
- feat(decisions): backport Microsoft-Decision-1 and the decision models Admin UI to rc/1.106.0 (#45639, #45673, #45654,
  #45717) by @mateo-berri in https://github.com/BerriAI/litellm/pull/45735
- feat(ui): backport the System One request form to rc/1.106.0 (#45721) by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45739
- feat(guardrails): backport the logging_only scope split to rc/1.106.0 (#45709) by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/45782
- fix(ui): backport modal backdrop fix to rc/1.106.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/45877
- feat(guardrails): backport the decision model guardrail to rc/1.106.0 (#45663) by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/45888
- fix(credentials): backport credential edit fixes to rc/1.106.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/45890
- fix(mcp): backport request-local guardrail bearers to RC 106 by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/45901
- feat(decisions): backport the rest of the decisions and System One launch to rc/1.106.0 by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/45891
- feat(ui): backport the Home page dashboard root to rc/1.106.0 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45911
- feat(ui): backport decision auto-router setup to 1.106 by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/45916
- fix(home): serve the bundled whats_new.json by default on rc/1.106.0 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45922
- feat(ui): backport the form-first Decisions playground restyle to rc/1.106.0 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45929
- chore: rebuild Admin UI bundle for rc/1.106.0 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45930
- fix(ui): backport Decisions yes / no answer type label to rc/1.106.0 (#45931) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45933
- feat(ui): backport #46260 Home What's new from day 0 support blog posts to rc/1.106.0 by @kerry-berri in
  https://github.com/BerriAI/litellm/pull/46309
- fix(guardrails): backport #46086 to rc/1.106.0 by @mateo-berri in https://github.com/BerriAI/litellm/pull/46383
- fix(prometheus): backport #46267 to rc/1.106.0 by @yucheng-berri in https://github.com/BerriAI/litellm/pull/46491
- feat(decisions): backport #45474, #45811, #45734, #46594, and #46596 to rc/1.106.0 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/46628
- fix(proxy): backport #46408 to rc/1.106.0 by @mateo-berri in https://github.com/BerriAI/litellm/pull/46827
- fix(caching): backport #45784 and #46488 to rc/1.106.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/47006
- test(e2e): backport three stale e2e test fixes from main to rc/1.106.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/47229

## New Contributors

- @Bernedotcom2312 made their first contribution in https://github.com/BerriAI/litellm/pull/42141
- @jimaldon made their first contribution in https://github.com/BerriAI/litellm/pull/40924
- @SteffanWolter made their first contribution in https://github.com/BerriAI/litellm/pull/40108
- @wakqasahmed made their first contribution in https://github.com/BerriAI/litellm/pull/42213
- @Aasif-Multani made their first contribution in https://github.com/BerriAI/litellm/pull/44183
- @joeym82956 made their first contribution in https://github.com/BerriAI/litellm/pull/44318
- @kohjunhao made their first contribution in https://github.com/BerriAI/litellm/pull/44173
- @ninadphalak made their first contribution in https://github.com/BerriAI/litellm/pull/42645
- @anniejeng made their first contribution in https://github.com/BerriAI/litellm/pull/44278
- @yamaceay made their first contribution in https://github.com/BerriAI/litellm/pull/39122
- @hektorjg made their first contribution in https://github.com/BerriAI/litellm/pull/44508
- @nilpntr made their first contribution in https://github.com/BerriAI/litellm/pull/44577
- @sorgfresser made their first contribution in https://github.com/BerriAI/litellm/pull/42281
- @ankitasahni511 made their first contribution in https://github.com/BerriAI/litellm/pull/42242
- @amarrtech made their first contribution in https://github.com/BerriAI/litellm/pull/43959
- @rohan-akto made their first contribution in https://github.com/BerriAI/litellm/pull/44343
- @RachelHuangZW made their first contribution in https://github.com/BerriAI/litellm/pull/43061
- @Winoren made their first contribution in https://github.com/BerriAI/litellm/pull/44800
- @mayuriphad made their first contribution in https://github.com/BerriAI/litellm/pull/38617
- @Solomon-mithra made their first contribution in https://github.com/BerriAI/litellm/pull/31942

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.105.0...v1.106.0

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
  ghcr.io/berriai/litellm:v1.105.1
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.105.1/cosign.pub \
  ghcr.io/berriai/litellm:v1.105.1
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

## What's Changed

- fix(proxy): backport #44243 and #44508 to stable/1.105.x for v1.105.1 by @kerry-berri in
  https://github.com/BerriAI/litellm/pull/46313

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.105.0...v1.105.1

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
  ghcr.io/berriai/litellm:v1.105.0
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.105.0/cosign.pub \
  ghcr.io/berriai/litellm:v1.105.0
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

## What's Changed

- feat(mcp): share compatibility-aware result conversion across tool surfaces by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43089
- fix(caching): propagate auth cache invalidation over Redis Cluster via a node-level pub/sub client by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43110
- feat(model-catalog): add Rust registry validation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43136
- test(rust): reorganize core crate tests and split cache and OCR suites by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43177
- fix(proxy): give SpendLogToolIndex its own share of the cleanup budget and log a per-run summary by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41768
- feat(rust): hand upstream response headers to the native Messages stream by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43178
- feat(testkit): agent clients for Claude Code, Codex and opencode by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43181
- ci: run migrated unit selections on every event in legacy GHA shards by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43182
- test: move tests/test_litellm root and small trees into tests/unit by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43186
- fix(sso): gate /sso/debug routes behind ENABLE_SSO_DEBUG, off by default by @ojensen-berri in
  https://github.com/BerriAI/litellm/pull/43150
- refactor(framer): replace Framer trait with tokio-util codecs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43193
- fix(anthropic): surface Responses bridge stream failures as Anthropic error events by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43126
- test: move tests/test_litellm/llms into tests/unit/llms by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43191
- test: move tests/test_litellm integrations and secret_managers into tests/unit by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43194
- feat(mcp): configure protocol versions and capability discovery by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/43169
- fix(proxy): record streamed /v1/responses container ownership before the response.completed frame by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43140
- fix(tests): drop the repeated UNIT_FLAG key in test_unit_shard_missing_paths by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43212
- fix(router): count provider budget spend on every API surface by @daqiangganjun in
  https://github.com/BerriAI/litellm/pull/38172
- fix(responses): fall back on pre-output stream drops, fail truncated streams, honor request_timeout by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43133
- fix(sentry): scrub PII and secrets inside object reprs and nested locals, add SENTRY_SEND_DEFAULT_PII opt-in by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43123
- fix(bedrock): surface a converse-stream 200 that decodes to no events as a 502 instead of an empty turn by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43213
- fix(jwt): let x-litellm-team-id select DB membership teams when the token also carries a team claim by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43206
- feat(integrations): add Databricks Zerobus trace logging callback by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42013
- fix(vertex_ai): keep legacy bucket_name in credential resolution and add GCS_BATCH_BUCKET_NAME env var by
  @mubashir1osmani in https://github.com/BerriAI/litellm/pull/42803
- feat(xai): add native xAI batches and files support by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42812
- fix(proxy): send a real error event when a /v1/messages stream fails by @4refael in
  https://github.com/BerriAI/litellm/pull/41826
- fix(logging): redact raw_request when turn_off_message_logging is set in the proxy config by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43219
- fix(router): parse the classifier verdict out of surrounding prose instead of falling to the default tier by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43215
- test(zerobus): move tests into active CI selection by @tin-berri in https://github.com/BerriAI/litellm/pull/43235
- fix(proxy): keep the submitted body out of 422 validation errors by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43231
- test: move tests/test_litellm core utils, routing, responses, caching and rust_bridge into tests/unit by @yuneng-berri
  in https://github.com/BerriAI/litellm/pull/43199
- chore(cost-map): add fireworks us-only deepseek v4.1 flash priority prices by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/43247
- chore(cost-map): sync openrouter prices and add perceptron-mk1.5 by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43246
- fix(cost-map): correct fireworks_ai deepseek-v4p1-flash pricing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43253
- feat(openrouter): add typesafe/jev-router to the cost map by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43248
- chore(cost-map): add fireworks priority prices for muse glimmer 30b and deepseek v4 flash vision exp by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43252
- refactor(rust): move credential inheritance and SDK limits into a driver preflight by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43259
- fix(router): hold Responses lifecycle events until output so a pre-output fallback announces one response by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43238
- refactor(http): hand out an owned Client and route all providers through the pool by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43245
- test: fix stale and state-leaking tests red on scheduled CircleCI by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43266
- fix(cost-map): retirement dates, chatgpt reasoning flags, bing pricing, bedrock mantle and mythos, azure gpt-5.6
  alias, anthropic batch rates, new nebius, openrouter and xai rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42951
- refactor(rust): promote anthropic messages out of experimental_pass_through by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43269
- test: stop CI tests from downloading tokenizer files and images by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43257
- fix(rust): preserve nested optional import failures by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43265
- ci: drop main and litellm_* branch filters from the CircleCI litellm-main workflows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43272
- feat(proxy): email alerts at configured percentages of a team member budget by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42665
- fix(callbacks-legacy-python): traverse and release the retained headers dict by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43274
- test(integration): port langfuse callbacks-in-db coverage to the local harness by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43282
- test(e2e): accept the otel cost write as a linked root trace by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42931
- test: finish the non-proxy half of tests/test_litellm by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43281
- refactor(rust): prepare inference and auth foundations for the gateway by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43287
- feat(rust): add config, router and gateway crates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43289
- fix(cost-map): remove duplicate openrouter/perceptron/perceptron-mk1.5 entry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43273
- fix(e2e): resolve the blank-S3 gateway repo root from the litellm package location by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42911
- test(integration): run the Langfuse DB-callback test on its own scratch database by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43288
- refactor(rust): expand logging and test coverage across gateway and Anthropic messages by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43295
- refactor: daily fresh tech debt cleanup, rolling PR (2026-09-25) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43151
- test(proxy_behavior): scope the management proxy fixture to its package so its spend monitor cannot race the spend
  tests by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43302
- fix(cost-map): registry audit 2026-09-26, MAI-Image-2.5-Flash price, Databricks Claude Opus 5.5, Azure Foundry
  retirement dates by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43254
- fix(cost-map): price fireworks deepseek v4.1 flash at the prices api value by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/43311
- fix(ci): stop stale CI reds, keep unit tests off the host env, retry CyberArk policy conflicts by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43294
- fix(otel): detach post-response service spans by request phase, name redis spans by operation by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43237
- test(e2e): assert only litellm-owned batch behavior and move the blank S3 env pin to an integration test by
  @yuneng-berri in https://github.com/BerriAI/litellm/pull/43321
- test(integration): pin the team-admin status-code matrix across every management route by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/43249
- feat(proxy): add fail_closed_rate_limit_enforcement to reject requests with 503 while Redis rate limit counters are
  unreachable by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43251
- fix(responses): run stream failure and success hooks on the iterating loop instead of blocking it by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43270
- fix(guardrails): block private destinations in custom code http_request and bound guardrail execution time by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43280
- feat(sail): add Sail as a provider with service_tier mapped to its completion window by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42840
- test(mcp): pin server resolution and authorization behavior by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/43261
- refactor(anthropic): rename experimental_pass_through to pass_through by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43329
- refactor(mcp): add shared server resolver without changing callers by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/43262
- ci: fail on new unbounded SQL IN lists and add a Prisma chunking helper by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/42629
- test(logging): drain the logging worker after each logging callback test so no later test inherits its events by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43344
- feat(guardrails): scan retrieved vector store chunks with the request's pre-call guardrails by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43271
- fix(mcp): adopt shared server resolution and caller authorization by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/43263
- fix(s3_v2): upload fresh events first, drop terminal failures and hour-old retries by default, opt-in adaptive
  concurrency by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43022
- feat(proxy): add maximum_daily_tag_spend_retention_period cleanup setting by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39221
- fix(cost-map): sync OpenRouter, Together, Cohere and Azure AI registry values with official sources by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43337
- docs(pr-template): add the backport-stable label only for a P0 regression by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43351
- fix(params): keep _litellm_* kwargs out of provider request bodies by construction by @shrey-berri in
  https://github.com/BerriAI/litellm/pull/43221
- test: remove substring guard test_default_api_base by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43355
- ci: cut CircleCI wall time without loosening test isolation by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43347
- fix(cost-map): correct azure gpt-4o-mini tts, transcribe, alias and MAI-Image-2.5 prices by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43357
- fix(tests): stop VCR recording and replaying a test's own localhost upstream by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43346
- test(integration): group /v1/messages contracts under tests/integration/messages_endpoint by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43352
- fix(params): validate stream_chunk_size once, before any provider call by @shrey-berri in
  https://github.com/BerriAI/litellm/pull/43222
- fix(openai): exclude fine-tuned and custom gpt-5-chat aliases from gpt-5 reasoning path by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43185
- fix(langtrace): deliver spans to app.langtrace.ai/api/trace with x-api-key by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43322
- fix(caching): stand default cache points down when extra_body hides a direct client mark by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43341
- fix(mcp): report reachability without stored credentials by @tin-berri in
  https://github.com/BerriAI/litellm/pull/43240
- fix(mcp): align hub publication status and controls by @tin-berri in https://github.com/BerriAI/litellm/pull/43241
- chore(cost-map): sync openrouter prices for deepseek, minimax, qwen and glm rows by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43384
- chore(cost-map): drop stale cache hit field from openrouter deepseek-v4-pro-0813 by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43389
- fix(responses): stream guardrail pre-call block as SSE with a typed output item by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42507
- feat(e2e): read management routes back from the control plane replicas by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43373
- feat(rust): add the openai_like chat config foundation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43379
- feat(router): opt in to prompt-cache cost routing by @tin-berri in https://github.com/BerriAI/litellm/pull/43232
- feat(otel): add SigNoz preset for OpenTelemetry v2 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43296
- feat(cli): reuse saved agent setup and add reconfigure by @tin-berri in https://github.com/BerriAI/litellm/pull/43392
- fix(streaming): keep litellm Usage on text-completion usage chunks by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43047
- fix(vertex_ai): consider tools when validating context caching min tokens by @agustin18 in
  https://github.com/BerriAI/litellm/pull/43319
- fix(anthropic): drop thinking blocks with empty thinking text, not just missing signature by @shoemoney in
  https://github.com/BerriAI/litellm/pull/38049
- test(e2e): report batch cleanup leftovers as a plain UserWarning by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43405
- fix(tools): salvage concatenated JSON tool call arguments by @kumarpriyanshu09 in
  https://github.com/BerriAI/litellm/pull/43260
- fix(gemini): forward seed to the Gemini API instead of rejecting it by @YaseenBashaT in
  https://github.com/BerriAI/litellm/pull/43197
- fix(vertex_ai): make Gemma fake streams work with traced Responses by @stewartpark in
  https://github.com/BerriAI/litellm/pull/43147
- fix(responses): emit the reasoning item on streaming /v1/responses for signature-only thinking by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43414
- fix(anthropic): forward the per-turn-control beta to Azure AI Foundry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43415
- test(vertex_ai): assert the usage the Gemma responses stream actually reports by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43422
- fix(bedrock): keep the provider status code on unprocessable image errors by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43416
- fix(vertex_ai): stop importing the vertexai SDK in partner-model completion by @anmolg1997 in
  https://github.com/BerriAI/litellm/pull/42274
- fix(token_counter): count Gemini function_declarations tools by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43417
- refactor(types): replace Any with proven types in 5 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43304
- chore(cost-map): update azure_ai/grok-4.6 input price from Azure pricing page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43440
- chore(cost-map): add azure_ai/MAI-Cyber-1-Flash by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43446
- refactor(rust): share anthropic types, request helpers, and streaming contracts across crates by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43426
- feat(rust): expand gateway configuration parsing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43460
- refactor(rust): share call lifecycle across route-owned inference by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43461
- feat(rust): add the HTTP host driver by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43462
- build(rust): package the gateway container by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43471
- refactor(rust): use shared execution in gateway inference by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43463
- fix(cost-map): add deprecation_date to together_ai Salesforce/Llama-Rank-V1 by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43507
- feat(rust): support the HTTP Responses API by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43464
- fix(cost-map): sync openrouter prices from the models API by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43506
- fix(cost-map): set together_ai gpt-oss-20b and gemma-4-31B-it deprecation_date to 2026-09-15 by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43509
- feat(rust): add litellm-db and litellm-db-testing workspace scaffolding by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43504
- feat(rust): connect Python inference bindings to shared routes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43465
- feat(rust): add structured route lifecycle tracing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43466
- feat(rust): separate gateway authentication and authorization by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43467
- feat(rust): add virtual key storage contracts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43468
- feat(rust): add gateway UI login and sessions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43469
- feat(rust): add the MCP gateway by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43470
- refactor(rust): remove delivery routing abstraction by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43514
- feat(azure): add mistral ocr pricing and azure max output limits by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43530
- refactor: clean up fresh tech debt from 2026-09-27 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43538
- refactor(types): replace Any with proven types in 8 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43551
- test(rust): enforce shared upstream error contract in wheel checks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43520
- fix(proxy): log key owner identity on expired key auth failures by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43105
- fix(cost-map): registry audit 2026-09-28, openai deep-research shutdown dates, azure deepseek v4.1 flash direct price,
  vertex gemini 3.8 live avatar price, drop azure_ai/muse-spark-1.3 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43566
- security(proxy): keep team callback credentials out of the stored request body by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43217
- feat(model_prices): add claude-sonnet-5-5 model pricing by @krrish-berri-2 in
  https://github.com/BerriAI/litellm/pull/43586
- test(integration): pin org-admin status codes in the team-admin matrix by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/43592
- refactor(guardrails): fix agent 365 to the production endpoint and log the opt-in fail_open at error level by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43189
- fix(model_prices): correct Claude Sonnet 5.5 capabilities and provider keys by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43587
- test(unit): stop test modules from putting their own directory on sys.path by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43421
- refactor(rust): centralize host execution and compose callbacks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43515
- fix(proxy): unregister logging callbacks removed from the stored config by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43428
- chore(cost-map): take azure limits for deepseek-v4-flash-0731 and v3.2-speciale by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43597
- revert: "feat(proxy): server-side Team Usage export beyond the top-N key cap (#42996)" by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/43376
- fix(cost-map): add web search flag and model page source to anthropic claude-sonnet-5-5 by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43584
- refactor(mcp): consolidate hub publication predicate by @tin-berri in https://github.com/BerriAI/litellm/pull/43394
- fix(provider): accept 2xx status codes in unified_access_group create by @Louis-Vauterin in
  https://github.com/BerriAI/litellm/pull/42461
- fix(panw_prisma_airs): honor experimental_use_latest_role_message_only on every request shape by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42447
- fix(cost-map): add Vertex batch cache prices to vertex_ai/claude-sonnet-5-5 by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43602
- revert: "feat(usage): search team keys beyond the top-N in the Team usage view (#42857)" by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/43377
- feat(providers): add Prism provider (internal copy of #40914) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41961
- test(integration): credential canary suite harness by @yucheng-berri in https://github.com/BerriAI/litellm/pull/43300
- feat(bedrock): add xai grok-4.7 pricing and sync llama, mistral large 2407 and minimax m2.5 prices by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43623
- ci: sync the weekly release cycle with Linear releases by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43636
- feat(cache): select Rust caching through explicit cache objects by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43601
- test(integration): credential canary slots for MCP and pass-through credentials by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/43308
- test(integration): stored-config credential canary slots by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/43309
- fix(guardrails): preserve Presidio output selection and restoration by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/43401
- fix(ui): rename All Models tab to Deployed Models and model filters to All Proxy Models by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43638
- feat(mcp): scan and pin upstream tool descriptions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43283
- feat(cost-map): add bedrock_mantle rows for claude opus 5.5 and sonnet 5.5 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43647
- chore(codeowners): drop UI, migration, and CODEOWNERS self owners by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43653
- feat(fireworks_ai): route and list the auto, auto-instant and firerouter routers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43641
- feat: add model leaderboard page by @ishaan-berri in https://github.com/BerriAI/litellm/pull/43649
- fix(google_genai): preserve proxy_server_request in completion adapter by @hsm207 in
  https://github.com/BerriAI/litellm/pull/43536
- fix(otel): send cache and reasoning tokens in langfuse usage_details by @ankit373 in
  https://github.com/BerriAI/litellm/pull/43553
- fix(vertex_ai): forward the per-turn-control beta for per-message output_config by @DeviaVir in
  https://github.com/BerriAI/litellm/pull/43558
- fix(cost-map): add tool calling and reasoning flags, correct max output for nebius DeepSeek-V4.1-Flash by
  @Flexomatic81 in https://github.com/BerriAI/litellm/pull/43588
- fix(proxy): resolve model_group_alias in the zero-cost budget predicate by @fedaeho in
  https://github.com/BerriAI/litellm/pull/43512
- refactor: clean up fresh tech debt from 2026-09-28 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43674
- refactor(types): replace Any with proven types in 7 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43704
- docs(security): point readers to the security announcements mailing list signup by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43713
- refactor(rust): add shared llms wire type derives by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43730
- fix(router): stream /v1/messages lifecycle frames live when no fallback can take over by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43600
- feat(cost-map): add baseten DeepSeek-V4.1-Flash-Fast by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43735
- feat(guardrails): send a configured gateway_name from noma_v2 to Noma by @itaimodi in
  https://github.com/BerriAI/litellm/pull/43678
- chore(cost-map): add openai gpt-6.1-sol from the pricing page by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43738
- test(integration): callback credential canary slots C1-C3 and D5 by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/43630
- test(integration): request-path credential canary slots D1-D4 by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/43307
- test(integration): sweep proxy logs, metrics, a Datadog intake and the Logs drawer for credential canaries by
  @yucheng-berri in https://github.com/BerriAI/litellm/pull/43306
- chore(cost-map): add azure and openrouter gpt-6.1-sol rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43744
- test(proxy): classify every credential-bearing param for the canary suite by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/43298
- fix(cost-map): lower fireworks up-to-4b size tier to the pricing page price by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43740
- fix(cost_calculator): bill chat per-second pricing once with a new cost_per_second field by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43614
- chore(cost-map): add openai gpt-6-astra ultrafast tier prices from the pricing page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43745
- fix(autorouter): compare historical and new savings consistently by @tin-berri in
  https://github.com/BerriAI/litellm/pull/43348
- fix(model-prices): align Azure, Bedrock, Copilot, Gemini, Groq, OpenAI and OpenRouter entries with official docs by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43598
- fix(guardrails): enable explicit PANW MCP output scanning by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43109
- refactor(rust): orchestrate Messages route execution by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43719
- fix(streaming): keep the served service_tier on streamed chunks and spend rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42870
- feat(bedrock): add openai gpt-6.1-sol global and base rows by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43758
- perf(router): fetch cooldown state and usage counters in one Redis round trip by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43320
- perf(proxy): hold one spend counter batch across admission and across post-call accounting by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43369
- perf(responses): run aresponses through the async wrapper so the cache is read once by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43769
- fix(router): bind Claude Code background sessions to their auto-router by @tin-berri in
  https://github.com/BerriAI/litellm/pull/43767
- feat(bedrock): add openai.gpt-6.1-sol us geo cris and Mantle rows by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43763
- fix(proxy): recover session key owners from daily spend for usage attribution by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43642
- chore(cost-map): take azure context limits from models-sold-directly by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43759
- perf(proxy): one request-scoped Redis pipeline for auth, spend, rate-limit and routing reads by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43407
- fix(mcp): scope OpenAPI listings to the exact server prefix and drop upstream OAuth metadata when a server is saved by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43608
- perf(proxy): one post-call Redis pipeline per backend for spend, rate-limit, routing and response-cache writes by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43779
- fix(bedrock): set gpt-6.1-sol max output tokens to 131072 by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43782
- perf(proxy): refresh auth management objects through the request Redis pipeline by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43776
- feat(agents): add identity storage and validation contracts by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/43720
- chore: bump litellm-enterprise 0.1.71 -> 0.1.72, litellm-proxy-extras 0.4.102 -> 0.4.103, litellm 1.104.0 -> 1.105.0
  by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43789
- fix(auth): give UI/CLI session tokens their own AES-GCM context and header-safe shape by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43790
- chore(deps): bump pyjwt, moment and brace-expansion to clear osv-scan by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43792
- fix(ui): surface x-litellm-call-id in Logs search, table and drawer by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42436
- fix(proxy): look up hashed key names with two spend log rows per key by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43656
- fix(cost-map): add deprecation_date to two together_ai nvidia rows by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43809
- test(ci): refresh retired OpenAI tool-call models by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43676
- fix(ui): keep MCP permissions visible after key, team and MCP server saves by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43810
- test(ci): repair MCP Responses and budget fixtures by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43788
- test(bedrock): accept regional aliases that inherit Converse routing by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43785
- fix(params): categorize internal param appropriately to prevent leaking into request by @shrey-berri in
  https://github.com/BerriAI/litellm/pull/43783
- perf(router): honour the cooldown read interval in the routing prefetch by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43815
- fix(router): carry per-request routing reads on context variables instead of public method kwargs by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43814
- fix(bedrock): add beta header for output config in message by @shrey-berri in
  https://github.com/BerriAI/litellm/pull/43778
- refactor: clean up fresh tech debt from 2026-09-29 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43830
- test(router): settle the shared logging worker before recording shadow callbacks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43847
- chore(model_prices): add Gemini Veo, Mistral and Azure Claude 4.5 deprecation dates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43857
- fix(cost_calculator): bill ultrafast prompts above 272k at the ultrafast long-context rates by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43764
- refactor(rust): centralize Python bridge execution wrappers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43871
- chore(cost-map): add openai gpt-image-2.5 batch prices from the pricing page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43869
- chore(cost-map): add fireworks priority prices for ember-1, nemotron and glm 5.3 us rows by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43811
- fix(proxy): attribute completed batch cost rows to /batches in daily activity by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43870
- fix(router): strip encrypted reasoning the pinned deployment cannot decrypt by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43781
- fix(cost_calculator): stop copying optional_params into response hidden params by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/43637
- feat(pricing): add vertex_ai gemini-3.8 flash tts rows by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43876
- fix(proxy): keep request-body credentials out of stored spend-log requests by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/43635
- fix(ui): right-align money and count columns across tables by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/37889
- feat(agents): enforce authoritative agent permissions by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/43721
- fix(proxy): strip caller credentials from websocket passthrough by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43855
- fix(ui): render access group MCP and agent selections as wrapping chips by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41228
- fix(responses): scan and mask top-level instructions with guardrails by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43629
- feat(traces): add Rust storage foundation by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/43819
- feat(ui): agent traces tab on logs with timeline and otel setup guide by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/43891
- feat(otel v2): excluded_services opt-out for datastore spans on tenant destinations by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43278
- fix(traces): correct ClickHouse rollup partitioning, dedupe keys, and retention changes by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43901
- fix(bedrock): keep applicable beta headers by @shrey-berri in https://github.com/BerriAI/litellm/pull/43829
- feat(agents): authenticate Entra identities and delegated requests by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/43722
- fix(hosted_vllm): keep reasoning_content on replayed assistant messages by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43599
- fix(proxy): delete large teams without per-member transaction fan-out by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42998
- feat(tracing): port OTLP ingestion to current trace foundation by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/43915
- feat(proxy): add native ROI calculator for gateway spend vs merged PRs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43669
- test(e2e): repair completion, SAIL, and spend-log fixtures by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43902
- test(s3_v2): pin async 5xx retry through the production AsyncHTTPHandler by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43080
- feat(ui): adopt the new LiteLLM logo and monogram by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43913
- fix(proxy): relay Azure passthrough body model groups through the router by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43896
- fix(proxy): register a UI-configured arize callback next to otel under OTel v2 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43906
- fix(transcription): honor base_url alias for Groq Whisper and report it as the api base by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43917
- feat(tracing): store spend in ClickHouse automatically by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/43928
- fix(packaging): keep wheel paths under Windows MAX_PATH for Store Python by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/43903
- feat(agents): add identity registration and dashboard controls by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/43723
- refactor(proxy): answer every team access check with TeamAccess.allows by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/43364
- test(bedrock): restore the AWS env after a failed live call in the auth tests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43921
- feat(lens): analyze agent activity with a separate worker by @moe-berri in
  https://github.com/BerriAI/litellm/pull/43889
- fix(router): bill service tiers at catalog rates for custom-priced deployments by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43890
- test(ci): refresh qualified retired OpenAI fixtures by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43938
- fix(anthropic): forward the dangerous-tool-use beta to Azure AI Foundry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43934
- test(proxy): scope user_api_key_auth overrides in proxy_server tests by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43952
- fix(wandb): set supports_vision true on GLM-5.3-Flash by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43951
- chore(cost-map): sync openrouter prices from the models API by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43950
- fix(grayswan): send request conversation and tool calls to post-call monitor by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43770
- fix(azure_storage): name Data Lake objects without base64 padding or slashes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43914
- fix(guardrails): treat an unknown straiker api_version as unset instead of skipping the guardrail by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43956
- chore(deps): bump gitpython and tornado, extend diskcache osv ignore to Nov 1 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43961
- fix(azure_storage): keep the DataLakeServiceClient alive until its TTL elapses by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43082
- feat(proxy): record in spend logs whether a request used a client-forwarded Anthropic OAuth token by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43063
- test(ci): repair stale tests and move retired OpenAI text-completion fixtures by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43958
- feat(e2e): record each e2e test's steps, starting with ProxyClient by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/42393
- feat(providers): add Cortecs as an OpenAI-compatible provider by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43872
- feat(ui): filter tags by name and description on the Tag Management page by @galovics in
  https://github.com/BerriAI/litellm/pull/42949
- fix(caching): write the response-cache SET to Redis at once instead of on the post-call batch by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43973
- test(e2e): typed per-test metadata for the e2e suite by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/42044
- feat(guardrails): honor litellm_params.timeout in every HTTP guardrail by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43134
- chore(cost-map): add fireworks inkling priority prices from the prices api by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/43949
- chore(cost-map): add deprecation date for anthropic claude-sonnet-4-5 by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43898
- fix(cost-map): raise baseten DeepSeek-V4.1-Flash max output to 262144 by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/43916
- fix(proxy): restore pre-config-wins handling of pass-through endpoints by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43962
- feat(lens): investigate sampled traces and retain batch results by @moe-berri in
  https://github.com/BerriAI/litellm/pull/43942
- fix(guardrails): scan Responses API input in Azure Prompt Shield by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43786
- fix(guardrails): scan Responses API input in Azure Text Moderation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43965
- refactor: clean up fresh tech debt from 2026-09-30 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43993
- test: inject the HIBP client and the MCP loop clock so two backend tests stop flaking by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44007
- fix(cost-map): reprice fireworks deepseek v4.1 flash to the 2026-10-01 pricing update by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44024
- test(anthropic): native /v1/messages reasoning integration tests built on a captured Claude Code request by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43361
- fix(bedrock): add beta header for thinking display updates by @shrey-berri in
  https://github.com/BerriAI/litellm/pull/43832
- fix(proxy): preserve decision request bodies under token limits by @shrey-berri in
  https://github.com/BerriAI/litellm/pull/43920
- test(proxy): migrate DB and Redis backed proxy tests into tests/integration by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43996
- feat(lens): track worker spend through virtual keys by @moe-berri in https://github.com/BerriAI/litellm/pull/43989
- test(proxy): move auth, hooks, policy_engine and client tests into tests/unit/proxy by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43998
- fix(ui): give model leaderboard a distinct trophy icon by @moe-berri in https://github.com/BerriAI/litellm/pull/44036
- test(ci): repair stale tests and flaky CI infrastructure by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43983
- test(proxy): move management_endpoints, management_helpers and guardrails tests into tests/unit/proxy by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44003
- feat(ui): agent traces open in a side drawer with a chat-style run view by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/43972
- feat(s3_v2): add s3_partition_granularity option for hourly S3 folders by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43748
- refactor(lens)!: rename internal engine code and API by @moe-berri in https://github.com/BerriAI/litellm/pull/44034
- test(proxy): move utils, agent_endpoints and endpoint tests into tests/unit/proxy by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44006
- test(proxy): move proxy_server, _experimental and db tests into tests/unit/proxy by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44012
- test(proxy): move middleware, spend_tracking, pass_through, common_utils and root proxy tests into tests/unit/proxy by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44015
- test(proxy): delete the legacy proxy test tree and shard tests/unit/proxy by glob by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44018
- chore(deps): bump pypdf from 6.16.2 to 6.19.0 by @dependabot[bot] in https://github.com/BerriAI/litellm/pull/44033
- chore(deps): drop unused pytest-postgresql dev dependency by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44056
- docs(proxy): point mcp_server test references at tests/unit/proxy by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44055
- feat(ui): show daily token totals on the model leaderboard by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44044
- chore(lint): remove the LIT002 mutable-construction rule by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43971
- feat(vertex-ai): add vertex_ai/xai/grok-4.7 pricing by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44059
- feat(ui): drop the Beta badge from the Cost Optimization nav item by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43967
- test(e2e): bill Sail windows that synchronous calls can still use by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44058
- ci(circleci): test Redis behavior against local Redis and print short tracebacks by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44062
- fix(router): keep silent_model out of embedding provider requests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44064
- fix(cost-map): add perplexity, openrouter, voyage and nebius models and fix registry metadata by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43907
- feat(tool-policies): show the user who owns the key that discovered a tool by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43892
- feat(proxy): gzip buffered responses for clients that accept it by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44052
- fix(auto-router): show actual and baseline spend for historical savings by @tin-berri in
  https://github.com/BerriAI/litellm/pull/44057
- refactor(proxy): inject tracing receiver and access context by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/44035
- feat: improve trace ingestion and trace details by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/43975
- fix(proxy): enforce key/team vector_stores allowlist on /v1/rag/query by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43953
- feat(lens): move traces and setup into Lens by @moe-berri in https://github.com/BerriAI/litellm/pull/44068
- test(proxy-extras): run the db push timeout hint test without a database URL by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44073
- fix(proxy-extras): build the SpendLogs indexes in the migration job instead of in migrations by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43948
- fix(mcp): resolve team-granted toolsets for non-admin keys and dashboard sessions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43908
- fix(bedrock): accept Converse messages with no content key by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43936
- feat: add litellm.agent() to run claude code, codex, opencode and deep agents through the ai gateway by @ishaan-berri
  in https://github.com/BerriAI/litellm/pull/43885
- feat(ui): add test trace, tracing key and otel endpoints to tracing setup by @ishaan-berri in
  https://github.com/BerriAI/litellm/pull/44090
- feat(proxy): add LITELLM_DISABLE_LAZY_ROUTES to register optional routers at startup by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43911
- test(e2e): keep 1ms-timeout deployments off the provider cache by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44082
- refactor(repositories): daily activity repository with centralized bounded usage queries by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43398
- fix(bedrock): add beta for mid-conversation tool changes by @shrey-berri in
  https://github.com/BerriAI/litellm/pull/43833
- feat(proxy): bounded daily activity routes (aggregated, search, model_top_keys, export, cache_leakage_keys) for all
  usage entities by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43408
- feat(ui): usage pages consume bounded daily activity routes instead of storing all keys client-side by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43409
- build(docker): drop the no-op PROXY_EXTRAS_SOURCE switch from the non-root image by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44097
- fix(proxy): persist SSO display name as user_alias on login by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44065
- fix(cost-map): restore later azure Models API retirement dates and date gpt-6.1-sol by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44072
- feat(lens): simplify setup and investigation workflow by @moe-berri in https://github.com/BerriAI/litellm/pull/44089
- chore(cost-map): sync openrouter prices from the models API by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/44105
- fix(providers): keep thinking display updates beta by @shrey-berri in https://github.com/BerriAI/litellm/pull/43969
- feat(rust): embed migration folders with a shared migrate! macro by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44104
- refactor(tracing): normalize agent spans in Rust by @yujonglee-berri in https://github.com/BerriAI/litellm/pull/44071
- perf(traces): recalculate ClickHouse TTL info only on retention changes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44117
- fix(proxy-extras): bound the lock waits of the partitioned SpendLogs index build by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44109
- build(deps): bump oauthlib to 4.0.0 to clear osv-scan by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43899
- fix(ui): label lens trace services as agents by @ishaan-berri in https://github.com/BerriAI/litellm/pull/44116
- fix(ui): split the KeyActivityPanel condition chains to bring the lint budget back under its ceiling by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44114
- chore: bump litellm-enterprise 0.1.72 -> 0.1.73, litellm-proxy-extras 0.4.103 -> 0.4.104 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44126
- feat(mcp): add Microsoft 365 (Graph) server to the MCP catalog by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43099
- chore(cost-map): add azure_ai deprecation dates from the Azure retired models page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44142
- fix(daily_activity): keep NULL entity ids when excluding entity ids by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44139
- fix(proxy): reject non-canonical daily activity dates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44143
- fix(proxy): always exit when database setup fails at boot by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44141
- feat(tracing): add scoped SQL queries and schema-aware help by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/44085
- fix(guardrails): straiker v3 routes sk_agt_ keys to v3 and fails closed on a missing verdict by @PhimmStraiker in
  https://github.com/BerriAI/litellm/pull/44011
- test(integration): move legacy proxy, router and Redis tests into tests/integration by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44128
- chore(cost-map): take azure_ai claude-sonnet-4-5 retirement date from the Azure schedule by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/44145
- fix(azure_storage): keep client call ids from sharing one Data Lake file by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44099
- fix(guardrails): restore Azure guardrail get_user_prompt dispatch and allow logging by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44067
- fix(proxy): keep tool payloads and logprobs unmasked in stored spend logs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44075
- test(e2e): move live-provider legacy tests into tests/e2e by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44120
- chore(harness): remove banner comments, restating comments and dead in_loop_thread by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44161
- test(straiker): assert a saved api_version v1 with an sk_agt_ key routes to v3 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44153
- refactor(types): replace Any with proven types in 7 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43844
- chore(release): backport #44066 to rc/1.105.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/44215
- fix(proxy-extras): backport #44203 to rc/1.105.0 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44220
- fix(ui): leave unset callback select params out of the save payload (backport #44213 to rc/1.105.0) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44223
- chore: bump litellm-proxy-extras 0.4.104 -> 0.4.105 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44235
- fix(ui): shrink the sidebar logo so it stops outweighing page titles (backport #44247 to rc/1.105.0) by @yuneng-berri
  in https://github.com/BerriAI/litellm/pull/44251
- test: repair stale and polluting tests red on scheduled main CI (#44229) [rc/1.105.0] by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44254
- test(integration): opt the config pass-through spend-log case into auth (rc/1.105.0 backport of #44265) by
  @yuneng-berri in https://github.com/BerriAI/litellm/pull/44269
- test: fix three order-dependent and timing-flaky tests (rc/1.105.0 backport of #44271) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44281
- fix(proxy-extras): retry P3009 when a peer already recovered the named migration row (rc/1.105.0 backport of #44283)
  by @yuneng-berri in https://github.com/BerriAI/litellm/pull/44308
- fix(bedrock): backport #44307 to rc/1.105.0 by @mateo-berri in https://github.com/BerriAI/litellm/pull/44317
- fix(otel): tolerate non-dict callback_settings.otel and ignore bare EXCLUDED_SERVICES env (backport #44086 to
  rc/1.105.0) by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44241
- chore(ui): rebuild the Admin UI bundle on rc/1.105.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/44386
- chore(deps): refresh locked dependencies on rc/1.105.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44803
- chore(docker): bump pgbouncer to 1.26.0 by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45013
- feat(decisions): backport /v1/systemone, OpenAI-format /v1/decisions and the openai Decisions provider to rc/1.105.0
  (#44236, #45184, #45214) by @mateo-berri in https://github.com/BerriAI/litellm/pull/45189
- feat(guardrails): backport the decision model guardrail to rc/1.105.0 (#45663) by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/45894
- feat(decisions): backport the decisions and Jev follow-ups to rc/1.105.0 without the playground by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/45905
- feat(ui): backport decision auto-router setup to 1.105 by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/45915
- chore: rebuild Admin UI bundle for rc/1.105.0 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/45927

## New Contributors

- @daqiangganjun made their first contribution in https://github.com/BerriAI/litellm/pull/38172
- @4refael made their first contribution in https://github.com/BerriAI/litellm/pull/41826
- @shrey-berri made their first contribution in https://github.com/BerriAI/litellm/pull/43221
- @agustin18 made their first contribution in https://github.com/BerriAI/litellm/pull/43319
- @shoemoney made their first contribution in https://github.com/BerriAI/litellm/pull/38049
- @YaseenBashaT made their first contribution in https://github.com/BerriAI/litellm/pull/43197
- @stewartpark made their first contribution in https://github.com/BerriAI/litellm/pull/43147
- @hsm207 made their first contribution in https://github.com/BerriAI/litellm/pull/43536
- @DeviaVir made their first contribution in https://github.com/BerriAI/litellm/pull/43558
- @Flexomatic81 made their first contribution in https://github.com/BerriAI/litellm/pull/43588
- @fedaeho made their first contribution in https://github.com/BerriAI/litellm/pull/43512
- @galovics made their first contribution in https://github.com/BerriAI/litellm/pull/42949

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.104.0...v1.105.0

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
  ghcr.io/berriai/litellm:v1.104.2
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.104.2/cosign.pub \
  ghcr.io/berriai/litellm:v1.104.2
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

## What's Changed

- feat(decisions): backport /v1/systemone, OpenAI-format /v1/decisions and the OpenAI Decisions provider to
  stable/1.104.x for v1.104.2 (#44236, #45184, #45214) by @mateo-berri in https://github.com/BerriAI/litellm/pull/45190

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.104.1...v1.104.2

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
  ghcr.io/berriai/litellm:v1.104.0
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.104.0/cosign.pub \
  ghcr.io/berriai/litellm:v1.104.0
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

## What's Changed

- build(deps): re-suppress GHSA-h7x2-h6g9-p789 in osv-scan, mlflow still has no fixed release by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41036
- feat(auth): add breached password detection to password policy by @ojensen-berri in
  https://github.com/BerriAI/litellm/pull/39321
- feat(auth): add self-service password change and plug plaintext password leaks by @ojensen-berri in
  https://github.com/BerriAI/litellm/pull/39562
- feat(auth): force password reset for breached or admin-set passwords by @ojensen-berri in
  https://github.com/BerriAI/litellm/pull/40107
- perf(proxy): serialize /model/info listing once with orjson by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41061
- fix(utils): stop wrapper_async submitting the sync success handler twice by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41058
- test(integration): native responses and messages cost cases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42010
- fix(proxy): stop re-sending un-resendable spend batches from the Redis buffer by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41994
- fix(router): skip cooldown for background response cost poll 404s by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42046
- fix(router): stamp model_group when retrieving a batch, so batch tokens are attributable (internal copy of #38499) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42062
- test(mcp): restore scoped execution and credential isolation regressions by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/42050
- feat(proxy)!: refuse to start with an unset, empty, or publicly known master key by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/42019
- docs: stop advertising sk-1234 as the master key in shipped configs and examples by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/42011
- test(logging): add autorouter estimate keys to the GCS pub/sub spend-log golden by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42061
- fix(router): add NotFoundErrorRetries so a retry policy can pin 404 retries by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42045
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42077
- fix(google_genai): forward response schema and tool parameters through the generateContent adapter by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42067
- test(e2e): restore MCP OAuth happy-path coverage (LIT-3467) by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/42051
- fix(mcp): tools/call no longer 404s on a worker that has not served tools/list by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42072
- chore(prices): sync OpenRouter prices: 7 models, 6 deprecated by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42082
- fix(proxy): wait for the spend-log table before creating startup views by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41974
- fix(guardrails): scan each choice's tool-call arguments apart on n>1 streams and log why a rewrite was discarded by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/40986
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42089
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42092
- chore: remove the dead telemetry flag from the SDK, proxy CLI and configs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42071
- docs(tests): define the tier contract for unit, integration and e2e by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42099
- fix(proxy): coordinate v2 migration startup and qualify container recovery by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/40932
- ci(tests): wire tests/unit into CircleCI and keep draining GHA shards green by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42103
- test(unit): block external sockets at import time and add a socket policy regression test by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42113
- fix(ci): excuse retired test-quality rules in the budget ratchet by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42116
- test: migrate wave 1 phase 2 legacy unit tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42108
- test(llms): migrate bedrock, baseten and base_llm batch tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42110
- test(llms): migrate phase 6 provider unit tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42107
- test: migrate nvidia, oci, ocr, oobabooga and openai legacy tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42115
- test: migrate phase 9 legacy llm provider tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42117
- test(llms): migrate phase 7 provider unit tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42114
- test: migrate wave 1 phase 8 legacy llm tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42112
- test(llms): migrate phase 5 provider unit tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42109
- refactor(types): replace Any with proven types in 30 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42127
- test(unit): make every tests/unit directory a package so pytest collection is unique by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42135
- test(unit): migrate wave 1 phase 3 anthropic, apiserpent, azure and azure_ai legacy tests by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42118
- test: migrate openai, openai_like and openrouter legacy tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42128
- test: migrate phase 14 wave 2 provider tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42132
- test: migrate phase 16 legacy tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42131
- test: migrate wave 1 phase 1 legacy tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42123
- test: migrate phase 12 legacy llm provider tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42137
- test: migrate phase 15 legacy tests to tests/unit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42136
- fix(proxy): enforce virtual key budgets for JEV test routing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41879
- feat(fal_ai): add Seedance 2.5 / 2.0 video generation via fal queue API by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41980
- chore(prices): sync OpenRouter prices: 11 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42096
- test: migrate legacy provider tests to tests/unit (wave 2, phase 13) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42145
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42154
- chore(prices): sync OpenRouter prices: 5 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42155
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42157
- fix(auth): reject deactivated JWT users and refresh cached status by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/42064
- fix(mcp): explain missing public client dependencies by @joshua-berri in https://github.com/BerriAI/litellm/pull/42148
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42162
- chore(prices): sync OpenRouter prices: 3 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42163
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42164
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42166
- chore(prices): sync OpenRouter prices: 3 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42168
- refactor(rust): split token counter backends by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42165
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42169
- chore(prices): sync OpenRouter prices: 3 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42175
- chore(prices): sync OpenRouter prices: 4 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42178
- chore(prices): sync OpenRouter prices: 3 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42179
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42182
- feat(rust): add typed secret managers and shared auth adapters by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42173
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42184
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42187
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42192
- fix(responses): forward safety_identifier through the chat completion bridge by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42193
- refactor(types): replace Any with proven types in 32 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42220
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42227
- fix(helm): render a fixed replicaCount on componentized deployments when HPA is disabled by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42207
- fix(proxy): return 422 instead of 429 for BudgetExceededError by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42097
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42234
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42240
- chore(prices): sync OpenRouter prices: 4 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42243
- fix(a2a): send message/stream for Bedrock AgentCore streaming requests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42239
- fix(registry): add MAI-Image-2.5-Pro pricing, fix Fireworks/Together entries, absorb verified open registry PRs, add
  Groq deprecation and Bedrock regional Qwen3 Next pricing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/34941
- fix(anthropic): forward safeguards and anthropic-beta unchanged on native /v1/messages by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42152
- chore(prices): sync OpenRouter prices: 4 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42246
- chore(prices): sync OpenRouter prices: 3 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42251
- chore(prices): sync Azure prices: 1 model, 1 deprecated by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42249
- chore(prices): sync AWS Bedrock prices: 25 models [enrichment failed: AWS Bedrock, 66 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42250
- test(a2a): migrate a2a_protocol legacy tests to tests/unit (wave 3 phase 17) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42160
- feat(proxy): default to the v2 migration resolver by @yuneng-berri in https://github.com/BerriAI/litellm/pull/42105
- feat(auto-router): configure heuristic v2 success threshold by @tin-berri in
  https://github.com/BerriAI/litellm/pull/42252
- chore(prices): sync Together AI prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42258
- chore(prices): sync OpenRouter prices: 6 models, 1 new by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42253
- fix(key_generate): use the user's own budget as the ceiling for UI session personal keys by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41588
- feat(team): show whether a member follows the team default budget and allow resetting to it by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41906
- chore(prices): sync AWS Bedrock prices: 13 models, 1 new [1 with gaps, enrichment failed: AWS Bedrock, 38 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42254
- chore(prices): sync OpenRouter prices: 7 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42261
- feat(proxy): add GET /utils/model_info to look up cost map info for unregistered models by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42121
- chore(prices): sync OpenRouter prices: 4 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42265
- feat(xai): add grok-4.7 to the cost map by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42264
- ci(e2e): fix the stage-mirror batch reds and keep a redacted pytest log by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42143
- chore(prices): sync AWS Bedrock prices: 3 models [enrichment failed: AWS Bedrock, 32 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42269
- chore(prices): sync OpenRouter prices: 6 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42270
- feat(fal_ai): add gpt-image-2.5 flare/sunburst, flux/dev and image edits by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42095
- feat(bedrock): add us.moonshotai.kimi-k3 pricing and fill the global Kimi K3 entry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42271
- test(google): boot the unified Google proxy fixture with a real master key by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42120
- feat(auto-router): add JEV classifier alongside LLM classifier by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41886
- fix(proxy): park requeued spend logs in Redis so they survive a pod restart during a DB outage by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42022
- fix(bedrock): forward anthropic-beta headers verbatim on the Claude platform messages path by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42275
- chore(prices): sync AWS Bedrock prices: 4 models [enrichment failed: AWS Bedrock, 26 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42279
- chore(prices): sync OpenRouter prices: 3 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42280
- fix(azure_ai): bridge gpt-5.4+ function tools with reasoning to the Foundry Responses API by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42041
- fix: apply configured cache_control_injection_points beside client cache_control marks by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41956
- fix(token_counter): count replayed redacted_thinking blocks so prompt_caching keeps pinning by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42069
- fix(mcp): paginate prompt and resource discovery by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39189
- chore(prices): sync AWS Bedrock prices: 3 models [enrichment failed: AWS Bedrock, 18 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42290
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42289
- fix(router): keep prompt caching affinity when the breakpoint moves by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42080
- feat(ui): show prompt caching requests and net savings by @tin-berri in https://github.com/BerriAI/litellm/pull/42055
- feat(bedrock_mantle): serve /v1/messages for Claude models on Mantle's native Anthropic Messages API by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42049
- feat(policy_engine): add default fallback policy attachments by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42119
- fix(mcp): handle split UTF-8 routing previews by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/34919
- fix(bedrock): send s3BucketOwner on batch input and output data config by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42262
- feat(rust): scaffold cache foundation for Python parity by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42196
- fix(fal_ai): price images from the dimensions fal returns by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42282
- chore(prices): sync AWS Bedrock prices: 1 model [enrichment failed: AWS Bedrock, 16 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42298
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42297
- feat(fal_ai): add MiniMax H3 text-to-video and reference-to-video by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42286
- fix(ci): let the install smoke test boot its key-less proxy config by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42296
- fix: rename the mainland China brand to Qianwen AI Platform by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42284
- test(integration): endpoint, breakdown component and failure support in the cost harness by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41999
- test(integration): embeddings, rerank, completions and moderations cost cases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42020
- chore(prices): sync OpenRouter prices: 4 models, 3 new by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42305
- test(integration): audio, image and per-unit cost cases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42024
- feat(ui): add upgrade banner with latest release changelog stats by @kerry-berri in
  https://github.com/BerriAI/litellm/pull/40429
- fix(fal_ai): surface fal errors in video status and content instead of completed and generic 500 by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42306
- test(integration): passthrough route cost cases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42028
- fix(proxy): detach stored credential when model editor selects None by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42291
- fix(proxy): renew budget reservation counter TTL while the request is in flight by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40322
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42320
- test(integration): pricing dimension and provider reported cost cases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42035
- fix(anthropic): forward Claude Code safeguards and dangerous-tool-use beta to Bedrock Invoke and Vertex on
  /v1/messages by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42288
- feat(edenai): add Eden AI provider across chat, Responses, Messages, embeddings, audio, images and video by @hMED22 in
  https://github.com/BerriAI/litellm/pull/41101
- feat(rust-cache): serve RedisClusterCache natively as a Redis topology by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42317
- test(integration): provider wire cost cases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42052
- test(e2e): replace custom endpoints_client with provider SDK clients by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/34358
- fix(mcp): keep oauth scopes in admin api credential redaction by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39805
- fix(otel v2): map OCR page markdown onto the generation output by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42267
- test(integration): proxy behaviour cost cases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42060
- chore(prices): sync OpenRouter prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42333
- test(integration): batch and realtime cost cases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42066
- fix(proxy): keep config-defined deployments when a config read returns no model_list by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41505
- feat(rust): add CyberArk Conjur secret manager backend by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42303
- fix(rust): preserve Python settings semantics at the native boundary by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42300
- fix(alerting): deliver every distinct alert queued in one flush window by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42314
- fix(bedrock): keep batch S3 credentials out of chat requests and debug logs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42312
- fix(proxy): evict the cached user row when SCIM or /user/delete removes a user by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42315
- fix(auth): fail closed when the team membership lookup hits a db outage by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42036
- test(migrations): cover the release-to-release upgrade path by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42294
- feat(rust): add Azure Key Vault secret manager backend by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42309
- feat(rust): native Azure Blob response cache backend by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42321
- chore(prices): sync AWS Bedrock prices: 6 models [enrichment failed: AWS Bedrock, 4 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42338
- chore(prices): sync OpenRouter prices: 3 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42337
- refactor(types): remove 1,173 Any errors across 169 backend files by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/40251
- fix(responses): stream one lifecycle across MCP auto-execute rounds by @Atharva-Kanherkar in
  https://github.com/BerriAI/litellm/pull/40121
- fix(responses): stop agentic follow-up from passing request params twice by @chopratejas in
  https://github.com/BerriAI/litellm/pull/41560
- fix(streaming): keep an explicit provider prompt_tokens=0 or completion_tokens=0 in streamed usage by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42323
- fix(router): walk every entry of a fallback list after a mid-stream failure by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42283
- refactor(mcp): extract explicit operation context and dispatch by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/42292
- test: fix stale budget-status and bad-database-url assertions by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42339
- chore(prices): sync OpenRouter prices: 3 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42349
- fix(responses): patch custom_tool_call_output in place on guardrail write-back by @chopratejas in
  https://github.com/BerriAI/litellm/pull/41561
- feat(rust): add native disk cache backend by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42311
- feat(auth): breached password detection, self-service change-password and forced password reset by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42278
- feat(docker): add a quickstart compose file served from the product repo by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42326
- fix(xai): accept max_completion_tokens as a supported param by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42353
- feat(rust): add native GCS object-store cache backend by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42325
- feat(rust): add HashiCorp Vault secret manager crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42308
- fix(proxy): apply DB-stored callback redaction settings before logger init by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42122
- fix(mcp): keep server lists stable across refreshes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41074
- chore(prices): sync OpenRouter prices: 4 models, 3 deprecated by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42357
- feat(rust): add native S3 cache backend by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42313
- feat(xiaomi_mimo): add mimo-v2.6-pro and mimo-v2.6-flash cost map rows with live e2e coverage by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42362
- fix(bedrock): add bare moonshotai.kimi-k3 cost map entry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42363
- feat(cache): add native Valkey semantic cache backend by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42316
- fix(logging_worker): make flush() survive an event loop change by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42355
- fix(auth): let jwt team_allowed_routes paths grant auth=true passthrough by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/42346
- fix(rust): declare _CacheTestHandle.valkey_semantic in native stub by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42364
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42365
- feat(ui): add internal-user savings and auto-router usage by @tin-berri in
  https://github.com/BerriAI/litellm/pull/42026
- test(model_management): cover actor edges and wildcard models by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41769
- feat(ui): expose remaining complexity router advanced settings by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42293
- test(ui): cover dashboard form journeys by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41773
- test(router): cover legacy lowest TPM selection by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41795
- feat(proxy): report the source of alerting, UI and router settings on read by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41788
- fix(proxy): record aborted outcome when spend-log cleanup is cancelled at shutdown by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/41213
- fix(router): make context-window escalation opt-in by @tin-berri in https://github.com/BerriAI/litellm/pull/41872
- feat(cache): serve Redis Semantic caches natively in Rust by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42319
- fix(cli): preserve newer installed status lines during setup by @tin-berri in
  https://github.com/BerriAI/litellm/pull/42356
- chore(prices): sync OpenRouter prices: 4 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42371
- feat(agents): attach access groups to agents and enforce them for models, MCP servers and agent calls by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41634
- fix(guardrails): run key-attached guardrails on /v1/videos by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42354
- fix(azure): propagate asyncio.CancelledError instead of raising a 500 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42295
- test(e2e): cover chat and responses registry gaps by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41794
- feat(cache): serve QdrantSemanticCache natively from Rust by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42324
- chore(prices): sync OpenRouter prices: 4 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42377
- feat(ui): show Capability and FUSE v2 routing forecasts by @tin-berri in https://github.com/BerriAI/litellm/pull/42057
- fix(cache): keep native Redis semantic binding and Qdrant batch writes after merge by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42379
- feat(ui): add per-user breakdown to team usage export by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42367
- feat(jwt-key-mapping): accept token_id as an alternative to the plaintext key by @Louis-Vauterin in
  https://github.com/BerriAI/litellm/pull/39578
- fix(openrouter): remove the retired stealth/union-alpha model from the cost map by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42386
- feat(pricing): add xai grok-4.20 aliases and image token prices from /v1/language-models by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42384
- test(proxy): isolate the agent read-through singleton between unknown-agent tests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42389
- fix(mcp): return camelCase tool keys from /v1/mcp/tools after the SDK 2 upgrade by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42352
- fix(logging): price terminal Responses stream events from their inner response by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42385
- fix(bedrock): send every Mantle beta in the anthropic-beta header on the bedrock/mantle route by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42376
- fix(bedrock): sign batch S3 requests with s3_access_key_id and s3_secret_access_key by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42342
- feat(fal_ai): add flux-lora-depth image edits and moondream3 chat completions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42334
- feat(proxy): opt-in litellm_call_id in JSON error bodies by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42391
- fix(fal_ai): price non-canonical image sizes from the nearest row and honour dump options by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42336
- fix(proxy): drop cost-map metadata echoed back on model save by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41944
- feat(openrouter): price typesafe/jev-1.13 and add an openrouter decisions pass-through by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42301
- feat(cost): warn and count $0 cost on billable requests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42345
- fix(proxy): release unclaimed budget reservations at request end by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42304
- test(integration): move Xiaomi MiMo coverage from live e2e to the providers wire shard by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42395
- feat(fal_ai): add queue-only /fal_ai pass-through route with spend tracking by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42360
- fix(auth): fail closed when the JWT single-team fallback or compact editor membership read hits a DB outage by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42344
- refactor(agentic-loop): build follow-up kwargs in one place so no executor can repeat a request param by
  @ryan-crabbe-berri in https://github.com/BerriAI/litellm/pull/42307
- fix(responses): drop client_metadata and merge system messages for Databricks chat-only models by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42390
- test(e2e-ui): check the MCP Tools tab against the upstream's own tools/list by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42397
- test(integration): chain a proxy-issued previous_response_id in the cost suite by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42396
- feat(rust-bridge): add cache and secret migration foundations by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42328
- fix(proxy): surface a database outage from the user read as 503 no_db_connection by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42399
- test(pricing): assert cache-priced vertex grok rows advertise supports_prompt_caching by @kumarpriyanshu09 in
  https://github.com/BerriAI/litellm/pull/41526
- fix(bedrock): price bedrock/mantle/<model> deployments from the base model row by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42402
- fix(anthropic_adapter): keep reasoning_effort a string for targets that stay on chat completions by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42401
- chore(prices): sync OpenRouter prices: 2 models, 2 deprecated by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42381
- feat(proxy): add TinyFish Agent API passthrough with per-step billing by @Zechereh in
  https://github.com/BerriAI/litellm/pull/41099
- chore(prices): sync OpenRouter prices: 2 models, 2 new by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42407
- ci: skip cost map file checks on PRs that leave the cost map untouched by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42406
- feat(tokenizer): preserve Python defaults with opt-in Rust dispatch by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42174
- fix(presidio): mask PII in streaming /v1/messages output by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42351
- fix(otel v2): map completions, images, speech, transcription and moderation output onto the Langfuse generation output
  by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42394
- fix(cost): honor per-second custom pricing on chat completions for every provider by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42403
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42418
- feat(errors): prefilled GitHub issue link on unmapped internal errors by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42065
- test(e2e): add conversational matrix across chat, messages and responses by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42359
- fix(proxy): answer 503 no_db_connection on management routes when the caller's user read hits a database outage by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42410
- fix(e2e-stack): print add-mask lines only under GitHub Actions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42423
- feat(errors): add stream and safe config flags to the bug report link by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/42428
- feat(router): native compact-to-fit across conversation APIs by @tin-berri in
  https://github.com/BerriAI/litellm/pull/42074
- fix(mcp): keep config-defined servers read-only by @joshua-berri in https://github.com/BerriAI/litellm/pull/42299
- ci(code-quality): allowlist _render_json in the recursive detector by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42442
- fix(guardrails): store the masked output in spend logs when Presidio masks the response by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42441
- fix(jwt): accept a team alias in x-litellm-team-id by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42445
- chore(prices): sync OpenRouter prices: 14 models, 1 deprecated [enrichment failed: OpenRouter, 5 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42438
- feat(rust): align secret manager operation contexts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42480
- chore(prices): sync OpenRouter prices: 1 model [enrichment failed: OpenRouter, 5 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42485
- feat(arize): per-team success and error sampling rates for the Arize AX callback by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42383
- test(unit): make bedrock collector and secret scan timing tests deterministic by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42405
- feat(anthropic): add Claude Opus 5.5 by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42489
- fix(gemini): simplify model version check by @philschmid in https://github.com/BerriAI/litellm/pull/42465
- fix(bedrock/claude_platform): strip body params the AWS endpoint rejects by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/31203
- fix(proxy): never render credential-bearing config keys in the bug report by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42493
- fix(cost): bill batch prompts above 272K at OpenAI's long-context batch tier by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39861
- fix(otel v2): map rerank and search output and the OCR, image edit and search input onto the Langfuse generation by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42444
- test(response_metadata): make the detailed-timing receive-anchor test timezone independent by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42429
- fix(utils): stop a nested additional_drop_params entry from crashing openai-compatible calls by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42492
- fix(jwt): say x-litellm-team-id matched no team id or alias in the 403 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42495
- fix(ui): surface the owner's user budget on keys without their own budget by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38220
- test(proxy): give every ui settings endpoint test a fresh settings store by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42430
- chore(prices): sync Azure prices: 34 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42502
- chore(prices): sync OpenAI prices: 25 models [enrichment failed: OpenAI, 32 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42501
- feat(router): time-windowed team reservation of deployments via model_info.access_windows by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42398
- feat(terraform): expose server_metadata on litellm_key so undeclared metadata is visible by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42453
- fix(mcp): restore legacy SSE and bounded cancellation cleanup by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/42382
- chore(prices): sync Google Gemini prices: 13 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42500
- fix(realtime): surface an upstream handshake refusal as an error event and policy close by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42388
- feat(openai): add GPT-6 Sol and GPT-6 Luna by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42515
- fix(router): explain fallback outcome in plain words in the raised error by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42509
- fix(cost): honor deployment pricing for image generation by @patel-26meet in
  https://github.com/BerriAI/litellm/pull/39311
- fix(streaming): let a later usage event zero out stale cache counts (#40736) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42330
- fix(fal_ai): handle seconds=auto and oversized sizes for minimax h3 videos by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42504
- fix(proxy): write key deleted audit logs for cascade and alias key deletions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42446
- fix(rust_bridge): keep Messages, token counter and tokenizer routes on Python by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42517
- chore(pricing): remove retired models flagged by the provider sync by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42521
- feat(proxy): admin-only /debug/report sharing the bug report environment by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42440
- fix(aws_secret_manager_v2): restore secret scheduled for deletion instead of failing CreateSecret by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42454
- feat(rust): add python-compat crate for Python data formats by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42510
- fix(langsmith): json.dumps with default=str so non-serializable metadata does not crash batch flush by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42424
- fix(proxy): make the lazy OpenAPI snapshot byte-identical on every Python version by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42519
- test(rust_bridge): drop route dispatch assertions, test the bridge directly by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42536
- fix(websearch_interception): keep intercepted searches under the parent request's session and trace by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41711
- test(e2e): assert a cooldown reaches a sibling replica within the 1s Redis read interval by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42422
- feat(proxy): opt-in include_guardrail_response returns guardrail_information in the response by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42327
- feat(logs): add span type filter to request logs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42491
- fix(e2e): route credential, cost map, and UI login calls to the control plane by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42506
- test(google_genai): move unified_google_tests to gemini-3.5-flash-lite by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42520
- feat(router): add group-scoped priority routing strategy by @tin-berri in
  https://github.com/BerriAI/litellm/pull/42378
- fix(fal_ai): align /fal_ai queue gate with the pricer and normalise resolution type by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42505
- fix(fal_ai): reuse the status client and headers on the video result probe by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42511
- refactor(rust): align the cache crates with Python and wire every native backend by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42530
- fix(fal_ai): honour global api_base for image generation and reject non-string reasoning_effort with 400 by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42512
- fix(ui): rename reminder markers to Ignore Custom Tags by @tin-berri in https://github.com/BerriAI/litellm/pull/42370
- chore(prices): sync Baseten prices: 12 models, 9 new [enrichment failed: Baseten, 15 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42558
- fix: enforce disable_custom_api_keys from general_settings by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42437
- feat: add configurable provider affinity header mapping by @togear in https://github.com/BerriAI/litellm/pull/41033
- fix(proxy): share model rate-limit buckets between a model_group_alias and its target by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42516
- test(e2e): one request lands the same spend on every surface by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42540
- fix(mcp): apply post-call rewrites without stale structured output by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41530
- chore(prices): sync Baseten prices: 4 models, 4 new [enrichment failed: Baseten, 3 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42578
- fix(otel): honor SSL_CERT_FILE and ssl_verify in OTLP HTTP exporters by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42106
- chore(prices): sync OpenAI prices: 3 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42557
- fix(ssrf): point the blocked-address remediation at litellm_settings by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42508
- fix(model_prices): registry audit 2026-09-22, absorb open pricing PRs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42543
- fix(gateway): expose /api/event_logging/batch on the gateway allowlist by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42572
- fix(proxy): honor DATABASE_DISABLE_PREPARED_STATEMENTS in the litellm CLI by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42556
- chore(prices): sync Vertex AI prices: 20 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42577
- fix(proxy): attribute provider and model_info on pre_call_hook rejections by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41077
- chore(cost-map): remove models past their deprecation date by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42435
- test(vcr): guard leaked cassette patches and make injected-transport embedding tests immune by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42542
- fix(otel): keep text completion choice fields beside the synthesized message by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42537
- fix(mcp): preserve discovery attribution and sanitize logging headers by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/42541
- fix(proxy_cli): import proxy_server once on script-style boot by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42584
- feat(bedrock): add Claude Opus 5.5 pricing and capabilities by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42588
- test(e2e): hold every worker under an idle RSS budget before any traffic by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42552
- feat(cost-map): add Claude Opus 5.5 for Vertex AI and Azure AI by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42599
- feat(proxy): configurable key_alias_pattern for key generate, update, and regenerate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42553
- test(proxy): make two proxy-infra tests independent of sibling-test state by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42581
- test: count a zombie grandchild as gone in the migrate deploy timeout test by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42570
- test(e2e): run the memory cell alone on the shared stack by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42518
- fix(caching): keep embedding cache hits aligned with request inputs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42571
- chore(prices): sync xAI prices: 3 models, 3 new [3 with gaps] by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42591
- fix(otel): record the GenAI exception event through the Logs API on both OpenTelemetry lines by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42431
- fix(spend): return 400 from /spend/calculate for a model with no pricing row by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42497
- fix(anthropic): return 400 instead of 500 when a content list holds a bare string by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42420
- feat(rust): add standalone cost calculator by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42604
- feat(logging): add normalized_error cluster key to error_information by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41715
- test(bedrock): point unit tests at model ids still in the cost map by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42606
- feat(rust): add immutable model catalog crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42605
- fix(ui): let the Create Key user picker find users by user_id, not just email by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41687
- test(cost_calculator): point image-generation deployment price test at a live gemini row by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42615
- test(utils): accept the per-size image cost keys in the price-map schema check by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42612
- fix(ollama): send PNG and JPEG images without requiring Pillow. by @Pawan-Shahane in
  https://github.com/BerriAI/litellm/pull/41979
- fix: answer get_api_base for github_copilot and chatgpt without running the login flow by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42602
- test: point CircleCI-only suites at models still in the cost map by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42617
- fix: drop duplicate cache_read_input_token_cost_batches keys from the price maps by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42623
- fix(s3): replace colons in generated log filenames by @mubashir1osmani in
  https://github.com/BerriAI/litellm/pull/40452
- test(realtime): drop legacy InvalidStatusCode tests and pin websockets imports by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42624
- fix(bedrock): treat blank AWS_S3_* env vars as unset for batch jobs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42528
- ci(test-unit): drop dead misc shard paths and skip missing paths with a warning by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42603
- fix(proxy): keep the in-flight daily spend batch when shutdown cancels the flush by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42593
- fix(utils): isolate callback errors in async_post_call_success_deployment_hook by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42535
- test(e2e): add secret manager lanes for HashiCorp Vault and CyberArk Conjur by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/42503
- feat(ui): simplify auto-router setup and clarify feature limits by @moe-berri in
  https://github.com/BerriAI/litellm/pull/42625
- feat(ui): add native LiteAdmin assistant by @tin-berri in https://github.com/BerriAI/litellm/pull/42443
- fix(mcp): preserve credential authority in DCR bridge authentication by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42563
- feat(ci): close open pull requests superseded by a merged fix on their linked issue by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42609
- test(cost): repoint the Azure image cost test at gpt-image-2 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42631
- feat(logger): dispatch Python logging through the Rust diagnostics processor by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42616
- fix(bedrock): drop unsupported sampling params on converse reasoning models by @emerzon in
  https://github.com/BerriAI/litellm/pull/39834
- test(utils): raise the post-success hook error from a guardrail in the failure-hook regression by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42646
- chore(docker): bump wolfi-base digest to pick up glibc 2.44-r6 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42643
- chore: bump litellm-enterprise 0.1.69 -> 0.1.70, litellm-proxy-extras 0.4.100 -> 0.4.101, litellm 1.103.0 -> 1.104.0
  by @yuneng-berri in https://github.com/BerriAI/litellm/pull/42633
- fix: repair seven regressions caught by CircleCI on main by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42640
- chore(e2e): move the compat-matrix populator from a GCE VM to a Render cron job by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42608
- chore(prices): sync Google Gemini prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42642
- chore(prices): sync OpenAI prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42648
- fix(bedrock): stream /v1/messages Invoke bytes through instead of holding them in a 1024-byte chunker by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42607
- fix(bedrock): send json_schema as a forced tool on Claude Opus 4.7 and 4.8 Converse by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42644
- test(e2e): tolerate provider-side flakes on five full-suite cells by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42628
- chore(prices): sync AWS Bedrock prices and sources from the AWS price list by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/42632
- fix(pricing): drop the unpublished cached rate from the Gemini Live preview entries by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42651
- test(integration): regression tests for August provider translation and streaming bugs by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42621
- fix(vector_stores): keep config-defined vector stores listed and read-only by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42574
- test(integration): regression tests for August cost tracking and budgeting bugs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42622
- chore(prices): sync Vertex AI prices: 2 models, 2 new [enrichment failed: Vertex AI, 224 held] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/42589
- fix(pricing): align bedrock_mantle/openai.gpt-daybreak-blue-5.6-sol with its Bedrock model card by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42672
- chore(prices): sync AWS Bedrock prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42673
- chore(prices): sync AWS Bedrock prices: 11 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42677
- fix(prices): align regional Bedrock Mistral Large 24.02 keys with the AWS pricing page by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42684
- chore(prices): sync AWS Bedrock prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42685
- test(integration): allow skipped nodes and drop the shard cap by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42687
- chore(prices): sync Vertex AI prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42680
- fix(policy_engine): keep inherited parent guardrails when a child policy condition misses by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42548
- fix(proxy): publish auth cache invalidations in the background so a wedged coordination Redis cannot stall user
  updates by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42534
- feat(otel): emit gen_ai.conversation.id from the caller's session id on v2 LLM spans by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42486
- ci: remove the unused create-release workflow by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42696
- fix(proxy): revoke UI session tokens on logout and password change by @ojensen-berri in
  https://github.com/BerriAI/litellm/pull/42463
- refactor(types): replace Any with proven types in 5 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42722
- chore(prices): sync OpenRouter prices: 19 models, 9 new [18 held] by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42592
- fix(model_prices): add azure_ai gpt-image-2 and groq llama-guard-3-8b deprecation dates by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42738
- fix(proxy): validate model credential name only when it changes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42701
- feat(models): add openrouter/aion-labs/aion-3.5-mini pricing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42743
- test(integration): add MCP gateway coverage wave 1 with a dedicated mcp shard and proxy coverage artifact by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42711
- fix(ui): keep untouched stored auto-router booleans and reminder marker casing on save by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42703
- feat(bedrock): add gpt-6-sol and gpt-6-luna model pricing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42746
- chore(ci): drop litellm_internal_staging and litellm_oss_staging references, main is the only trunk by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42745
- feat(cost-map): add Azure Foundry pricing for gpt-6-sol and gpt-6-luna by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42747
- feat(secrets): route secret resolution through native Rust backends by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42619
- test: deflake fuzzy picker, breached-password HIBP, and MCP stdio timeout tests (rolling deflake 2026-09-22) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42125
- feat(gemini): add gemini-3.8-flash-tts and gemini-3.8-flash-lite-tts prices by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42752
- test(integration): regression tests for July provider translation, routing and streaming bugs by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42693
- test(integration): regression tests for July cost tracking, budgeting and spend bugs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42694
- feat(models): add openrouter/stealth/space-bunny-alpha by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42759
- fix(params): stop stream_chunk_size reaching provider request bodies by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42664
- ci: add merge smoke checks workflow with loopback-only harness and 11 curated cases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42709
- fix(completion_extras): forward non-enum reasoning_effort through the Responses bridge instead of dropping it by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42452
- fix(bedrock): honour stream_chunk_size in Invoke streaming by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42686
- fix(prices): add baseten/zai-org/GLM-5.3-Fast pricing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42764
- fix(ui): keep per-user MCP credentials updatable and clearable after setup by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42652
- test(rust): model the blocking OCR hook as a guardrail so its raise propagates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42775
- feat(guardrails): straiker guardrail speaks the v3 platform API (/api/v3/detect) by @PhimmStraiker in
  https://github.com/BerriAI/litellm/pull/41880
- fix(anthropic): preserve MCP tool results in the non-Anthropic Messages bridge by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42783
- test(integration): cover customer reported cache key, cache_control, bedrock request id, responses schema, scim and
  tag budget contracts by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42785
- chore(prices): sync OpenRouter prices: 2 models, 2 deprecated [20 held] by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42756
- ci: add tests-only CircleCI pipeline with coverage and docs validation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42773
- chore(prices): sync Baseten prices: 1 model by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42771
- feat(bedrock): add bare openai.gpt-6-sol and openai.gpt-6-luna cost map rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42798
- feat(cache): add a guarded native response-cache resolver foundation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42769
- feat(embeddings): add native dispatch foundation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42799
- fix(mcp): return 401 challenge for REST token-exchange tool calls without a subject token by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42782
- fix(mcp): forward caller bearer on REST oauth_delegate tool calls by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42787
- feat(models): add together_ai/together/Tev1-4B-experimental by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42807
- chore(prices): sync Fireworks AI prices: 2 models, 2 new [2 with gaps] by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42590
- feat(rust-bridge): extend native dispatch foundation to chat completions, responses, and messages by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42805
- feat(bedrock): serve the OpenAI models on bedrock-runtime's native Responses API (internal copy of #38489) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42767
- fix(redis): authenticate sync clusters with IAM credential providers by @SiluPanda in
  https://github.com/BerriAI/litellm/pull/40204
- fix(proxy): apply user_api_key_cache_max_size to the key object partition by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42796
- fix(mcp): keep tool attribution on guardrail-blocked REST calls by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42790
- chore(prices): sync OpenRouter prices: 1 model [17 held] by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42806
- fix(key_management): invalidate cached object permissions on key update by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/36719
- docs: simplify pull request template into plain English questions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42813
- test(straiker): deterministic integration audit of the v3 platform relay by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42781
- fix(otel): root post-response service spans in their own trace linked to the request by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42826
- revert: restore the full pull request template (reverts #42813) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42828
- fix(ui): hide LiteAdmin in Playground and add admin preference by @tin-berri in
  https://github.com/BerriAI/litellm/pull/42755
- fix(ui): prefer native providers in auto-router presets by @tin-berri in https://github.com/BerriAI/litellm/pull/42639
- fix(shadow-eval): replay approved pre-call guardrail snapshots by @tin-berri in
  https://github.com/BerriAI/litellm/pull/42774
- fix(ui): show ten prompt caching requests per page by @tin-berri in https://github.com/BerriAI/litellm/pull/42638
- feat(lint): add LIT013 flagging *-ok suppressions that suppress nothing and remove the 240 stale ones by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42793
- fix(mcp): reject duplicate MCP server names and aliases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42791
- feat(proxy): honor model_info.discoverable on the model listing endpoints by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42825
- feat(cost-map): add vertex ai llama 3.3 70b, veo 2/3, virtual try-on and 2.5 tts rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42837
- fix(proxy): gate disable_global_guardrails on keys and teams to proxy admins by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42699
- fix(models): sync openrouter prices from the models API by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42832
- feat(models): add gemini preview aliases and deep research 04-2026 rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42833
- docs(pr-template): drop empty sections from the PR body and tighten the User Flow by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42794
- feat(ui): configure prompt caching request rows per page by @tin-berri in
  https://github.com/BerriAI/litellm/pull/42842
- fix(ollama): read the JSON thinking field on non-streaming completions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42838
- feat(models): add openai chat-latest, codex and deep-research rows from the model docs by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42834
- fix(proxy): document request body and response schemas for the Responses API in OpenAPI by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42802
- fix(models): add the June 1, 2026 retirement date to the vertex_ai gemini-2.0-flash rows by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42850
- fix(caching): stamp provider on sync cache-hit logs so responses spend logs record provider by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42830
- feat(models): add 39 together_ai chat rows priced by the Together models API by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42851
- chore(models): add deprecation_date to claude-mythos-preview from the Anthropic deprecations page by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42845
- test(integration): assert /v1/responses usage reports Anthropic system cache write then read by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42855
- fix(models): add the sora-2-pro shutdown date to the sora-2-pro-high-res rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42846
- feat(models): add openrouter/openai/gpt-oss-120b:batch from the OpenRouter models API by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42847
- feat(models): add gemini lyria-realtime-exp row inherited from lyria-3.5 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42848
- feat(bedrock): add 17 aws-bedrock cost map rows from provider sync by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42852
- fix(models): add fireworks deprecation dates for kimi k2.6 fast, kimi k2.7 code fast and glm 5.2 fast us by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42849
- fix(model-catalog): declare above_32k cost fields on ModelInfo by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42856
- fix(model_prices): registry audit 2026-09-23, in-region Bedrock Claude prices by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42779
- test(integration): cover per key tag rpm limits and tag budget_duration resets by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42859
- fix(models): add fireworks deprecation date for glm 5.2 fast serverless rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42866
- chore(vertex_ai): add deprecation dates for retired claude 3 and jamba 1.5 partner models by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42867
- test(integration): assert /v1/models reports max_input_tokens and max_output_tokens by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42858
- fix(fireworks_ai): route firerouter short names and bill pass-through legs at the routed model's rates by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42814
- fix(models): add azure gpt-4o-mini-transcribe and gpt-4o-mini-tts deprecation dates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42873
- fix(models): add openai deprecation date for gpt-5-chat-latest and gpt-5-chat by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42872
- fix(models): add fireworks 2026-09-25 deprecation dates for glm 5.2, kimi k2.6, kimi k2.7 code, deepseek v4 and muse
  glimmer rows by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42874
- fix(model_prices): bedrock bare Claude ids priced at the Global SKU (aws-bedrock sync) by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42875
- feat(cost-map): add retired azure gpt-5 chat and o1-preview data zone rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42878
- fix(models): correct gemini robotics er 2 preview audio input price by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42877
- feat(vertex_ai): add gemini-3.8-flash-cyber pricing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42879
- fix(presidio): stream non-Anthropic raw SSE through the post_call hook unbuffered by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42777
- fix(cost-map): halve openrouter deepseek-v4-flash-0731 output price by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42881
- fix(cost-map): sync vertex-ai deprecation dates from Vertex model lifecycle pages by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42882
- fix(cost-map): add azure gpt-realtime-mini deprecation date by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42883
- fix(models): correct fireworks kimi k3 us pricing to the published rate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42884
- fix(cost-map): add azure gpt-realtime-mini-2025-10-06 deprecation date by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42885
- fix(logging): scan the exceeded budget wording linearly so a crafted error message cannot stall the proxy by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42778
- fix(proxy): keep deployment labels on cache-hit post_call guardrail rejections by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42780
- fix(proxy): do not requeue a daily spend batch whose commit already left for postgres by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42786
- fix(cost-map): sync openrouter prices and add fireworks ember-1 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42889
- fix(cost-map): source and chat completions endpoint for bedrock mantle gpt-5.4 and gpt-5.5 by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42890
- feat(cost-map): add vertex_ai/gemini-3.8-live by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42891
- fix(passthrough): log upstream 4xx/5xx error bodies and carry them into the failure hook by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/42695
- test(integration): add read-replica routing harness to the CircleCI integration suite by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42692
- fix(s3_v2): bound concurrent S3 uploads per flush and add opt-in JSONL batch files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41258
- fix(cost-map): source for bedrock mantle gpt-5.6 luna, sol, terra and grok-4.6 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42898
- test(integration): edge-case matrices for malformed token limits and callback_settings shapes by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42895
- fix(cost-map): add azure deprecation dates for gpt-6 and gpt-realtime-whisper by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42897
- feat(cost-map): add wandb DeepSeek-V4.1-Flash and gemma-4-26B-A4B-it by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42924
- fix(cost-map): update openrouter kimi-k2.7-code input price by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42932
- fix(cost-map): add azure deprecation dates for regional gpt-6 rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42933
- chore(techdebt): clear fresh tech debt from the last 24 hours (rolling, 2026-09-06 to 2026-09-24) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42710
- fix(cost-map): sync vertex-ai rows (gemma 4 maas cache price, chirp_2) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42942
- feat(bedrock): add gpt-5.4 and gpt-5.5 us and global inference profile pricing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42941
- fix(cost-map): update azure gpt-4.1-nano and gpt-4o-2024-05-13 retirement dates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42947
- fix(proxy): list key and team model aliases in GET /v1/models by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42908
- fix(cost-map): sync openrouter prices for deepseek v4 and glm-5.3 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42952
- fix(cost-map): add batch prices for vertex gemini-3.8-flash-cyber by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42953
- fix(cost-map): add azure realtime, audio and partner model rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42954
- fix(cost-map): sync openrouter deepseek-v4-pro prices by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42956
- fix(cost-map): sync openrouter deepseek-v4-pro prices by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42964
- fix(proxy): fail parked DB lookups at a deadline and flip readiness while they stall by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42654
- fix(cost-map): sync openrouter deepseek-v4-pro prices by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42969
- feat(cost-map): sync azure models, add MAI-Image-2.6, deepseek-v4.1-flash, muse-spark-1.3 by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42970
- fix(bedrock): extrapolate global cris pricing for gpt-5.4 and gpt-5.5 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42971
- fix(cost-map): sync openrouter deepseek v4 flash, v4 pro and v4.1 flash prices by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42974
- refactor(types): replace Any with proven types in 13 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42937
- fix(cost-map): sync openrouter deepseek-v4-pro prices by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42978
- fix(cost-map): add vertex ai priority audio input prices for gemini flash rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42980
- feat(rust_bridge): stamp x-litellm-rust on native sync and async streams at the bridge boundary by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42758
- feat(azure): add gpt-audio and gpt-realtime alias rows from the Azure model list by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42981
- fix(cost-map): align openrouter deepseek-v4-pro cache hit price with cache read by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42985
- fix(cost-map): take the later azure deprecation date for gpt-4.1-nano, gpt-4o-transcribe and gpt-realtime-2.1 by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42986
- fix(cost-map): add supports_reasoning to azure/eu/gpt-6-astra by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42989
- fix(mcp): reject origins outside the configured allowlist by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/42649
- fix(cost-map): drop stale cache_hit field from openrouter deepseek-v4-pro by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42994
- fix(cost-map): add vertex cache read, batch and above 200k prices for gemini image preview rows by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42995
- test(ollama): assert the images sent to Ollama instead of echoing them through response by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42905
- fix(ui): pass is_proxy_admin for proxy admins on the models page team drill-in by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43003
- test(e2e/ui): give the logout specs their own admin session by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42930
- fix(azure): update gpt-audio-mini and gpt-5-chat deprecation dates from the retirement schedule by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43017
- test(vertex_ai): run the files peak-memory guards without coverage tracing by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42914
- test(mcp): stop a comprehension variable from shadowing the body() helper by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42906
- test(mcp): patch create_mcp_server_if_identifier_free in the store-model-in-db MCP tests by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42916
- test(guardrails): run the cache-hit redis outage test on the shared owned_redis helper by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42925
- feat(rust): shape Anthropic Messages requests natively by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42982
- fix(prometheus): add model_group label to deployment request and rate limit metrics by @ahamedshaik16 in
  https://github.com/BerriAI/litellm/pull/42966
- fix(cost-map): add the Vertex shutdown date to gemini-2.5-flash-native-audio by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43024
- feat(vertex): native batch JSONL passthrough with cost tracking by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42810
- fix(logging): pass provider response headers to callbacks on every endpoint by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42824
- feat(usage): search keys beyond the top-N usage subset by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42827
- feat(usage): search team keys beyond the top-N in the Team usage view by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42857
- fix(bedrock): route unmapped openai family model ids to converse by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42713
- refactor(rust): move tests.rs files inline or under tests/ and drop autotests = false by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43028
- fix(cost-map): add video and reasoning output prices to vertex gemini-omni-1.1-flash by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43036
- feat(proxy): server-side Team Usage export beyond the top-N key cap by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42996
- fix(proxy): stop leaking periodic tasks on every DB config reload by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42784
- chore(cost-map): add azure deprecation dates from the Models API for five realtime and transcribe rows by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43037
- fix(proxy): pass team member spend rows as jsonb so a $0 flush cannot poison the pool connection by @ryan-crabbe-berri
  in https://github.com/BerriAI/litellm/pull/43029
- fix(vertex_ai): keep batch output_file_id null until Vertex reports outputInfo by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43030
- fix(playground): stop following streamed tokens, add jump to bottom button by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42968
- fix(cost-map): drop the priority input price from vertex gemini-2.5-flash-image by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43050
- feat(compat-matrix): resolve and install the Claude Code CLI per run by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43038
- test(e2e/ui): hide the LiteAdmin button in the shared admin session by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43033
- ci: fix the litellm-tests unit job (sysmon, codecov on failure, env -i allowlist, selection errors, reruns param) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42900
- test: take keys out of the legacy proxy, enterprise and mcp unit tests before moving them by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42901
- feat(terraform): add display_name to litellm_model resource and model data sources by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42987
- feat(proxy_cli): add --validate_config dry-run flag by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41705
- fix(e2e): skip unpublished npm versions in the Claude Code PR-gate resolver by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43053
- chore(cost-map): move azure gpt-realtime-2.1-mini deprecation date to the later Models API date by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43058
- docs(github): require UI before/after screenshots and intentional UX change note in PR template by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43021
- ci: move caching, proxy-extras, gateway and enterprise tests into tests/unit and run them from litellm-tests by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42902
- feat(proxy): let callbacks filter the model listing routes per caller by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43027
- ci: move tests/proxy_unit_tests to tests/unit/proxy and run the proxy-db shards from litellm-tests by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42903
- ci: move provider-independent MCP tests into tests/unit and run mcp-integration from litellm-tests by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42904
- fix(vertex_ai): translate /v1/responses batch rows through the Responses-to-Chat bridge by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43042
- fix(cost-map): add vertex priority prices for gemini-3-pro-image-preview and batch price for gemini-embedding-001 by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43069
- feat(agents): add optional per-agent kill switch webhook by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42841
- fix(proxy): stop /utils/transform_request from calling the provider and blocking the event loop by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/33954
- fix(ui): explain unbackfilled key lifetime spend and ship a backfill script by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42967
- chore(cost-map): add video input price to gemini 3.8 live rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43073
- fix(cost-map): drop cache read price from vertex gemini-2.5-flash-image by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43078
- docs(e2e): carve harness tests out of the no-unit-tests hard rule by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43076
- fix(mcp): cap an agent key's tools at what the invoking user and team may call by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/42478
- feat(spend): capture-rate check of LiteLLM spend against the OpenAI bill by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43044
- ci: run the claude_code harness unit-test trees in the lint job by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43077
- fix(cost-map): sync openrouter deepseek v4 and glm-5.3-flash prices, add mistral-large-2512 by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43090
- feat(cost-map): add fireworks glm-5p3 US-only rows and kimi-k3-us priority prices by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43092
- feat(ui): offer reset of custom member budgets when team default changes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42835
- fix(router): serve Responses turns from a sibling when the encrypted content origin has no boundary peer by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43015
- chore(cost-map): sync gemini priority, flex and video token prices from the Gemini API pricing page by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43091
- feat(cost-map): add fireworks deepseek-v4p1-flash US-only rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43097
- fix(router): match provider-prefixed fallback keys for bare model groups served by wildcard deployments by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43062
- fix(bedrock): map Anthropic batch row params the way real time does by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43087
- feat(ui): make the audit log detail drawer wider and resizable by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42808
- feat(proxy): enforce tpm_limit and rpm_limit set on tag objects by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41807
- feat(rust_bridge): read secrets through Python from Rust routes and declare Rust-only routes with NO_PYTHON by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43057
- refactor(ocr): remove the Python OCR execution path and require the Rust route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43081
- fix(spend): attribute CLI session spend to the per-user cli-session alias instead of the hashed session token by
  @mateo-berri in https://github.com/BerriAI/litellm/pull/40541
- test(e2e): pin end-user and tag attribution from Codex-style headers on /v1/responses by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43093
- fix(vertex_ai): return chunk content, extractive text, and structData from search_api vector store hits by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43100
- feat(lint): cap comprehensions at one for and one if clause (LIT014) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42650
- chore(cost-map): add openai deprecation dates from the deprecations page by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43102
- chore(cost-map): add gemini tts batch output prices from the Gemini API pricing page by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43103
- feat(proxy): let team admins update member key budgets when enabled by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42555
- fix(vertex_ai): surface the Gemma container's own error inside a 200 :predict response by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43075
- chore(cost-map): add azure retirement dates from the retired Foundry models page by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43104
- fix(fal_ai): price nano-banana-2 and nano-banana-pro image generations by resolution by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43101
- chore(cost-map): add computer-use-preview deprecation date from the openai deprecations page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43116
- fix(proxy): authorize key model aliases the same way as team aliases by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43049
- chore(cost-map): add azure retirement dates for command-r-plus and gpt-4 by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/43117
- fix(vertex_ai): stop advertising OpenAI platform-only params on Gemma and Llama routes by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/43079
- fix(router): honor disable_fallbacks on mid-stream fallback by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43111
- refactor(types): declare litellm-owned kwargs as typed objects and derive the lists from their fields by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42843
- chore: bump litellm-enterprise 0.1.70 -> 0.1.71, litellm-proxy-extras 0.4.101 -> 0.4.102 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43120
- fix(cost): apply a deployment's pricing override to realtime sessions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43114
- refactor(rust): extract the host coroutine into its own crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43129
- chore(cost-map): add together-ai deprecation dates for gpt-oss-20b and gemma-4-31B-it by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43127
- feat(mcp): allow ["*"] wildcard in mcp_tool_permissions to grant all current and future tools by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43108
- ci: cut rc/<X.Y.0> off main every Friday at 3am Pacific by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43121
- fix(anthropic): keep the replayed prefix byte-stable for preserved thinking on chat completions by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42630
- feat(providers): add Nadir intelligent-router provider (nadir/auto) by @doramirdor in
  https://github.com/BerriAI/litellm/pull/33227
- fix(together_ai): backfill deprecation_date from Together deprecation history by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43135
- test(e2e): cover Azure code_interpreter container files by native id with a service-account key by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43122
- fix(router): await budget redis pipeline before sync reads (internal copy of #32618) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43125
- chore(cost-map): add openai cached image input prices from the pricing page by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/43143
- feat(langfuse)!: migrate the sdk callback to langfuse v4 by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/36741
- fix(key_management): count team unified access group MCP servers when validating key MCP grants by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41231
- fix(ui): group cost optimization cache leakage by model group by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43008
- fix(presidio): mask streamed /v1/messages output when the first upstream read is a keepalive, a data-less ping, or a
  split utf8 character by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/43023
- test: backport stale and state-leaking test fixes to rc/1.104.0 (#43266) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43267
- chore: backport CI fixes, #43206 and Rust changes to rc/1.104.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43338
- fix(s3_v2): backport #43022 to rc/1.104.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43354
- chore: rebuild Admin UI bundle for rc/1.104.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43372
- chore: backport CircleCI speedups (#43347) and cost-map fixes (#42951) to rc/1.104.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43366
- revert(usage): remove the top-N key cap, its follow-ups and the daily global spend rollup code from rc/1.104.0 by
  @yuneng-berri in https://github.com/BerriAI/litellm/pull/43385
- fix(streaming): backport text-completion usage chunk fix (#43047) to rc/1.104.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43402
- test(e2e): report batch cleanup leftovers as a plain UserWarning on rc/1.104.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43406
- test(e2e): skip the LangSmith batch serialization e2e on rc/1.104.0 until CI has a LangSmith key by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43418
- test(unit): stop test modules from putting their own directory on sys.path on rc/1.104.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43420
- fix(proxy): unregister logging callbacks removed from the stored config on rc/1.104.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43432
- chore(release): sync rc/1.104.0 to v1.104.0-rc.2 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43825
- fix(proxy): backport #43962 to rc/1.104.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/44054
- chore(release): backport #43948, #44109, #44124 to rc/1.104.0 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44156
- revert: backport of #43948, #44109, #44124 to rc/1.104.0 (#44156) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44212
- chore(release): backport #44066 to rc/1.104.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/44216
- fix(proxy): enforce the migration check by default and stop building SpendLogs indexes in migrations (rc/1.104.0) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/44206
- chore: bump litellm-proxy-extras to 0.4.102.post1 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/44224
- test(integration): opt the config pass-through spend-log case into auth (rc/1.104.0 backport of #44265) by
  @yuneng-berri in https://github.com/BerriAI/litellm/pull/44267
- test: fix three order-dependent and timing-flaky tests (rc/1.104.0 backport of #44271) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44280
- chore(release): backport #44277 to rc/1.104.0 and bump oauthlib by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44304
- chore(release): backport #44283 and part of #44229 to rc/1.104.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44312
- chore(release): backport part of #43902 and #43983 to rc/1.104.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/44332
- fix(proxy-extras): keep the post-migration sanity check from building the hand-built SpendLogs indexes by
  @yuneng-berri in https://github.com/BerriAI/litellm/pull/44397

## New Contributors

- @chopratejas made their first contribution in https://github.com/BerriAI/litellm/pull/41560
- @Zechereh made their first contribution in https://github.com/BerriAI/litellm/pull/41099
- @philschmid made their first contribution in https://github.com/BerriAI/litellm/pull/42465
- @patel-26meet made their first contribution in https://github.com/BerriAI/litellm/pull/39311
- @togear made their first contribution in https://github.com/BerriAI/litellm/pull/41033
- @Pawan-Shahane made their first contribution in https://github.com/BerriAI/litellm/pull/41979
- @SiluPanda made their first contribution in https://github.com/BerriAI/litellm/pull/40204
- @ahamedshaik16 made their first contribution in https://github.com/BerriAI/litellm/pull/42966
- @doramirdor made their first contribution in https://github.com/BerriAI/litellm/pull/33227

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.103.0...v1.104.0

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
  ghcr.io/berriai/litellm:v1.103.2
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.103.2/cosign.pub \
  ghcr.io/berriai/litellm:v1.103.2
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

## What's Changed

- chore(release): sync stable/1.103.x to v1.103.1 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43824
- fix(proxy): backport #40541, #43642, and #43656 to stable/1.103.x for v1.103.2 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43897
- fix(anthropic): backport #42152 and #42288 to stable/1.103.x by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/43662
- fix(proxy): backport #43962 to stable/1.103.x by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43984

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.103.1...v1.103.2

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
  ghcr.io/berriai/litellm:v1.103.1
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.103.1/cosign.pub \
  ghcr.io/berriai/litellm:v1.103.1
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.103.0...v1.103.1

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
  ghcr.io/berriai/litellm:v1.103.0
```

**Verify using the release tag (convenience):**

Tags are protected in this repository and resolve to the same key. This option is easier to read but relies on tag
protection rules:

```bash
cosign verify \
  --key https://raw.githubusercontent.com/BerriAI/litellm/v1.103.0/cosign.pub \
  ghcr.io/berriai/litellm:v1.103.0
```

Expected output:

```
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key
```

---

## What's Changed

- fix(responses): translate the reasoning object into a chat-completion reasoning effort by @joshgarnett in
  https://github.com/BerriAI/litellm/pull/36363
- fix(proxy): bound tool and guardrail index create_many by the spend-log statement budgets by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/40561
- fix(mcp): require admission for delegated OAuth by @joshua-berri in https://github.com/BerriAI/litellm/pull/40923
- fix(logging): log one bounded summary for a burst of timed-out LoggingWorker callbacks by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/40912
- fix(fireworks): resolve short model names to long cost map keys by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40929
- ci: remove main branch source guard by @yuneng-berri in https://github.com/BerriAI/litellm/pull/40172
- chore(ci): promote internal staging to main by @yuneng-berri in https://github.com/BerriAI/litellm/pull/40942
- fix(spend_logs): store litellm_call_id and match it in request_id lookups by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39068
- fix(auth): refresh lite login session token grants from the live user and team rows by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/40657
- feat(bedrock): support file delete and list for S3-backed managed files by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39836
- fix(proxy): gate the webhook test alert on proxy admins by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/40814
- fix(ui): hide admin write-form tabs on the models page from view-only admins by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/38867
- fix(anthropic-adapter): surface mid-stream provider errors as Anthropic error events by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/33352
- docs(github): add an Affected release section to the PR template by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/40618
- docs(e2e): ban unit tests under tests/e2e by @yassin-berriai in https://github.com/BerriAI/litellm/pull/33852
- fix(router): preserve Azure Entra ID params in reusable credentials by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40889
- docs(user endpoints): remove unsupported soft_budget param from user docstrings by @shivamrawat1 in
  https://github.com/BerriAI/litellm/pull/36585
- feat(friendli): auto-sync Friendli model metadata into price registry by @Lee-Si-Yoon in
  https://github.com/BerriAI/litellm/pull/35918
- build(deps): bump smol-toml to 1.8.0 to clear GHSA-7w5x-hrqm-74c2 in osv-scan by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40478
- fix(bedrock_mantle): price GovCloud regions from the regional cost row and accept region-prefixed model names by
  @mateo-berri in https://github.com/BerriAI/litellm/pull/39846
- chore(ci): remerge internal staging by @yuneng-berri in https://github.com/BerriAI/litellm/pull/40943
- test(auth): freeze the cache clock in auth prefetch tests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40996
- feat(jwt): allow virtual_key_claim_field per issuer by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40927
- fix(cost): bill cached realtime audio tokens at the audio cache-read rate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40627
- perf(logging): skip correlation contextvar stamping when request_correlation_in_logs is off by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41054
- feat(pricing): add azure gpt-chat-latest rates and drop retired friendliai llama-3.1 entries by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/40976
- build(deps): re-suppress GHSA-h7x2-h6g9-p789 in osv-scan on main, mlflow still has no fixed release by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41104
- fix(otel): cap per-index OpenInference message attributes span-wide by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40562
- feat(proxy): add general_settings.allowed_file_extensions for /v1/files uploads by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41106
- fix(proxy): forward provider request id headers on mapped error responses by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40925
- fix(router): name the all-deployments-in-cooldown error on 429 responses by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40995
- fix(ui): show the team alias on the model info page and in its raw JSON by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40992
- feat(proxy): honor LITELLM_DISABLE_ACCESS_LOG_PATHS to drop noisy uvicorn access log lines by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41096
- fix(prometheus): label pre-call rate limit failures with the resolved api_provider by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41059
- perf(proxy): serialize /model/info listing once with orjson by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41114
- fix(utils): stop wrapper_async submitting the sync success handler twice by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41115
- fix(redis): log a timeout streak once per interval instead of one line per cache call by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40817
- fix(router): record flat retry attempts and cap retries from attempted_retries by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40930
- refactor(prometheus): source PROXY_LLM_PROVIDER_FALLBACK from litellm.constants by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41118
- fix(proxy): hide default credentials login hint when UI_PASSWORD is set by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41107
- fix(cli): show routed models and session stats for LLM API keys by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41116
- fix(bedrock/realtime): propagate deferred Nova Sonic stream failures to the router by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41064
- fix(proxy): keep org admins' own team memberships in other orgs visible on team list by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41086
- feat(model_info): provider-scoped fill_missing_for_providers backfill from fallback generalization rules by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41093
- fix(auth): load team membership once per request and skip prisma on an L1 hit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41102
- refactor(harness): expand independent trace coverage by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/41120
- fix(proxy): release max_parallel_requests slot when a realtime session ends without LLM callbacks by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41113
- fix(router): cool down team deployments on 429 when a sibling serves the same public model by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/40991
- fix(ui): move tags typed into key metadata JSON into the Tags field by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41023
- fix(ui): let team admins grant a team all proxy models by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/40196
- chore(lint): graduate 12 rules from the strict-gate ratchet by @HUAHAODIA in
  https://github.com/BerriAI/litellm/pull/41048
- test: add dedicated CircleCI integration contract foundation by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41066
- fix(utils): keep litellm params out of provider request bodies by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41018
- fix(openai): keep extra_headers out of the chat request body on the httpx handler path by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41141
- test: cover persisted updates and warmed authorization policies by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41070
- fix(proxy): resolve x-litellm-call-id from response metadata when routes omit call_id by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41056
- chore(prices): sync Vertex AI prices: 14 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/40955
- ci(codeql): exclude noisy Python quality queries by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41142
- feat(proxy): predict prompt-cache costs across deployments by @tin-berri in
  https://github.com/BerriAI/litellm/pull/40877
- fix(prompt_security): keep polling file sanitization through non-terminal statuses by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41131
- fix(health): skip background health check DB writes when the latest-row read fails by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41145
- feat(model_armor): logging_only mode scans completed streams after delivery by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40702
- fix(bedrock guardrails): derive contextual grounding source and query from plain messages by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41132
- fix(cli): drop enum.StrEnum so the CLI imports on Python 3.10 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41046
- fix(responses): route mid-stream error events through exception_type so content_policy_fallbacks fire by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/40988
- fix(cost): bill gemini-embedding-2 per token and stop double charging audio by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41157
- test: bind management E2E callers and isolate JWT actors by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/40892
- fix(headroom): protect cache_control-marked rows anywhere in history by @rad-p44 in
  https://github.com/BerriAI/litellm/pull/40315
- test: add strict stateless provider replay identity by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41149
- fix(ci): test checked-out model pricing in unit jobs by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41181
- fix(guardrails): write per-message guardrail rewrites back onto Responses input items by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40939
- fix(proxy): log the provider usage on deferred /v1/messages calls and price cache writes without a creation rate by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41172
- fix(guardrails): record not_run evaluation when scoping leaves nothing to scan by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/39050
- fix(responses): preserve provider affinity by @AaronHowell in https://github.com/BerriAI/litellm/pull/40228
- fix(sdk): keep body and proxy headers on BadRequestError mapped from a litellm_proxy 400 by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/40994
- fix(responses): hoist Codex additional_tools input items into the chat bridge tools by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40989
- fix(router): honor team and key provider weights by @tin-berri in https://github.com/BerriAI/litellm/pull/41072
- test(e2e): verify streamed answers and tool continuation by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41194
- fix(cli): label router costs and simplify the routed-model header by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41186
- test(spend): reconcile concurrent requests and daily activity by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41188
- fix(guardrails): scan the Anthropic top-level system prompt and tool_use arguments by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40984
- fix(router): count num_retries_per_request across fallback hops by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41191
- fix(bedrock): grant rerank, retrieve, agent, and agentcore actions in the web identity session policy by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41168
- fix(vertex-live): bill Gemini Live sessions end to end (internal copy of #37075) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40915
- fix(health): resolve litellm_credential_name in realtime health checks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41173
- feat(proxy): unified custom_key_policy hook for key generate, update and regenerate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40921
- fix(proxy): enforce custom_key_update policy on /key/regenerate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40695
- fix(router): preserve session model choice within each complexity tier by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41174
- test(pricing): let synced GovCloud Bedrock rows cite the AWS price list by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41263
- docs(github): ask for interactive coding-tool proof in the PR template by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41257
- feat(proxy): add POST /management/v1/users/bulk for batched user and team membership creation by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41028
- fix(credentials): answer 409 on a credential name collision, make Terraform adoption opt-in by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/40917
- feat(proxy): add POST /management/v1/users/bulk_delete and POST /management/v1/teams/{team_id}/members/bulk_delete by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41039
- fix(proxy): list directly assigned team models in model access errors by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41256
- feat(auto-router): allow opted-in team members to manage their routers by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41175
- build(rust-bridge): add typed _native stub and validate it with mypy.stubtest by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41180
- feat(guardrails): add new upstream presidio pii entities including german set by @MvdB in
  https://github.com/BerriAI/litellm/pull/36775
- fix(responses): filter bridged kwargs like the native Responses path by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41144
- test(e2e): cover the reliability retry, cooldown, fallback, and routing-strategy cells by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39857
- fix(anthropic): add the per-turn-control beta when a message carries output_config by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41189
- fix(router): bind per-request routing_strategy override selectors to the request's callbacks by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41178
- feat(proxy): bind JWT claims to registered agents via agent_id_jwt_field by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40904
- fix(proxy): enforce organization budgets when max_budget is 0 by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/41271
- fix(alerting): send llm_exceptions Slack alert for 5xx HTTPException and ProxyException by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41125
- fix(headroom): protect the cached prefix through the last cache_control breakpoint by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41161
- fix(utils): cache custom HuggingFace tokenizers across /utils/token_counter requests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41216
- fix(router): keep weighted routing when a deployment id equals a model_name by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41156
- feat(router): add capability classifier as Fuse foundation by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41270
- fix(proxy): keep access-group raw SQL writes on the writer while writer_unavailable is stale by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41283
- fix(prometheus): count 401 auth failures in litellm_proxy_failed_requests_metric by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41170
- test: drop tests that pin vendor facts and add the CLAUDE.md rule by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41269
- fix(proxy): run the remaining inline token counts off the event loop by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40262
- fix(proxy): log blocked streaming guardrail responses as failures, not success by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40191
- feat(proxy): add tpd_limit (tokens per day) for batch submissions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40997
- fix(proxy): reconcile budget reservation before enqueuing spend to the DB by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40310
- fix(xai): stop sending web_search_options to xAI's retired Live Search path by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38278
- feat(terraform): add tpm_limit, rpm_limit, budget_duration, allowed_models to litellm_team_member_add by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/38682
- fix(rerank): bill Vertex search_units from input records and give every rerank response a unique id by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/35180
- fix(router): stop counting caller-set timeout 408s toward deployment cooldown by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41230
- feat(router): add Fuse V2 classifier after capability forecasting by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41272
- fix(proxy): keep client User-Agent on auth failure spend logs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41291
- fix(proxy): reset budgets by decrementing pre-reset spend instead of zeroing rows by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41279
- fix(xai): honor nested web_search filters on the xAI Responses API by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/38268
- fix(router): stop registering a caller-supplied credential as a router deployment by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/41289
- fix(router): accept custom_provider_map providers before the first completion call by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41300
- fix(proxy): return 400 instead of 500 for lone surrogate escapes in request body by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41297
- fix(langsmith): keep events appended during an in-flight flush instead of clearing them by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41288
- fix(logging): track spend for streams a deployment hook converted to non-streaming by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41171
- fix(bedrock): sanitize client tool_call ids to Bedrock toolUseId constraints by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40872
- fix(passthrough): attribute Vertex passthrough successes to the resolved router deployment by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41307
- feat(ui): persist Models table search, filters, sort and page in the URL by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41296
- fix(jwt-auth): scope JWT key mappings by issuer to prevent cross-issuer collisions by @yassin-berriai in
  https://github.com/BerriAI/litellm/pull/41281
- feat(openai): add openai_system_messages_first to put system messages first for prompt caching by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41304
- feat(ui): add custom request headers to the API Playground by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41309
- feat(cli): sync Codex /model picker from proxy /v1/models in lite codex by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40476
- chore: bump litellm-enterprise 0.1.67 -> 0.1.68, litellm-proxy-extras 0.4.97 -> 0.4.98, litellm 1.102.0 -> 1.103.0 by
  @yuneng-berri in https://github.com/BerriAI/litellm/pull/41321
- feat: add aihubmix provider pricing entries by @IToSSc in https://github.com/BerriAI/litellm/pull/41179
- feat(auto-router): add per-model Fast mode toggle by @tin-berri in https://github.com/BerriAI/litellm/pull/41282
- fix(proxy): include litellm_call_id in LLM API exception logs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41205
- fix(proxy): keep yaml pass-through endpoints visible to auth after db overlay by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41303
- fix(proxy): resolve router_settings.model_group_alias before key/team model auth by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41308
- fix(ui): block usage export and flag the range when a spend page fails by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41294
- fix(vertex_ai): bill Gemini Omni Interactions usage and Veo sampleCount on passthrough by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41322
- fix(proxy): honor LITELLM_LOG for uvicorn and proxy extras loggers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41306
- fix(cost): price native Responses WebSocket turns at their returned service_tier by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41318
- fix(proxy): key model rpm/tpm override takes precedence over team model limit by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41302
- fix(proxy): track per-member organization spend by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41255
- feat(proxy): add /nvidia_nim passthrough route for NIM object detection and OCR /v1/infer by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41316
- feat(model_info): add provider-neutral Gemini 2.5+ chat baseline fallback generalization by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41320
- fix(spend): sum multi-round session duration in logs UI by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/35388
- feat(router): limit unlicensed Capability and Fuse v2 routers to one each by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41326
- fix(guardrails): resolve caller identity from metadata buckets in custom code guardrail by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41126
- fix(e2e): onboard dashboard users through invitations by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41319
- feat(guardrails): add Microsoft Agent 365 MCP tool-call guardrail by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/38241
- test: drop remaining tests that pin cost-map vendor facts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41298
- feat(ui): show average response time per model in usage model activity by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41313
- fix(proxy): preserve Anthropic pricing modifiers in router savings by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41341
- feat(guardrails): support pre_call and during_call modes for llm_as_a_judge by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41128
- fix(gemini): propagate the provider's modelVersion to the response model by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41338
- fix(fireworks-ai): bill cache-write, reasoning and audio tokens via the shared cost calculator by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41339
- feat(guardrails): singulr v2 API contract with logging_only, pre_mcp_call and post_mcp_call by @yucheng-berri in
  https://github.com/BerriAI/litellm/pull/41329
- ci(image-scan): ignore zlib CVE-2026-85091 until Wolfi ships the fix by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41353
- feat(e2e): reuse exact provider responses for 24 hours by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41346
- fix(xai): keep 'instructions' on the xAI Responses API so system messages survive web search by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/38254
- feat(ui): configure capability and Fuse v2 classifiers by @tin-berri in https://github.com/BerriAI/litellm/pull/41315
- fix(anthropic): tolerate message_delta events without usage when streaming by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41336
- test(router): ignore deployment-selection logs in the fallback log assertion by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41358
- test(proxy): assert budget resets decrement the cleared spend by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41359
- fix(e2e): expect models filters to persist after reload by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41348
- fix(e2e): record cookie-setting provider responses and keep prompt-caching tests live by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41366
- fix(responses): recount tokens when a streamed response completes without usage by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41337
- fix(ui): simplify Capability and Fuse advanced routing options by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41371
- fix(mcp): authorize JWT OAuth credential persistence by @joshua-berri in https://github.com/BerriAI/litellm/pull/41314
- feat(router): stream shadow traffic and fan out silent_model to multiple targets by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41368
- perf(content_filter): scan a bounded window per streamed chunk by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41407
- fix(proxy): hide model allowlist from client-facing model access denied errors by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41310
- feat(http): opt-in outbound HTTP/2 for httpx clients by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41268
- refactor(rust): remove gateway, config, router, realtime, and Rust trace-parity instrumentation by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41432
- fix(guardrails): don't add post_call output scan for MCP-only Presidio modes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40571
- chore(prices): sync Azure, Azure AI, Gemini, OpenAI, Bedrock, Together AI, Fireworks and Vertex prices: 278 models, 59
  new, 30 deprecated by @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/41154
- fix(rag): forward retrieval_filter from retrieval_config to vector store search by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/34427
- refactor(rust): extract auth and cache crates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41464
- fix(proxy): default litellm_trace_id to the OTel server span trace id by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41386
- chore(codeowners): add ryan and kerry as owners of the cost map by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41333
- fix(responses): guard empty-choices chunks in the Responses API streaming bridge by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/34455
- chore(prices): sync Google Gemini prices: 22 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/41457
- fix(bedrock): forward userContext in Knowledge Base Retrieve requests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41475
- ci(rust): split rust jobs, use nextest and Swatinem/rust-cache by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41480
- fix(fireworks_ai): flatten dict-form reasoning_effort to its effort string by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41335
- fix(proxy): never forward the LiteLLM virtual key to Anthropic on the /anthropic passthrough by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41340
- fix(proxy): rename AWS Secrets Manager secret when key alias changes by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41468
- feat(otel): promote nested request metadata keys to litellm.metadata.* span attributes by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41462
- fix(proxy): sync AWS Secrets Manager on body-less key regenerate and key alias changes by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41458
- fix(http_handler): keep a handler alive while a response it issued is still reading by @max-sixty in
  https://github.com/BerriAI/litellm/pull/34829
- fix(bedrock): make prompt caching work on the Nova InvokeModel route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41343
- ci(migrations): flag defaulted ADD COLUMN on request-log tables by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41460
- feat(prometheus): add customer (end_user) budget gauges by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41472
- fix(otel): drop None metric and event attributes before OTLP export by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/36815
- fix(anthropic): carry the served model from message_start onto stream chunks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41446
- fix(models): rolling registry audit: Gemini latest aliases, Nova cache pricing, OpenRouter/Together sync, Mistral GLM
  5.3, Azure snapshots, Grok caching by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41112
- fix(router): count TPM/RPM usage before building rate-limit headers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41474
- feat(guardrails): release buffered stream chunks after each passing scan by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41425
- fix!: re-check budget on router fallback targets by @runjivu in https://github.com/BerriAI/litellm/pull/41379
- refactor(ocr): move file preparation from the python bridge into litellm-core by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41489
- feat(s3): add s3_log_prompts_only option to log prompts without responses by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41327
- feat(team): team-level model_max_budget with key-level overrides by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41330
- feat(keys): filter /key/list by active, expired, revoked or deleted status and serve deleted keys from /key/info by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41311
- feat(proxy): expose lifetime total_spend on virtual keys by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41403
- fix(proxy): release completed max-parallel slots promptly by @elifozdamar in
  https://github.com/BerriAI/litellm/pull/40843
- feat(ui): accept ssh clone urls when registering a skill by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/35418
- fix(prices): dedupe Nova cache_read_input_token_cost keys left by a text merge by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41496
- fix(otel): propagate W3C trace context on HTTP and WebSocket passthrough by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40669
- fix(proxy): remove duplicate user budget hook that 429'd zero-cost models by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41345
- test(logging): pick this test's own records out of the shared log batch by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41487
- test(together_ai): move request-shape checks to the mapped file, drop the live ones by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41360
- feat(ui): shared URL-state layer for tables and tabs by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41331
- feat(e2e): make the provider cache reusable across builds and mount Bedrock behind it by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41402
- fix(mcp): fail closed on missing upstream credentials by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/41364
- feat(rust): scaffold Redis cache crate by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41501
- fix(dashscope): forward reasoning_effort to the provider by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/37506
- fix(proxy): carry litellm_call_id through endpoint specific error logs and failure responses by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41356
- fix(proxy): retry rate-limit fallbacks from a pristine request snapshot by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40596
- fix(gemini): map minimal thinking to low for Gemini 3.7 and 3.8 Flash by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41201
- fix(proxy): stop forwarding LiteLLM credential headers on Bedrock agent-runtime passthrough by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41504
- fix(streaming): estimate interrupted Anthropic stream usage from reasoning_content by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41503
- fix(azure_ai): route Responses API to native /openai/v1/responses for Foundry Models by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/33856
- fix(proxy): show all model groups to proxy admins in /model_group/info by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41094
- feat(proxy): let proxy admins choose which team fields team admins may edit by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/39996
- fix(bedrock): neutralize orphaned tool blocks instead of raising or injecting a dummy tool (internal copy of #31400)
  by @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41513
- feat(ui): persist organizations and projects list, detail tab and key table state in the URL by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41445
- fix(bedrock_mantle): accept and forward verbosity on gpt-5.x chat completions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41509
- test: cover database transactions and persisted accounting by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41073
- test: provider wire contracts, streaming and recovery by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41075
- fix(mcp): count admin static headers as api_key credential slots by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41514
- ci: auto-merge provider-info-sync PRs when CI, Greptile and Bugbot are clean by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41494
- feat(rust): add standalone framing crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41500
- fix(proxy): enforce tag budgets for tags added by guardrails by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40842
- fix(utils): run post-call deployment hook on converted chat streams by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41495
- fix(e2e): bind provider-cache recordings to the deployment's test, not the serving process by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41520
- test: add extension and browser integration contracts by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41078
- fix(logging): scan each log record once and collapse base64 payloads before the secret regex by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/40934
- fix(spend_tracking): attribute router-rejected requests to the model group provider by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41507
- feat(router): discover token limits for hosted OpenAI-compatible models by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41508
- feat(proxy): let team admins edit rpm_limit and max_budget when enabled by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41525
- fix(otel): fit per-index OpenInference messages to the span's remaining attribute budget by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41498
- test(aws): verify rotated secret value by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41524
- test(e2e): read a deleted key back as deleted, not as a 404 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41551
- fix(otel v2): map the caller's Langfuse user, session and tags onto the root and generation spans by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41140
- test: fix seven tests left stale by #41311, #41337, #39996, #41310, #41289 and #41315 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41527
- test(budgets): cover management null handling by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41563
- test(e2e): drop the auto-router select "opens below" spec by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41568
- fix(guardrails): stream Prompt Security post_call redactions in incremental_diff mode by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41558
- fix(guardrails): give post-call scans the scoped request conversation and tools by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41220
- feat(openrouter): add stealth/union-alpha to the model cost map by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41576
- test(management): cover project authorization lifecycle by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41573
- feat(rust): map Anthropic Messages transformations by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/41531
- fix(e2e): clear the three standing errors in the scheduled Buildkite suite by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41616
- refactor(rust_bridge): declarative route catalog and shared runtime selection by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41479
- fix(mock_completion): keep the resolved provider so router custom pricing resolves for azure_ai deployments by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41623
- fix(mcp): restrict health discovery to virtual key grants by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/41609
- fix(mcp): preserve request-selected guardrails during tool execution by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/41619
- refactor(ocr): mirror Python provider layout and preserve tests by @yujonglee-berri in
  https://github.com/BerriAI/litellm/pull/41550
- test(fireworks_ai): stop pinning vision support on minimax-m3 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41627
- perf(spend_tracking): index LiteLLM_SpendLogs by (api_key, startTime) by @etiennechabert in
  https://github.com/BerriAI/litellm/pull/37983
- fix(proxy): reject non-string model with 400 and log its spend as unknown-model by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41633
- test(together_ai): stop pinning successor deprecation status by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41635
- chore(prices): sync Together AI prices: 6 models, 6 deprecated [sync failed: Google Gemini] by
  @berriai-litellm-provider-info-sync[bot] in https://github.com/BerriAI/litellm/pull/41570
- fix(budgets): page end-user cache invalidation after a budget reset by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41488
- chore: bump litellm-proxy-extras 0.4.98 -> 0.4.99 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41659
- fix(tests): resolve the integration support package without run.py's PYTHONPATH by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41373
- fix(ui): keep untimed guardrail entries on the request lifecycle by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41374
- fix(anthropic-bridge): convert mid-conversation system turns to user turns on /v1/messages to chat completions by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41493
- fix(bedrock): support aws-sdk-bedrock-runtime 0.10/0.11 in Bedrock Realtime by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41542
- feat(cli): deprecate the litellm-proxy entrypoint in favour of lite by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41673
- fix(scim): align pagination `count` validation with RFC 7644 by @zachbernstein-sdx in
  https://github.com/BerriAI/litellm/pull/41444
- fix(bedrock): never emit Converse cachePoint for OpenAI-family models by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41419
- fix(images): stop forwarding the raw image[] and mask[] form keys by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/39512
- feat(management_v1): bulk update team member budgets by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41632
- refactor(rust): extract provider translations by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41690
- feat(cli): rename lite autoroute up/down to start/stop, keeping the old names as deprecated aliases by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41672
- fix(responses): keep the addressed response id off bridged provider requests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41689
- fix(license): let a wildcard allowed_features license grant the auto_router feature by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41684
- fix(ui): list every provider in the cache leakage by-model table by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40875
- fix(team): keep a forked member budget's reset window and audit bulk member budget writes by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41686
- feat(proxy): add TypeSafe AI Jev evaluate passthrough with registry-priced spend tracking by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41607
- test(e2e): cover bedrock batch file upload and create in the us-gov-west-1 partition by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41536
- feat(grafana): add all-metrics dashboard and fix stale dashboard_v2 gauges by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41578
- fix(cost): price Azure PTU spillover requests at standard token rates by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41569
- build(deps): bump soupsieve to 2.9.2 to clear the osv-scan advisories by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41703
- fix(fireworks_ai): restore supports_vision on minimax-m3 in the cost map by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41699
- feat(policy_engine): explicit priority for policy attachment execution order by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41571
- feat(router): add TypeSafe Jev as a complexity router classifier by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41615
- ci(auto-merge): stop requiring Greptile and Bugbot on price sync pull requests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41678
- fix(ui): persist disabling cache control injection points on model update by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40632
- fix(bedrock): gate Invoke tool search on the model map for Opus 4.8 and gen 5 Claude by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41702
- fix(proxy): propagate db model renames to key, team, org, project and user model allowlists by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41694
- test: delete unit-test assertions that pin cost-map prices, limits and deprecation dates by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41443
- chore(tests): remove commented-out hf, petals and vertex ai completion blocks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41640
- chore(openai): drop commented-out legacy cost_per_token implementation by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41641
- chore(proxy): delete deprecated unused litellm/proxy/_logging.py by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41642
- chore(proxy): remove unreferenced performance_utils profiling module by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41643
- test(streaming): remove commented-out retired-provider streaming tests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41648
- refactor(langfuse): remove unreachable langfuse v1 logging path by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41652
- test: remove 15 fully commented-out test files that collect no tests by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41654
- chore(tests): remove fully commented-out proxy test files and their CI entries by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41660
- refactor(prometheus): remove unreferenced metric validators and pretty printers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41661
- chore(streaming): remove retired ai21/maritalk/baseten/azure raw-bytes handlers and dead palm completion code by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41662
- refactor(vertex_ai): remove constant-False is_using_v1beta1_features stub and its dead call sites by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41665
- fix(passthrough): keep target URL query when client sends no query params by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41448
- fix(responses): drop top_p for gpt-5 reasoning models when drop_params is set by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41469
- fix(ocr): keep a downloaded document inlined when callbacks intercept the request (#41550 follow-up) by @yuneng-berri
  in https://github.com/BerriAI/litellm/pull/41719
- fix(models): rolling registry audit: Azure retirement dates, Bedrock Mantle Grok 4.3 context window by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41597
- test(logging): add azure_spillover to the GCS pub/sub spend-log golden by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41729
- fix(proxy): forward every method on the typesafe pass-through route by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41723
- test(cost_map): stop pinning supports_reasoning absent on the openrouter o1 entry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41734
- fix(model_prices): add cache-read pricing to Mistral chat models missing it by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41736
- refactor(rust): isolate legacy callback contract by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41752
- test(cost_map): drop tests that pin provider-owned catalog values by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41763
- test(e2e/ui): wait for the filtered budget list before clicking a row action by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41756
- chore(prices): sync OpenRouter prices: 443 models, 191 new, 4 deprecated by @berriai-litellm-provider-info-sync[bot]
  in https://github.com/BerriAI/litellm/pull/41727
- fix(batches): bill Bedrock Titan embedding batch lines from inputTextTokenCount by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41767
- fix(proxy): persist only the keys a caller changed in save_config by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41748
- chore(prices): sync OpenRouter prices: 2 models, 1 deprecated by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/41770
- fix(proxy): run prompt injection heuristics off the event loop by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41541
- fix(proxy): evict jwt key mapping cache on user, team, org, and bulk key deletion by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41707
- refactor(ui): remove unused HelpLink and HelpIcon components by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41644
- chore(ui): remove orphaned ROLE_STYLES and RoleStyle from pretty messages view by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41645
- chore(ui): remove never-rendered GuardrailConfig mock component and its test by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41646
- chore(ui): remove unused NewBadge component and its test by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41647
- chore(ui): remove dead compareUI ModelSelector and its test by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41649
- refactor(ui): remove unused createCredentialFromModel helper and CredentialValues interface by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41650
- refactor(ui): drop unused cost-tracking barrel re-exports and response types by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41651
- refactor(ui): drop unused rolesAllowedToSeeUsage, viewOnlyRoles and isViewOnlyRole exports by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41653
- chore(ui): remove unused access-groups type interfaces by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41655
- refactor(ui): remove dead networking exports and orphaned Claude Code marketplace helpers by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41656
- refactor(ui): remove dead useKeyList hook from key_list.tsx by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41657
- chore(ui): remove orphaned useDeleteProject hook and its test by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41658
- refactor(interactions): remove expired use_legacy_interactions_schema shim by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41663
- refactor(rust): align crates with Python package layering by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41829
- chore(prices): sync OpenRouter prices: 15 models, 6 deprecated by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/41772
- refactor(proxy): make the config file win over the database by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41779
- fix(ui): let admins change a model's team from the model edit page by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40700
- fix(ui): show per-second pricing for video models instead of $0.00 token costs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/39308
- fix(cost): bill cache-read tokens at the input rate when the map has no cache-read rate by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41832
- fix(responses): honor nested additional_drop_params paths by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40730
- feat(router): reject with 429 when a deployment's max_parallel_requests slots are all in use by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41555
- perf: defer fastapi and tiktoken BPE imports out of import litellm by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41585
- feat(proxy): add Amazon Transcribe pass-through with completion-time job pricing by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41515
- feat(proxy): per-key default budget for dynamically created customers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41636
- feat(mcp): show live gateway sessions by AI client and user by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41692
- ci: replace the title-similarity duplicate bot with a Codex semantic check by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/40935
- feat(proxy): temporary budget increase for team members by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41620
- feat(vault): add separate login and secret namespaces for HashiCorp Vault by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41539
- feat(vertex_ai): stream GCS batch output files from /v1/files/{id}/content by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41506
- feat(a2a): reach Microsoft Foundry agents with Entra auth and versioned card discovery by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41511
- fix(azure): strip litellm format field from file and image content parts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41275
- ci: classify new issues into domain, provider, kind, priority and lift labels by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41695
- fix(router): validate routing_groups at save time and keep invalid DB groups from blocking SSO load by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41351
- fix(bedrock): send aws_session_tags on every STS call via one typed auth struct by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/40500
- fix(anthropic): register thinking-binding-controls-2026-08-01 in beta headers config by @clonylu in
  https://github.com/BerriAI/litellm/pull/41203
- feat(guardrails): add TypeSafe Jev relevance-based compaction guardrail by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41757
- feat(keys): let team service account keys use key management endpoints for their own team by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/40807
- test(docs): read only the first column of the router_settings reference table by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41860
- fix(scim): accept entitlements and roles entries without a value on SCIM user PUT by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41830
- perf(proxy): split aggregated usage query into key-free rollups and bounded top-N keys by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41293
- chore(deps): bump anyio from 4.13.0 to 4.14.2 by @dependabot[bot] in https://github.com/BerriAI/litellm/pull/41846
- feat(proxy): limit repeated failed Admin UI sign-in attempts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40982
- fix(proxy): make SettingsStore.clear() terminate when the config file owns a key by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41862
- feat(vscode): add LiteLLM language model provider extension by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41865
- feat(mcp): let proxy admins force-close live MCP sessions and revoke stored user credentials by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41725
- feat(models): add qwen3.8 flash rows, fix Cohere embed v3 context, Bedrock Mantle and OpenRouter pricing by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41754
- fix(azure): keep api-version query after vector store search path by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41384
- fix(router): honor stream_timeout on the SDK-native passthrough route (/v1/messages, /converse) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41875
- fix(proxy): track team member spend when the member has no budget by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41349
- feat(proxy): add Azure AI Speech pass-through route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41557
- fix(responses): stop managed Responses WebSocket from leaking litellm_params into provider request body by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/33101
- feat(rust): port exception_type to litellm-core-utils by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41873
- fix(ui): show internal user email in logs table and log detail drawer by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40737
- fix(router): report null cost for unpriced deployments instead of 0 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40878
- feat(azure_ai): support FLUX.2 flex images by @emerzon in https://github.com/BerriAI/litellm/pull/39424
- fix(mistral): accept reasoning_effort on all models and drop client_metadata for Codex compatibility by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41062
- feat(passthrough): deepgram streaming /v1/listen WebSocket passthrough with duration-based cost tracking by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41554
- test(ocr): declarative provider x auth x input matrix, fix Rust 401 mapping by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41884
- fix(proxy): classify Azure Speech short audio behind a prefixed api base by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41882
- feat(proxy): add LiteLLM_DailyGlobalSpend key-free rollup for the usage dashboard by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41324
- fix(proxy): keep requested model guardrails and key disable_fallbacks on rate-limit fallback by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41783
- fix(bedrock): carry s3_endpoint_url and s3_region_name into file content downloads by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41138
- ci(duplicate-check): let Codex reach GitHub from its sandbox by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41883
- fix(proxy): resolve model_group_alias to its target for /v1/models metadata by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41483
- fix(proxy): reset sibling tpm/rpm counters when the shared rate limit window rolls over by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41838
- feat(ui): link MCP Servers page to the user's connected MCP servers by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41888
- fix(proxy): name the blocking guardrail in x-litellm-applied-guardrails by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41583
- fix(responses): merge deployment litellm_params into native websocket response.create frames by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41881
- feat: honor eager_input_streaming on Bedrock and Anthropic Claude tools by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41871
- fix(otel): keep caller traceparent and tracestate on pass-through relays by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41786
- ci: remove the dead Agent Shin triage workflows and scripts by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41894
- fix: set vertex gemma-4-26b-a4b-it-maas context window to 262144 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41887
- refactor(rust): formalize legacy callback contract by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41885
- fix(gemini): preserve candidates with finishReason and no content (#40477) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41892
- fix(team): apply team_member_budget updates to members still on the team default by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41347
- fix(enterprise): resolve openai_moderations model at call time and default to omni-moderation-latest by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41895
- fix(proxy): track project spend and enforce project budgets additively by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41354
- fix(proxy): refuse config-owned keys on POST /config/update by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41868
- test(integration): cover off-peak pricing on a live proxy by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41901
- fix(proxy): requeue daily spend rows when the commit fails without the Redis buffer by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41878
- fix(responses): emit typed streaming failure events by @zoroyihan7 in https://github.com/BerriAI/litellm/pull/40243
- fix(bedrock): clamp maxTokens to the 16-token minimum for OpenAI GPT and xAI Grok models on Converse by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41870
- chore(model_info): backfill reseller Gemini entries from provider catalogs and prune retired ids by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41902
- feat(mcp): allowlist MCP client applications at the gateway by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41667
- fix(schema): classify off_peak_pricing as a structured object in the model prices schema generator by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41847
- fix(rate_limiter): render the 429 reset time in UTC as labelled by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41911
- ci(issues): comment which release carries the fix when a pull request closes an issue by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41910
- feat(proxy): let team admins manage projects via team_admin_editable_team_fields by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41916
- fix(bedrock): sign batch retrieve and cancel with deployment credentials when AWS_BEARER_TOKEN_BEDROCK is set by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41904
- fix(websearch_interception): surface a failed search as a web_search_tool_result_error block and end the turn by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41905
- fix(cost_calc): default fireworks cached input to the documented 50% discount when the map has no cache-read rate by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41917
- fix(timing): anchor response duration and overhead at proxy receive time by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41891
- feat(xai): add speech-to-text (Grok Voice Transcribe) via /v1/audio/transcriptions by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41914
- feat(rust): add litellm-http client pool and inject it into the OCR route by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41897
- feat(vertex_ai): stream Chirp speech-to-text over /v1/realtime by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41721
- chore: consolidate CLAUDE.md into AGENTS.md by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41921
- feat(proxy): serve the Claude Code gateway protocol under /claude_code_gateway by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/34267
- fix(responses): restore encrypted_content and apply affinity on the native WebSocket relay by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41893
- feat(proxy): add RFC 8693 token exchange for IdP JWTs on the gateway token endpoint by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41485
- fix(websearch): forward the deployment api_base to agentic follow-up calls on /v1/messages by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41918
- fix(proxy): parse role_permissions where it is read by @yuneng-berri in https://github.com/BerriAI/litellm/pull/41924
- fix(responses): announce message item before text events in the chat completions bridge by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41564
- fix(proxy): unpin cost-map pricing copied into model_info and report pricing overrides by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41843
- feat(websearch): let the model emit objective + multi-query search shapes by @adssoccer1 in
  https://github.com/BerriAI/litellm/pull/40399
- fix(exceptions): keep internal_server_error as the public type of an upstream 500 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41930
- fix(proxy): dispatch llm_api_check moderation through during_call_hook by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41685
- fix(policy_engine): deliver guardrail text rewrites on multi-choice, unfinished, and envelope-less streams by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41933
- fix(anthropic): keep cache_control for Gemini targets on /v1/messages and normalize Anthropic ttl units by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41938
- fix(guardrails): stop the Javelin api_version default leaking into Azure Content Safety by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41941
- fix(alerting): clarify budget threshold messages by @gaurav-pandey-zocdoc in
  https://github.com/BerriAI/litellm/pull/39102
- fix(cost): carry image and video input tokens through the Responses usage bridge (internal copy of #36887) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41237
- ci(unit): fail a hung test in 120s with a traceback instead of idling the shard to its step timeout by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41948
- refactor(types): replace Any with proven types in 6 files by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41947
- fix(proxy): register transcribe as a known provider for model grants by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41926
- feat(batches): support Mistral files/batches and per-page OCR batch cost tracking (internal copy of #40484) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41934
- fix(utils): reject an untranslatable tool_choice with a 400 instead of a 500 by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41234
- fix(proxy): keep request metadata out of the cost tracking failure alert by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41950
- fix(masker): memoize shared nodes and fail closed past the depth cap by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41952
- fix(responses): drop tool_search and local_shell in the chat completions bridge by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41953
- fix(rag): resolve registry stores on /v1/rag/ingest and reject providers without ingestion by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41940
- fix(azure): send the resolved Entra ID token on image generation requests by @abhirup7 in
  https://github.com/BerriAI/litellm/pull/40147
- fix(proxy): keep the raw client model out of spend logs for rejections outside the router by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41943
- fix(cost): resolve dated openai/azure snapshots to their undated cost map entry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41423
- fix(proxy): /key/bulk_update writes only the fields each item carries by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41949
- fix(cost): bill DeepSeek V4.1 Flash and V4 Pro at off-peak rates outside peak hours by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41960
- test(cost): point dated snapshot tests at a date the cost map cannot carry by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41971
- fix(proxy): refuse runtime writes to config-owned settings by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41931
- refactor(rust): centralize layered settings resolution by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41969
- test(utils): isolate dated model fallback from pricing additions by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/41975
- test(response_metadata): anchor detailed-timing test on a fixed instant instead of wall clock by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41946
- test(integration): literal request/response cost tracking suite on a test-owned cost map by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41328
- chore(prices): sync Azure prices: 5 models, 5 deprecated by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/41966
- feat(ocr): add Rust-only Textract and sign provider requests after host hooks by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41977
- refactor(rust): use typed pyo3 APIs instead of getattr/import strings by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41981
- fix(router): enforce model tpm limits against shared redis usage across replicas by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41915
- feat(proxy): say when a stored setting is ignored because the config file owns it by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/41985
- fix(otel v2): summarize embedding vectors as Langfuse observation output by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41982
- fix(caching): scope automatic breakpoints to supported Claude transports by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41920
- fix(proxy): return 400 instead of 500 for /v1/responses without input by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41939
- fix(llmguard): accept proxy async call types by @yucheng-berri in https://github.com/BerriAI/litellm/pull/41787
- fix(model_prices): drop anthropic deprecation floors and correct azure gpt-4.1-nano retirement date by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41964
- fix(ui): show user attribution in Top Virtual Keys usage tables by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/40729
- chore(prices): sync OpenRouter prices: 172 models, 2 new by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/41833
- fix(ocr): set DeepSeek OCR sampling defaults by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41992
- ci: remove auto-merge-price-sync workflow, the Devin sync automation merges price PRs by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41993
- refactor(mcp): upgrade SDK2 while preserving legacy gateway behavior by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/41718
- revert(guardrails): drop the scoped request conversation and tools from post-call scans (#41220) by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41986
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/41996
- test(unified_google_tests): use the Vertex global endpoint and retry 429s with backoff by @devin-ai-integration[bot]
  in https://github.com/BerriAI/litellm/pull/41995
- fix(rust): refuse native routes in processes forked after the runtime started by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41987
- fix(terraform): unlink the registry docs entries that 404 on click by @shivamrawat1 in
  https://github.com/BerriAI/litellm/pull/42003
- fix(otel v2): map Responses API output onto the Langfuse generation output by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41991
- test(e2e): stop the config suite locking itself out of the shared proxy by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42008
- chore: bump litellm-enterprise 0.1.68 -> 0.1.69, litellm-proxy-extras 0.4.99 -> 0.4.100 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42025
- fix(proxy): close the config-ownership gaps QA found in the settings store by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42009
- fix(proxy): block project requests when max_budget is 0 by @ryan-crabbe-berri in
  https://github.com/BerriAI/litellm/pull/41997
- fix(auth): inherit org alias, budget and rate limits for JWT and team-linked keys by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41681
- feat(batches): run hosted_vllm batches inside LiteLLM by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41942
- fix(proxy): forward stream response attributes through the hook boundary and merge logged applied_guardrails by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42027
- feat(ui): configure web search interception from the Admin UI by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42007
- fix(azure): drop tool_choice when the request has no tools (internal copy of #41781) by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42031
- fix(azure): tool choice without tools causes 400 by @dsteeley in https://github.com/BerriAI/litellm/pull/41781
- test(mcp): verify scoped execution and OAuth credential isolation by @joshua-berri in
  https://github.com/BerriAI/litellm/pull/41731
- test(e2e): cover MCP OAuth SSO and cold restart persistence by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/41909
- fix(proxy): estimate auto-router baseline costs from durable cache history by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41177
- fix(auto-router): show heuristic v2 score estimates in routing details by @tin-berri in
  https://github.com/BerriAI/litellm/pull/42001
- feat(router): add maintained Fuse model and harness presets by @tin-berri in
  https://github.com/BerriAI/litellm/pull/41617
- refactor(rust): rename legacy callback adapter crate by @devin-ai-integration[bot] in
  https://github.com/BerriAI/litellm/pull/42037
- Revert "test(mcp): verify scoped execution and OAuth credential isolation" by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/42039
- revert(e2e): remove MCP OAuth SSO and cold restart tests by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/42040
- test(mcp): cover SDK redirect compatibility by @joshua-berri in https://github.com/BerriAI/litellm/pull/42033
- feat(ui): report whether the serving proxy has applied web search interception by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42042
- fix(test): unbreak the integration-cost and proxy_e2e_anthropic_messages CircleCI jobs on main by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/42048
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42006
- feat(otel v2): opt-in llm_only span scope for Langfuse destinations and the operator Langfuse exporter by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41740
- test(e2e): point the Nova Sonic realtime test at nova-2-sonic by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42053
- fix(team): emit audit events for member_delete and role changes and carry the final roster on team create by
  @devin-ai-integration[bot] in https://github.com/BerriAI/litellm/pull/41840
- chore(prices): sync OpenRouter prices: 5 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42058
- chore(prices): sync OpenRouter prices: 2 models by @berriai-litellm-provider-info-sync[bot] in
  https://github.com/BerriAI/litellm/pull/42063
- chore: rebuild Admin UI bundle from main (build kXnLzJ6ylsRPmgSkCkCKM) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42054
- test(mcp): migrate the mcp test helpers to the mcp 2.x MCPServer API by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42075
- test(logging): add autorouter estimate keys to the GCS pub/sub spend-log golden by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42076
- test(batches): skip the Bedrock GovCloud batch e2e until its secrets are provisioned by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/42081
- fix(bedrock): backport the /v1/messages Invoke streaming pass-through to rc/1.103.0 (#42607) by @mateo-berri in
  https://github.com/BerriAI/litellm/pull/42658
- revert(usage): remove the top-N key cap and global spend rollup code from rc/1.103.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43326
- fix(proxy): backport team member spend jsonb flush to rc/1.103.0 (#43029) by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43323
- fix: backport five regression fixes to rc/1.103.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43331
- chore: rebuild Admin UI bundle for rc/1.103.0 by @yuneng-berri in https://github.com/BerriAI/litellm/pull/43328
- fix(jwt,otel): backport session conversation id and JWT team header selection to rc/1.103.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43343
- fix(caching): stand default cache points down when extra_body hides a direct client mark by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43342
- test(integration): make rc/1.103.0 integration groups collect and pass again by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43382
- test(e2e): clear the two rc/1.103.0 e2e reds owned by upstream providers by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43388
- test(ci): fix the e2e and integration reds left on rc/1.103.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43391
- fix(streaming): backport text-completion usage fix and e2e provider-flake tolerance to rc/1.103.0 by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43400
- fix(proxy): unregister logging callbacks removed from the stored config by @yuneng-berri in
  https://github.com/BerriAI/litellm/pull/43429

## New Contributors

- @joshgarnett made their first contribution in https://github.com/BerriAI/litellm/pull/36363
- @HUAHAODIA made their first contribution in https://github.com/BerriAI/litellm/pull/41048
- @rad-p44 made their first contribution in https://github.com/BerriAI/litellm/pull/40315
- @AaronHowell made their first contribution in https://github.com/BerriAI/litellm/pull/40228
- @MvdB made their first contribution in https://github.com/BerriAI/litellm/pull/36775
- @IToSSc made their first contribution in https://github.com/BerriAI/litellm/pull/41179
- @max-sixty made their first contribution in https://github.com/BerriAI/litellm/pull/34829
- @runjivu made their first contribution in https://github.com/BerriAI/litellm/pull/41379
- @elifozdamar made their first contribution in https://github.com/BerriAI/litellm/pull/40843
- @etiennechabert made their first contribution in https://github.com/BerriAI/litellm/pull/37983
- @zachbernstein-sdx made their first contribution in https://github.com/BerriAI/litellm/pull/41444
- @clonylu made their first contribution in https://github.com/BerriAI/litellm/pull/41203
- @zoroyihan7 made their first contribution in https://github.com/BerriAI/litellm/pull/40243
- @adssoccer1 made their first contribution in https://github.com/BerriAI/litellm/pull/40399
- @gaurav-pandey-zocdoc made their first contribution in https://github.com/BerriAI/litellm/pull/39102
- @abhirup7 made their first contribution in https://github.com/BerriAI/litellm/pull/40147

**Full Changelog**: https://github.com/BerriAI/litellm/compare/v1.102.0...v1.103.0

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
