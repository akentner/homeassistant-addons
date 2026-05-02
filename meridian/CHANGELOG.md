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
