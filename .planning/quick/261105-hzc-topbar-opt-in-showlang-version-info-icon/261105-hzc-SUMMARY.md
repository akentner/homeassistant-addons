---
status: complete
---

# Summary 261105-hzc

- Info link target: `/config/app/<slug>/config` (slug from Supervisor at runtime, never hard-coded; hidden without answer)
- Version source: same Supervisor call (installed version incl. subpatch; config.yaml is not in the image)
- Lib 0.8.0; tests: admin-ui node 315, haos-monitor node 52, pytest admin-ui 384 / ntfy 386 / secrets-sync 66 / haos-monitor 246
- Not verified: real HA ingress rendering, live navigate to the config page; Nextgen deploy pending (needs push + CI image)
