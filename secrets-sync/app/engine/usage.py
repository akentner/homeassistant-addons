"""Find `!secret <key>` references in YAML files (see docs/SPEC.md, "Secret usage").

Only key names and file/line positions are collected, never values. HA resolves `!secret` against the nearest
`secrets.yaml` in the file's folder or a parent folder; references that resolve to a *different* secrets.yaml (for
example ESPHome's own) do not count for ours.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

# The tag value is the whole YAML scalar (keys may contain parentheses and the like), optionally quoted
_REF = re.compile(r"""!secret\s+(?:"([^"]+)"|'([^']+)'|([^\s,\]}#"']+))""")
_COMMENT = re.compile(r"(^|\s)#.*$")
SKIP_DIRS = frozenset({"custom_components", "deps", "node_modules", "backups", "__pycache__", "secrets_files"})
EXTENSIONS = (".yaml", ".yml")
SECRETS_NAME = "secrets.yaml"
MAX_FILES = 20000
MAX_FILE_BYTES = 1024 * 1024
MAX_REFS_PER_KEY = 20
TIME_BUDGET = 20.0


@dataclass
class Scan:
    files_scanned: int = 0
    truncated: bool = False
    refs: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    roots: list[str] = field(default_factory=list)


def _own_scope(directory: Path, root: Path, cache: dict[Path, Path | None]) -> Path | None:
    """Directory holding the nearest secrets.yaml between `directory` and `root` (inclusive), or None."""
    if directory in cache:
        return cache[directory]
    candidate = directory / SECRETS_NAME
    if candidate.is_file() and not candidate.is_symlink():
        found: Path | None = directory
    elif directory == root or directory.parent == directory:
        found = None
    else:
        found = _own_scope(directory.parent, root, cache)
    cache[directory] = found
    return found


def scan(roots: Iterable[tuple[str, Path]], *, clock: Callable[[], float] = time.monotonic) -> Scan:
    """Scan `(label, path)` roots. The first root is the HA config dir whose secrets.yaml is ours."""
    result = Scan()
    started = clock()
    ours: Path | None = None
    for index, (label, root) in enumerate(roots):
        if not root.is_dir():
            continue
        result.roots.append(label)
        if index == 0:
            ours = root
        cache: dict[Path, Path | None] = {}
        for current, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS)
            here = Path(current)
            scope = _own_scope(here, root, cache)
            # config root: only references resolving to /config/secrets.yaml are ours;
            # other roots: references without any secrets.yaml of their own are attributed to ours
            counts = scope is None or (index == 0 and scope == ours)
            if not counts:
                continue
            for name in sorted(files):
                if not name.endswith(EXTENSIONS) or name == SECRETS_NAME:
                    continue
                if result.files_scanned >= MAX_FILES or clock() - started > TIME_BUDGET:
                    result.truncated = True
                    return result
                path = here / name
                try:
                    if path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
                        continue
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                result.files_scanned += 1
                rel = path.relative_to(root).as_posix()
                shown = rel if index == 0 else f"{label}/{rel}"
                for number, line in enumerate(text.splitlines(), start=1):
                    if "!secret" not in line:
                        continue
                    for match in _REF.finditer(_COMMENT.sub("", line)):
                        key = next(g for g in match.groups() if g)
                        result.counts[key] = result.counts.get(key, 0) + 1
                        refs = result.refs.setdefault(key, [])
                        if len(refs) < MAX_REFS_PER_KEY:
                            refs.append((shown, number))
    return result


def summarize(result: Scan, known: set[str]) -> dict[str, object]:
    """State block: used / missing (referenced but not in secrets.yaml) / unused key names."""

    def entry(key: str) -> dict[str, object]:
        return {"count": result.counts[key], "refs": [{"file": f, "line": n} for f, n in result.refs[key]]}

    used = {k: entry(k) for k in sorted(result.refs) if k in known}
    missing = {k: entry(k) for k in sorted(result.refs) if k not in known}
    return {
        "enabled": True,
        "roots": list(result.roots),
        "files_scanned": result.files_scanned,
        "truncated": result.truncated,
        "used": used,
        "missing": missing,
        "unused": sorted(known - set(result.refs)),
    }
