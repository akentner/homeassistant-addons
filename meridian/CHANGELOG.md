## [1.62.5](https://github.com/rynfar/meridian/compare/meridian-v1.62.4...meridian-v1.62.5) (2026-08-17)

### Bug Fixes

- route native subagents to base model tiers ([#839](https://github.com/rynfar/meridian/issues/839))
  ([91aeaf5](https://github.com/rynfar/meridian/commit/91aeaf56d6d220a4cd01fc0bfebe5dfd486e7b90))

## [1.62.3](https://github.com/rynfar/meridian/compare/meridian-v1.62.2...meridian-v1.62.3) (2026-08-17)

### Bug Fixes

- **concurrency:** follow env changes for the shared SDK semaphore budget
  ([e40ff28](https://github.com/rynfar/meridian/commit/e40ff2853732b2853bfc28bbf85064fda0f9959f))

## [1.62.1](https://github.com/rynfar/meridian/compare/meridian-v1.62.0...meridian-v1.62.1) (2026-08-15)

### Bug Fixes

- **concurrency:** stop internal dispatch hops from taking a second queue slot
  ([#813](https://github.com/rynfar/meridian/issues/813))
  ([32ccab8](https://github.com/rynfar/meridian/commit/32ccab8a33ab2535cad529a1cf430187cb87caf2))
- **passthrough:** stop announcing a truncated turn as a clean finish
  ([#801](https://github.com/rynfar/meridian/issues/801))
  ([7c83f2b](https://github.com/rynfar/meridian/commit/7c83f2b10ff5c8dc4ed62ca96f12c1985570329d))
- **plugins:** derive the known-adapter list from the registry ([#814](https://github.com/rynfar/meridian/issues/814))
  ([226232d](https://github.com/rynfar/meridian/commit/226232d573b060c5a19f6eac38286e7f0bdd6137))
- **session:** retry a refused resume before abandoning the session
  ([#811](https://github.com/rynfar/meridian/issues/811))
  ([cb6fe0c](https://github.com/rynfar/meridian/commit/cb6fe0c6bff5188ab7e089d8bd481a62d0f719c0))

## [1.61.0](https://github.com/rynfar/meridian/compare/meridian-v1.60.0...meridian-v1.61.0) (2026-08-11)

### Features

- Hermes Agent integration example plugin + docs ([#762](https://github.com/rynfar/meridian/issues/762))
  ([8b789e4](https://github.com/rynfar/meridian/commit/8b789e4e491c31ec79737cb18dd9c79666496f20))

### Bug Fixes

- **errors:** recognize the CLI's other limit wordings ([#788](https://github.com/rynfar/meridian/issues/788))
  ([697a618](https://github.com/rynfar/meridian/commit/697a61881dc85bffc237be57f0d2cd5c08ac5a98))
- keep Jcode chat sessions cache-affine ([#784](https://github.com/rynfar/meridian/issues/784))
  ([3bdc7d0](https://github.com/rynfar/meridian/commit/3bdc7d0f973610246771b683b9960ab44a662641))
- **passthrough:** never leave a passthrough continuation unanswered
  ([#793](https://github.com/rynfar/meridian/issues/793))
  ([2852159](https://github.com/rynfar/meridian/commit/28521591060c368a0fc1ce48f7ecd90da675a5f3))
- **quota:** back off OAuth usage rate limits ([#785](https://github.com/rynfar/meridian/issues/785))
  ([128d87d](https://github.com/rynfar/meridian/commit/128d87df0502ffca947a85b114d022638e7db764))
- **quota:** distinguish a rate-limited usage fetch from a missing token
  ([#786](https://github.com/rynfar/meridian/issues/786))
  ([d82da9f](https://github.com/rynfar/meridian/commit/d82da9fbf9ec008278f3b257d33496f8df0ca679))
- **usage:** report why a usage fetch failed instead of calling every failure no_token
  ([#789](https://github.com/rynfar/meridian/issues/789))
  ([7c8d2b4](https://github.com/rynfar/meridian/commit/7c8d2b414edf46b670f99f08c341b4c2b889e580))

> ### ⚠️ Behaviour change: claude.ai connectors are now off by default
>
> If your claude.ai account has connectors attached (Drive, Gmail, Calendar), they previously loaded for any adapter
> **not** in passthrough mode. As of 1.60.0 they require an explicit opt-in at `/settings` → **claude.ai Connectors**.
>
> **Affected:** `cherry`, `droid`, and any deployment running `MERIDIAN_PASSTHROUGH=0`. **Not affected:** `opencode` and
> other passthrough-default adapters — connectors were already disabled for them.
>
> Nothing errors when this bites. The model simply no longer has the tool and answers as though the data were
> unavailable, so a lost capability is easy to misread as the model being unhelpful. See
> [claude.ai connectors](https://github.com/rynfar/meridian/blob/main/docs/configuration.md#claudeai-connectors).

## [1.60.0](https://github.com/rynfar/meridian/compare/meridian-v1.59.0...meridian-v1.60.0) (2026-08-04)

### Features

- gate claude.ai connectors behind an opt-in flag ([#759](https://github.com/rynfar/meridian/issues/759))
  ([370c286](https://github.com/rynfar/meridian/commit/370c286cbfbaa2e31dafa2a8222bd344944a4766))

### Bug Fixes

- don't treat transport metadata as a system instruction ([#758](https://github.com/rynfar/meridian/issues/758))
  ([59931d0](https://github.com/rynfar/meridian/commit/59931d0e09e2c1f51a33064bfa433cc2db785583))

## [1.59.0](https://github.com/rynfar/meridian/compare/meridian-v1.58.3...meridian-v1.59.0) (2026-08-04)

### Features

- add webFetchPreflight toggle, scoped to the adapter it affects ([#752](https://github.com/rynfar/meridian/issues/752))
  ([e2aa19f](https://github.com/rynfar/meridian/commit/e2aa19ff77f7695dffaf959e4fc7da3da1b73a9b)), closes
  [#748](https://github.com/rynfar/meridian/issues/748)
- quiet the subprocess's non-essential outbound traffic ([#757](https://github.com/rynfar/meridian/issues/757))
  ([63a5301](https://github.com/rynfar/meridian/commit/63a530151da0909dba061ff6d6c61c13b53e2d90))

## [1.58.3](https://github.com/rynfar/meridian/compare/meridian-v1.58.2...meridian-v1.58.3) (2026-08-03)

### Bug Fixes

- **cwd:** use the client's directory as the SDK cwd when it exists locally
  ([#746](https://github.com/rynfar/meridian/issues/746))
  ([f16e2a6](https://github.com/rynfar/meridian/commit/f16e2a6846be834cdddceb1756713ccc27f91d35)), closes
  [#744](https://github.com/rynfar/meridian/issues/744)
- **passthrough:** defer early stop while a tool_use block is still streaming
  ([#745](https://github.com/rynfar/meridian/issues/745))
  ([46e55dc](https://github.com/rynfar/meridian/commit/46e55dce5234e858710459c94462c4add371f87d)), closes
  [#742](https://github.com/rynfar/meridian/issues/742)
- **pi:** read the session identity OMP carries in metadata.user_id
  ([#747](https://github.com/rynfar/meridian/issues/747))
  ([e41019b](https://github.com/rynfar/meridian/commit/e41019bd4c5a16625cd5d2105529c68915395f57)), closes
  [#734](https://github.com/rynfar/meridian/issues/734)
- register claude-code transforms so tool calls pass through ([#743](https://github.com/rynfar/meridian/issues/743))
  ([94ba52f](https://github.com/rynfar/meridian/commit/94ba52fb388728b7f36250ece0391e00a7316493))
- **sanitize:** stop a self-closing tag swallowing text up to the next paired tag
  ([#736](https://github.com/rynfar/meridian/issues/736))
  ([0f20bfd](https://github.com/rynfar/meridian/commit/0f20bfdfc0075546fd9933250b46cb525acb4f1a)), closes
  [#722](https://github.com/rynfar/meridian/issues/722)
- **sanitize:** strip Meridian's own markers from assistant content on replay
  ([#738](https://github.com/rynfar/meridian/issues/738))
  ([f19cf48](https://github.com/rynfar/meridian/commit/f19cf4834e9252cc27e0487dbce9dbc0a8ad754c)), closes
  [#724](https://github.com/rynfar/meridian/issues/724)

## [1.58.2](https://github.com/rynfar/meridian/compare/meridian-v1.58.1...meridian-v1.58.2) (2026-07-30)

### Bug Fixes

- **adapters:** stop x-session-affinity misrouting Crush to the OpenCode adapter
  ([#733](https://github.com/rynfar/meridian/issues/733))
  ([1878ef8](https://github.com/rynfar/meridian/commit/1878ef86aedac17b88b6d342b4dffa1cc112e2cd))
- **errors:** target the extended-context hint at the tier that failed
  ([#730](https://github.com/rynfar/meridian/issues/730))
  ([a453f66](https://github.com/rynfar/meridian/commit/a453f669aabfb260c6f666fcc9975dd0be653b26)), closes
  [#716](https://github.com/rynfar/meridian/issues/716)
- **routing:** normalize SDK reset timestamps to epoch milliseconds
  ([#727](https://github.com/rynfar/meridian/issues/727))
  ([0660815](https://github.com/rynfar/meridian/commit/06608151e99cb9198cb14fadca359e7b9835d63c)), closes
  [#708](https://github.com/rynfar/meridian/issues/708)
- **routing:** skip OAuth usage refinement for non-claude-max profiles
  ([#729](https://github.com/rynfar/meridian/issues/729))
  ([8610d20](https://github.com/rynfar/meridian/commit/8610d20865d18749e9a8ddec9ef03fa047100004)), closes
  [#699](https://github.com/rynfar/meridian/issues/699)
- **session:** ignore thinking blocks in the lineage hash ([#731](https://github.com/rynfar/meridian/issues/731))
  ([5c419bd](https://github.com/rynfar/meridian/commit/5c419bd19c20187f865dec9c26105f7a52d1f32d)), closes
  [#710](https://github.com/rynfar/meridian/issues/710)

## [1.58.1](https://github.com/rynfar/meridian/compare/meridian-v1.58.0...meridian-v1.58.1) (2026-07-29)

### Bug Fixes

- **query:** correct the preset's false gitStatus provenance claim
  ([#726](https://github.com/rynfar/meridian/issues/726))
  ([8ce601b](https://github.com/rynfar/meridian/commit/8ce601babef481a4d168367cb14cb6586f3d4824)), closes
  [#694](https://github.com/rynfar/meridian/issues/694)
- **sanitize:** make &lt;thinking&gt; stripping opt-in ([#721](https://github.com/rynfar/meridian/issues/721))
  ([15f6eb5](https://github.com/rynfar/meridian/commit/15f6eb5c10689d28e136be8e947b86decd3797ff))

## [1.57.1](https://github.com/rynfar/meridian/compare/meridian-v1.57.0...meridian-v1.57.1) (2026-07-28)

### Bug Fixes

- give keyless conversations priority-pool affinity ([#704](https://github.com/rynfar/meridian/issues/704))
  ([fcec079](https://github.com/rynfar/meridian/commit/fcec079e2f519de7dd65f553941835a765cf3aac))
- make postinstall script Windows-portable
  ([ac8244b](https://github.com/rynfar/meridian/commit/ac8244bdf642618070917511363cd659bdc2a6f0))
- make postinstall script Windows-portable
  ([379e0c9](https://github.com/rynfar/meridian/commit/379e0c9d118c063452715f805a0d65e8c641b3e5))
- replay stale session histories safely + lineage safety harness ([#705](https://github.com/rynfar/meridian/issues/705))
  ([9aa8aff](https://github.com/rynfar/meridian/commit/9aa8affb07ce5c4e051a496efc5379eb9be0b456))
- **responses:** harden typeless-item handling against malformed input
  ([3c94acd](https://github.com/rynfar/meridian/commit/3c94acd40a6b82e4d68010da4ee892e2b145184b))
- **responses:** treat input items without a type as messages
  ([013f85d](https://github.com/rynfar/meridian/commit/013f85d48a30a5b396601eba24c9dc87a04739ca))
- **responses:** treat input items without a type as messages
  ([c8a37d0](https://github.com/rynfar/meridian/commit/c8a37d01437679bc66e433801fcd5d7785b57782))
- scope rate-limit store per profile so priority cooldowns use the right account's reset
  ([#697](https://github.com/rynfar/meridian/issues/697))
  ([1cd557c](https://github.com/rynfar/meridian/commit/1cd557c442025cf7ac003c0c79f05d0797dd47a6))
- **session:** bound modified-continuation resume so stale lineage replays fresh
  ([6b61e66](https://github.com/rynfar/meridian/commit/6b61e66ac2bce14364b435d5d9bc80e9bcaf88f5))
- **session:** bound modified-continuation resume so stale lineage replays fresh
  ([141eab5](https://github.com/rynfar/meridian/commit/141eab58009dbedb9a41ae904d61eec9e960c5d0)), closes
  [#689](https://github.com/rynfar/meridian/issues/689)
- **settings:** isolate tests from the developer's real settings file
  ([#703](https://github.com/rynfar/meridian/issues/703))
  ([2a30a8c](https://github.com/rynfar/meridian/commit/2a30a8c3d6b1eb4b854c85785d2c46d1d73b9bd4))
- surface claude-code postinstall output instead of silencing it
  ([301cc5c](https://github.com/rynfar/meridian/commit/301cc5ca91dec9efd95049a7b830cd950f6f0289))

## [1.57.0](https://github.com/rynfar/meridian/compare/meridian-v1.56.1...meridian-v1.57.0) (2026-07-24)

### Features

- add Claude Opus 5 to the model list, make it the canonical opus
  ([f0c885c](https://github.com/rynfar/meridian/commit/f0c885c53ec027eafb8f70bf5d68889971f464c7))
- add Claude Opus 5 to the model list, make it the canonical opus
  ([87cfcda](https://github.com/rynfar/meridian/commit/87cfcdadf24c0e64ef08e2ee81fc5d8debc2bfea))
- image input and incomplete status for Responses API (/v1/responses)
  ([37fb773](https://github.com/rynfar/meridian/commit/37fb773744196d72d0c153f0cf693461572617ce))
- support image input and incomplete status in Responses API
  ([92745e0](https://github.com/rynfar/meridian/commit/92745e0cee278bfc70f5bc698e2aa5d50fdae85d))

## [1.56.1](https://github.com/rynfar/meridian/compare/meridian-v1.56.0...meridian-v1.56.1) (2026-07-23)

### Bug Fixes

- **ui:** restore the visual pace bar on account cards ([#681](https://github.com/rynfar/meridian/issues/681))
  ([e7117de](https://github.com/rynfar/meridian/commit/e7117de55263d156f8c4f36c1ca182fb0b552ab4))

## [1.55.1](https://github.com/rynfar/meridian/compare/meridian-v1.55.0...meridian-v1.55.1) (2026-07-23)

### Bug Fixes

- never rename a subagent_type that is already a registered agent
  ([#672](https://github.com/rynfar/meridian/issues/672))
  ([c72f91f](https://github.com/rynfar/meridian/commit/c72f91f723c50b0bd7a90e1351f72558f3b3a6a2)), closes
  [#671](https://github.com/rynfar/meridian/issues/671)

## [1.55.0](https://github.com/rynfar/meridian/compare/meridian-v1.54.0...meridian-v1.55.0) (2026-07-21)

### Features

- **codex:** resume SDK sessions across turns via prompt_cache_key
  ([#655](https://github.com/rynfar/meridian/issues/655)) ([#665](https://github.com/rynfar/meridian/issues/665))
  ([84cbdc5](https://github.com/rynfar/meridian/commit/84cbdc5e06bbff2bf588b5d0075378590d560337))
- install plugins in Docker via MERIDIAN_PLUGINS
  ([dd6e8d3](https://github.com/rynfar/meridian/commit/dd6e8d39753abf9abddae7f48d5f306bf0829cff))
- install plugins in Docker via MERIDIAN_PLUGINS ([#668](https://github.com/rynfar/meridian/issues/668) + fix-ups)
  ([9dcb3d3](https://github.com/rynfar/meridian/commit/9dcb3d337114f9dd803e994cdb4827fd74fe5e0c))

### Bug Fixes

- **docker:** anchor the plugin install root, harden failure paths
  ([9ce7dd9](https://github.com/rynfar/meridian/commit/9ce7dd9ba56d67e458f1e6d1af97d9e1d7af7717))
- explicit session keys override the fork/subagent independence guard
  ([#669](https://github.com/rynfar/meridian/issues/669))
  ([b46e08e](https://github.com/rynfar/meridian/commit/b46e08ed5358c6738e73362fd483524b6b1ef7b7))

## [1.54.0](https://github.com/rynfar/meridian/compare/meridian-v1.53.0...meridian-v1.54.0) (2026-07-19)

### Features

- Claude Design MCP proxy (/v1/design/\*) with dedicated OAuth flow
  ([e1547c3](https://github.com/rynfar/meridian/commit/e1547c3625b486bfcd1864c848babc3098719f28))
- Claude Design MCP proxy (/v1/design/\*) with dedicated OAuth flow
  ([#543](https://github.com/rynfar/meridian/issues/543))
  ([1963c94](https://github.com/rynfar/meridian/commit/1963c94669eaa7821d7f449b195b638c653dfd67))

### Bug Fixes

- **mcp:** stop shell-interpolating grep tool input, treat exit 1 as no matches
  ([05513c4](https://github.com/rynfar/meridian/commit/05513c451725ce75865dfeae4f1dc1b756e17119))

## [1.52.0](https://github.com/rynfar/meridian/compare/meridian-v1.51.0...meridian-v1.52.0) (2026-07-17)

### Features

- add Sonnet 5 to the model list, make it the canonical sonnet ([#631](https://github.com/rynfar/meridian/issues/631))
  ([#644](https://github.com/rynfar/meridian/issues/644))
  ([b1cde57](https://github.com/rynfar/meridian/commit/b1cde574e78b39de7118f356d302da974c99e7ae))
- **cli:** read MERIDIAN_PLUGIN_DIR and MERIDIAN_PLUGIN_CONFIG env vars
  ([59743bd](https://github.com/rynfar/meridian/commit/59743bdf586ede60e08642df1e505f2bf157fcbf))
- env-configurable plugin loading + home-manager plugin settings ([#623](https://github.com/rynfar/meridian/issues/623)
  by [@connor-grady](https://github.com/connor-grady))
  ([b40bfba](https://github.com/rynfar/meridian/commit/b40bfba577b8a5a777f30e1b5f33cde554e05e1b))
- **nix:** add pluginConfig and pluginDir home-manager settings
  ([5cb1821](https://github.com/rynfar/meridian/commit/5cb18211634acd32d1efef38c24d1813791966e1))

### Bug Fixes

- decouple SDK settings from settingSources so memory:false works with claudeMd off
  ([#634](https://github.com/rynfar/meridian/issues/634)) ([#645](https://github.com/rynfar/meridian/issues/645))
  ([379bd6b](https://github.com/rynfar/meridian/commit/379bd6bfa62f96ce1a6f02416aa15f6de421fbd8))
- frame fresh-session replays in a context-only envelope ([#619](https://github.com/rynfar/meridian/issues/619))
  ([#646](https://github.com/rynfar/meridian/issues/646))
  ([ce1f954](https://github.com/rynfar/meridian/commit/ce1f9543a94222c08fbfc548c2889f737ebf6b94))
- hold non-stream denies until turn end — parallel calls survive both modes
  ([#592](https://github.com/rynfar/meridian/issues/592)) ([#647](https://github.com/rynfar/meridian/issues/647))
  ([0d50467](https://github.com/rynfar/meridian/commit/0d50467e4c05e9b127b0f6ba8883f3d01625b2b9))
- **nix:** only export MERIDIAN_PLUGIN_CONFIG when plugins are configured
  ([f241032](https://github.com/rynfar/meridian/commit/f241032fa25929b899ac4d1819302bbd5c297062))
- retry busy-session resume refusals instead of failing deterministically
  ([#630](https://github.com/rynfar/meridian/issues/630)) ([#643](https://github.com/rynfar/meridian/issues/643))
  ([81b589c](https://github.com/rynfar/meridian/commit/81b589c654d7f640e308a079ab45aececf7ae884))

## [1.50.0](https://github.com/rynfar/meridian/compare/meridian-v1.49.1...meridian-v1.50.0) (2026-07-16)

### Features

- **telemetry:** envelope-integrity tripwires for wire-contract violations
  ([#632](https://github.com/rynfar/meridian/issues/632))
  ([4f8db58](https://github.com/rynfar/meridian/commit/4f8db589e1be65e0c83476e6c9926bebbf84c135))

### Bug Fixes

- **passthrough:** hold denies until generation completes ([#552](https://github.com/rynfar/meridian/issues/552)
  streaming red reads) ([#625](https://github.com/rynfar/meridian/issues/625))
  ([df48e3b](https://github.com/rynfar/meridian/commit/df48e3b9f0a374ee4e30665ee10add17da77e98e))
- **passthrough:** suppress the SDK subprocess's scratchpad advertisement
  ([#627](https://github.com/rynfar/meridian/issues/627)) ([#628](https://github.com/rynfar/meridian/issues/628))
  ([18d6b24](https://github.com/rynfar/meridian/commit/18d6b24da8c12a649df852027427d679fcc89fcb))

## [1.49.1](https://github.com/rynfar/meridian/compare/meridian-v1.49.0...meridian-v1.49.1) (2026-07-14)

### Bug Fixes

- **passthrough:** capture parallel same-tool calls instead of dropping them
  ([#620](https://github.com/rynfar/meridian/issues/620))
  ([f732658](https://github.com/rynfar/meridian/commit/f7326582a3ecf5c79ca9cdcc509bd39c3d88b406))
- **passthrough:** strip hook-dropped tool calls from the client response
  ([#622](https://github.com/rynfar/meridian/issues/622))
  ([141bee0](https://github.com/rynfar/meridian/commit/141bee01270d07e09667aea0c3b7a0770b849aff))

## [1.49.0](https://github.com/rynfar/meridian/compare/meridian-v1.48.1...meridian-v1.49.0) (2026-07-13)

### Features

- **adapters:** named adapter instances with per-instance config ([#616](https://github.com/rynfar/meridian/issues/616))
  ([fcc1d3e](https://github.com/rynfar/meridian/commit/fcc1d3ebb54d12f64c880956e4e3ee1692cc730e)), closes
  [#476](https://github.com/rynfar/meridian/issues/476)
- **profiles:** sticky session-to-profile routing via rendezvous hashing
  ([#615](https://github.com/rynfar/meridian/issues/615))
  ([873a53b](https://github.com/rynfar/meridian/commit/873a53b5d96cff5db9ed7bded3971fc71417ba57)), closes
  [#383](https://github.com/rynfar/meridian/issues/383)

### Bug Fixes

- **nix:** patch vendored ELF binaries so claude.exe runs on NixOS
  ([#612](https://github.com/rynfar/meridian/issues/612))
  ([ef899f4](https://github.com/rynfar/meridian/commit/ef899f44461f50166e81b2b4bb73c9d17949c931))
- **replay:** stop rendering Human:/Assistant: transcript lines in prompts
  ([#618](https://github.com/rynfar/meridian/issues/618))
  ([1e1228c](https://github.com/rynfar/meridian/commit/1e1228c46f55129a89b1fc3a32a152ae12d143e9))

## [1.46.0](https://github.com/rynfar/meridian/compare/meridian-v1.45.4...meridian-v1.46.0) (2026-07-13)

### Features

- **models:** route Claude Mythos 5 (claude-mythos-\*) through the fable tier
  ([a42a5cf](https://github.com/rynfar/meridian/commit/a42a5cfcc672e01bbb4e28d7f6042ce4d3f4e156))
- **models:** route Claude Mythos 5 (claude-mythos-\*) through the fable tier
  ([c218527](https://github.com/rynfar/meridian/commit/c218527e4a91e4b65a3cfc12e813f1f51ffcd205))

### Bug Fixes

- give deferred passthrough sessions a turn for ToolSearch discovery
  ([#598](https://github.com/rynfar/meridian/issues/598))
  ([b1e4681](https://github.com/rynfar/meridian/commit/b1e4681adbab4c93e875bb655fba7991a7881c9a))

## [1.45.3](https://github.com/rynfar/meridian/compare/meridian-v1.45.2...meridian-v1.45.3) (2026-07-10)

### Bug Fixes

- apply opencode transforms to the openai adapter ([#587](https://github.com/rynfar/meridian/issues/587))
  ([465cd2d](https://github.com/rynfar/meridian/commit/465cd2d32e285581e0823e68b8793683a1013950))
- clamp token-refresh timer delay to the 32-bit max (Node 26 overflow loop)
  ([#583](https://github.com/rynfar/meridian/issues/583))
  ([7ea7c6f](https://github.com/rynfar/meridian/commit/7ea7c6feacda44bc6029033807100e2e9394a47c))
- populate capabilities on /v1/models so clients allow image input
  ([#585](https://github.com/rynfar/meridian/issues/585))
  ([31b6042](https://github.com/rynfar/meridian/commit/31b604271666d9a8f39dc211563c1919f1519c6b))
- require a meaningful baseline before flagging a context spike ([#586](https://github.com/rynfar/meridian/issues/586))
  ([b469aeb](https://github.com/rynfar/meridian/commit/b469aeb88f5758918ad3c581d81de961690dc7df))
- stop bash redirect heuristic emitting non-path false positives ([#581](https://github.com/rynfar/meridian/issues/581))
  ([b3706b6](https://github.com/rynfar/meridian/commit/b3706b6cb921c73132b420a2b2a2a801e8995d40))
- strip SDK-only context_management from forwarded stream events ([#584](https://github.com/rynfar/meridian/issues/584))
  ([76086ca](https://github.com/rynfar/meridian/commit/76086ca4d94b7df26605d5eebad08e9050e42e84))

## [1.45.2](https://github.com/rynfar/meridian/compare/meridian-v1.45.1...meridian-v1.45.2) (2026-07-10)

### Bug Fixes

- forward token usage on OpenAI-format streaming responses
  ([6c9f04a](https://github.com/rynfar/meridian/commit/6c9f04acbe221a554bb32e8e64ebe3eeb3831f58))
- **passthrough:** truthful deny reasons for dropped tool calls ([#580](https://github.com/rynfar/meridian/issues/580))
  ([661276d](https://github.com/rynfar/meridian/commit/661276d75d8181f5a7da9e2588c28c8058b011db)), closes
  [#552](https://github.com/rynfar/meridian/issues/552)

## [1.44.1](https://github.com/rynfar/meridian/compare/meridian-v1.44.0...meridian-v1.44.1) (2026-06-25)

### Bug Fixes

- implement passthrough for the pi adapter ([#544](https://github.com/rynfar/meridian/issues/544))
  ([dc1bf2f](https://github.com/rynfar/meridian/commit/dc1bf2f2384c39fef98d63b051119b457149032f))

## [1.44.0](https://github.com/rynfar/meridian/compare/meridian-v1.43.0...meridian-v1.44.0) (2026-06-16)

### Features

- **effort:** accept reasoning_effort end-to-end (OpenAI translation + validation)
  ([#536](https://github.com/rynfar/meridian/issues/536))
  ([bf38f2b](https://github.com/rynfar/meridian/commit/bf38f2bfdf6e2005b0367b337272151b8f531110))
- **profiles:** add headless OAuth code flow ([#504](https://github.com/rynfar/meridian/issues/504))
  ([28f6a01](https://github.com/rynfar/meridian/commit/28f6a01c153de03cf7c3737a26daf9ab38f1cb65))

### Bug Fixes

- **docker:** match meridian-v\* release tags for image builds ([#507](https://github.com/rynfar/meridian/issues/507))
  ([186b268](https://github.com/rynfar/meridian/commit/186b2684a66711389af1fd6bdab92969f0ed1b29))
- **logging:** gate [PROXY] operational stderr behind config.silent
  ([#537](https://github.com/rynfar/meridian/issues/537))
  ([e69a8db](https://github.com/rynfar/meridian/commit/e69a8db71c04c8e3b0ab8249835619df413d5d85))
- **openai:** don't inject claude_code preset on /v1/chat/completions
  ([#533](https://github.com/rynfar/meridian/issues/533))
  ([1e8ddd3](https://github.com/rynfar/meridian/commit/1e8ddd3e59ea7e2ac54b837f4ed3e71cabe250e0))
- **profiles:** refresh selected profile credentials ([#500](https://github.com/rynfar/meridian/issues/500))
  ([c389ac1](https://github.com/rynfar/meridian/commit/c389ac1f679e475f8c7e7036bf7f74a6a874d12e))
- **server:** install uncaughtException/unhandledRejection handlers for library consumers
  ([#505](https://github.com/rynfar/meridian/issues/505))
  ([8b77143](https://github.com/rynfar/meridian/commit/8b77143f8f0762d92da2c5a4adec23ee4415c11d))
- **setup:** never overwrite opencode.json; merge non-destructively (closes
  [#519](https://github.com/rynfar/meridian/issues/519)) ([#538](https://github.com/rynfar/meridian/issues/538))
  ([8c5ad3e](https://github.com/rynfar/meridian/commit/8c5ad3e057c08e732cd8078f575455d6d0600cfb))
- **tokenRefresh:** silence scheduled refresh log ([#518](https://github.com/rynfar/meridian/issues/518))
  ([da722a3](https://github.com/rynfar/meridian/commit/da722a397ff5b39e946bf5012b924323fb199c1e))
- Windows build + partial-overlap export dedup ([#510](https://github.com/rynfar/meridian/issues/510))
  ([619a582](https://github.com/rynfar/meridian/commit/619a582db221fd425f16afb0fd5536e58a302a36))

## [1.43.0](https://github.com/rynfar/meridian/compare/meridian-v1.42.1...meridian-v1.43.0) (2026-05-29)

### Features

- support Claude Opus 4.8 ([#521](https://github.com/rynfar/meridian/issues/521))
  ([236781d](https://github.com/rynfar/meridian/commit/236781de81aa1a303e9e766c5c1a69207db3571f))

### Bug Fixes

- **proxy:** support explicit opus 4.6 and 4.7 pins ([#497](https://github.com/rynfar/meridian/issues/497))
  ([597a304](https://github.com/rynfar/meridian/commit/597a3042cbb7435297cab9960c3dccade3e6bd6f))

## [1.42.1](https://github.com/rynfar/meridian/compare/meridian-v1.42.0...meridian-v1.42.1) (2026-05-06)

### Bug Fixes

- **auth-status:** route claude auth status/login through resolver, not PATH
  ([#478](https://github.com/rynfar/meridian/issues/478)) ([#492](https://github.com/rynfar/meridian/issues/492))
  ([5ca8212](https://github.com/rynfar/meridian/commit/5ca82120d3e5114dcc8fce926ee156d9a3380ca0))
- **passthrough:** strip SDK tool catalog and CLAUDE.md from upstream payload
  ([#490](https://github.com/rynfar/meridian/issues/490))
  ([b279fee](https://github.com/rynfar/meridian/commit/b279feed06c8ba035256370c0ccefc712522130d))

## [1.42.0](https://github.com/rynfar/meridian/compare/meridian-v1.41.1...meridian-v1.42.0) (2026-05-06)

### Features

- **diagnostics:** surface resolved Claude executable + source in /health and startup log
  ([#485](https://github.com/rynfar/meridian/issues/485))
  ([c875cb4](https://github.com/rynfar/meridian/commit/c875cb49008641e252f968e8cb4e27a360dd369b))
- register OAuth token as profile (closes [#446](https://github.com/rynfar/meridian/issues/446))
  ([e2c9b81](https://github.com/rynfar/meridian/commit/e2c9b8181d62fcacc9ec740a606af66e719aa781))
- **tokenRefresh:** background scheduler keeps refresh chain warm
  ([becf7f7](https://github.com/rynfar/meridian/commit/becf7f7cebc8fa8dafc631fc4e15e48b2f2af5e9))
- **tokenRefresh:** make scheduler activity visible in default logs
  ([59270c2](https://github.com/rynfar/meridian/commit/59270c21a4c2fcd878a88c2b2a59ecef98d24b89))
- **tokenRefresh:** proactive ensureFreshToken before SDK call
  ([0b82dfc](https://github.com/rynfar/meridian/commit/0b82dfca47e93aef34bff3d24c6ff313bfe69bb4))

### Bug Fixes

- **errors:** broaden isExpiredTokenError to catch generic 401s
  ([91e1bb3](https://github.com/rynfar/meridian/commit/91e1bb3964ea369a514ed0aa9f6ae76b6c9ffd95))
- **plugins:** convert Windows paths to file:// URLs for ESM import
  ([554d70c](https://github.com/rynfar/meridian/commit/554d70cf1ab0359137816a590d7aa5d5608a8812))
- **plugins:** gate pathToFileURL on win32 + add loader to windows-smoke CI
  ([150a456](https://github.com/rynfar/meridian/commit/150a4568a33753af1f1aabe6918bbcf6ceaa16ed))
- **profiles:** clean oauth-token isolation dir on profile remove
  ([39dd273](https://github.com/rynfar/meridian/commit/39dd2730b3ea6a4bbb0a8d486e0e9df4aa176aef))
- **profiles:** isolate oauth-token profile from host ~/.claude
  ([d400c55](https://github.com/rynfar/meridian/commit/d400c5525aaeee7834e0db6bfddfd48b82d6343a))
- **proxy:** fall back to process.cwd() when SDK cwd doesn't exist
  ([#381](https://github.com/rynfar/meridian/issues/381)) ([#473](https://github.com/rynfar/meridian/issues/473))
  ([232f727](https://github.com/rynfar/meridian/commit/232f727d5dfb3d28fc5c7bfeabb4344292fb9878))
- **proxy:** forward auth headers on /v1/chat/completions internal hop
  ([#470](https://github.com/rynfar/meridian/issues/470))
  ([6567639](https://github.com/rynfar/meridian/commit/65676394198cb1fc47b9b30704a872ee1cc57031)), closes
  [#415](https://github.com/rynfar/meridian/issues/415)
- **query:** preserve CLAUDE_CONFIG_DIR for oauth-token profiles under sharedMemory
  ([274dbf1](https://github.com/rynfar/meridian/commit/274dbf18653882e6761ee1fa6676827274c16e3c))
- **security:** require auth on /settings/api/\* and /settings (closes
  [#477](https://github.com/rynfar/meridian/issues/477)) ([#486](https://github.com/rynfar/meridian/issues/486))
  ([5db6341](https://github.com/rynfar/meridian/commit/5db63417ef0e14e63c57f079ce92432f527d9a26))
- **tokenRefresh:** generation-track scheduler to kill orphan chains
  ([aac7c9a](https://github.com/rynfar/meridian/commit/aac7c9a0122410b3fa83487f38a8f4810cb6ab86))

## [1.41.1](https://github.com/rynfar/meridian/compare/meridian-v1.41.0...meridian-v1.41.1) (2026-05-01)

### Bug Fixes

- **droid:** respect MERIDIAN_PASSTHROUGH env (closes [#440](https://github.com/rynfar/meridian/issues/440))
  ([#461](https://github.com/rynfar/meridian/issues/461))
  ([40b1ba8](https://github.com/rynfar/meridian/commit/40b1ba8b4c33854eba8c593325001d402491e5e4))
- **env:** strip CLAUDE_CODE_USE_POWERSHELL_TOOL from SDK env (closes
  [#441](https://github.com/rynfar/meridian/issues/441)) ([#468](https://github.com/rynfar/meridian/issues/468))
  ([c113970](https://github.com/rynfar/meridian/commit/c113970c9a6d4406c3cf87bcff2204a4c6423836))
- **features:** respect codeSystemPrompt=false on passthrough (closes
  [#408](https://github.com/rynfar/meridian/issues/408)) ([#469](https://github.com/rynfar/meridian/issues/469))
  ([2d0130c](https://github.com/rynfar/meridian/commit/2d0130c349ec1598b067c75adc35309bbc16fec5))
- **proxy:** reject empty messages array, defensive array allocation (closes
  [#450](https://github.com/rynfar/meridian/issues/450)) ([#466](https://github.com/rynfar/meridian/issues/466))
  ([611e03c](https://github.com/rynfar/meridian/commit/611e03c4914bb6ae71f8cf7bca9adfd1f041f165))
- **proxy:** use SDK result.usage for non-stream output_tokens (closes
  [#449](https://github.com/rynfar/meridian/issues/449)) ([#465](https://github.com/rynfar/meridian/issues/465))
  ([7a89322](https://github.com/rynfar/meridian/commit/7a893228e0ecf0e83f1aeac1758728e47b898fe8))
- **query:** strip CLAUDE_CONFIG_DIR for sharedMemory instead of setting (closes
  [#453](https://github.com/rynfar/meridian/issues/453)) ([#467](https://github.com/rynfar/meridian/issues/467))
  ([95f61b0](https://github.com/rynfar/meridian/commit/95f61b031456304210853c41480a739ab357349e))
- **resolver:** Windows + broken-postinstall fallbacks (closes [#417](https://github.com/rynfar/meridian/issues/417),
  mitigates [#445](https://github.com/rynfar/meridian/issues/445))
  ([#463](https://github.com/rynfar/meridian/issues/463))
  ([8e088b0](https://github.com/rynfar/meridian/commit/8e088b07ad895898f3115bbf39584fbff286eeeb))
- **tokenRefresh:** write compact JSON for credentials (closes [#452](https://github.com/rynfar/meridian/issues/452))
  ([#464](https://github.com/rynfar/meridian/issues/464))
  ([22c9c41](https://github.com/rynfar/meridian/commit/22c9c41a3cde4f286f8a69f60d9099a5ae9ec65f))
