# Deferred Items — 260908-pfq

Out-of-scope discoveries logged, not fixed (executor scope boundary).

## 1. `gsd-tools windows append` cannot write to `.planning/WINDOWS.md`

`node gsd-tools.cjs windows append --kind deviation --phase quick-260908-pfq ...` fails with:

```text
Error: Ledger table region could not be located in .planning/WINDOWS.md; refusing to write.
```

The file looks structurally intact on inspection (frontmatter + heading + blockquote + rendered table + fenced JSON
block with one `fixed` entry from Phase 17). The tool's table-region detector nonetheless does not find the region —
plausibly because `prettier` realigned the table's column padding on a later commit, which the detector's marker
matching does not tolerate.

Not fixed here because:

- It is pre-existing and unrelated to this item's six files.
- The tool's own error message explicitly forbids hand-editing the rendered table ("never hand-edit the rendered
  table"), so the safe remedy is either editing the fenced JSON block or letting `gsd-tools` regenerate the region —
  both are changes to cross-phase planning state that this quick item does not own.

Consequence: the one deviation from this item (the fixture-harness bug, see `260908-pfq-SUMMARY.md` §Deviations) is
recorded in the SUMMARY only, not in the cross-phase ledger. Anyone running `/gsd-ship` should be aware the ledger is
currently un-writable via the tool.
