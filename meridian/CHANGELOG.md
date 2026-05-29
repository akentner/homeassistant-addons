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
