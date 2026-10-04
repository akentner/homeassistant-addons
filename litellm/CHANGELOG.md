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
