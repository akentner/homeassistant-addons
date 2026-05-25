#!/usr/bin/env python3
"""
Base Image Update Script

Determines the latest base image tag by reading version ARGs directly from
the home-assistant/docker-base Dockerfiles on GitHub (avoids GHCR tag listing
API which is incomplete).

When a newer tag is found for an add-on:
  - Updates build_from in build.yaml
  - Increments the numeric subpatch in config.yaml (X.Y.Z-N -> X.Y.Z-(N+1))
  - Updates README.md badges/links via update_readme_md helper (if applicable)
"""
import re
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# Allow importing helpers from update-version.py (hyphen in filename -> importlib)
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "update_version", Path(__file__).parent / "update-version.py"
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
update_readme_md = _mod.update_readme_md


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def fetch_github_file(repo: str, path: str) -> str:
    """Return the raw text of a file from the default branch of a GitHub repo."""
    url = f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "update-base-image/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode()


# ---------------------------------------------------------------------------
# Tag resolution
# ---------------------------------------------------------------------------

def resolve_latest_tag(acfg: dict) -> str | None:
    """
    Read the upstream Dockerfile(s) from GitHub and return the expected
    GHCR image tag for this add-on.
    """
    source_repo = acfg["source_repo"]
    source_file = acfg["source_file"]
    pattern = acfg["version_pattern"]
    tag_template = acfg.get("tag_template")

    content = fetch_github_file(source_repo, source_file)

    # For multi-group patterns (phone-logger) use DOTALL matching
    m = re.search(pattern, content, flags=re.DOTALL)
    if not m:
        return None

    if tag_template:
        # Substitute named groups into the template
        tag = tag_template
        for k, v in m.groupdict().items():
            tag = tag.replace("{" + k + "}", v)
        return tag
    else:
        return m.group("version")


# ---------------------------------------------------------------------------
# Numeric comparison helper
# ---------------------------------------------------------------------------

def tag_version_key(tag: str) -> list[int]:
    """Extract all numeric parts of a tag as a sortable key."""
    return [int(x) for x in re.findall(r"\d+", tag)]


def tag_is_newer(candidate: str, current: str) -> bool:
    """Return True if candidate tag is strictly newer than current."""
    return tag_version_key(candidate) > tag_version_key(current)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def read_file(path: Path) -> str:
    with open(path) as f:
        return f.read()


def write_file(path: Path, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def current_build_from_tag(build_yaml_path: Path, image: str) -> str | None:
    """Parse the tag currently set for *image* in build.yaml build_from section."""
    content = read_file(build_yaml_path)
    escaped_image = re.escape(image)
    m = re.search(
        rf'build_from:.*?{escaped_image}:([^\s"\']+)',
        content,
        flags=re.DOTALL,
    )
    return m.group(1) if m else None


def update_build_from_tag(
    build_yaml_path: Path, image: str, old_tag: str, new_tag: str, dry_run: bool
) -> bool:
    """Replace old tag with new tag in build_from section."""
    content = read_file(build_yaml_path)
    escaped_image = re.escape(image)
    new_content = re.sub(
        rf'({escaped_image}:){re.escape(old_tag)}',
        rf'\g<1>{new_tag}',
        content,
    )
    if new_content == content:
        print(f"  ⚠️  build.yaml: pattern not replaced (image={image}, old={old_tag})")
        return False
    print(f"  ✅ {'Would update' if dry_run else 'Updated'} build.yaml: {old_tag} → {new_tag}")
    if not dry_run:
        write_file(build_yaml_path, new_content)
    return True


def current_config_version(config_yaml_path: Path) -> str | None:
    """Return the full version string from config.yaml (e.g. '5.36.0-7')."""
    content = read_file(config_yaml_path)
    m = re.search(
        r'^version:\s*["\']([0-9]+\.[0-9]+\.[0-9]+-(?:[0-9]+|(?:alpha|beta|rc)[0-9]+))["\']',
        content,
        flags=re.MULTILINE,
    )
    return m.group(1) if m else None


def increment_subpatch(version: str) -> str | None:
    """
    Increment numeric subpatch: '5.36.0-7' -> '5.36.0-8'.
    Pre-release versions (alpha/beta/rc) are left untouched — return None.
    """
    m = re.match(r'^([0-9]+\.[0-9]+\.[0-9]+)-([0-9]+)$', version)
    if not m:
        return None  # pre-release or unexpected format
    return f"{m.group(1)}-{int(m.group(2)) + 1}"


def update_config_subpatch(
    config_yaml_path: Path, old_version: str, new_version: str, dry_run: bool
) -> bool:
    """Replace old_version with new_version in config.yaml."""
    content = read_file(config_yaml_path)
    new_content = content.replace(
        f'version: "{old_version}"',
        f'version: "{new_version}"',
    )
    if new_content == content:
        new_content = content.replace(
            f"version: '{old_version}'",
            f"version: '{new_version}'",
        )
    if new_content == content:
        print(f"  ⚠️  config.yaml: could not replace version {old_version}")
        return False
    print(f"  ✅ {'Would update' if dry_run else 'Updated'} config.yaml: {old_version} → {new_version}")
    if not dry_run:
        write_file(config_yaml_path, new_content)
    return True


# ---------------------------------------------------------------------------
# Per-add-on update logic
# ---------------------------------------------------------------------------

def process_addon(
    addon_name: str,
    acfg: dict,
    addon_dir: Path,
    dry_run: bool,
) -> bool:
    """
    Check for a new base image tag and update files if needed.
    Returns True if an update was applied (or would be applied in dry-run).
    """
    image = acfg["image"]
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Checking {addon_name} ({image})")

    build_yaml = addon_dir / "build.yaml"
    config_yaml = addon_dir / "config.yaml"

    if not build_yaml.exists():
        print(f"  ❌ build.yaml not found in {addon_dir}")
        return False
    if not config_yaml.exists():
        print(f"  ❌ config.yaml not found in {addon_dir}")
        return False

    # 1. Determine current base image tag from build.yaml
    current = current_build_from_tag(build_yaml, image)
    if current is None:
        print(f"  ❌ Could not parse current base image tag for {image}")
        return False
    print(f"  Current base image tag: {current}")

    # 2. Resolve latest tag from upstream Dockerfile
    try:
        new_tag = resolve_latest_tag(acfg)
    except Exception as exc:
        print(f"  ❌ Failed to resolve latest tag: {exc}")
        return False

    if new_tag is None:
        print(f"  ⚠️  Could not determine latest tag from upstream Dockerfile")
        return False
    print(f"  Latest available tag:   {new_tag}")

    if current == new_tag:
        print(f"  ✅ Already up to date")
        return False

    if not tag_is_newer(new_tag, current):
        print(f"  ✅ Current tag {current!r} is already newer than resolved {new_tag!r} — skipping")
        return False

    print(f"  → Update available: {current} → {new_tag}")

    # 3. Read current config version and compute new subpatch
    cfg_ver = current_config_version(config_yaml)
    if cfg_ver is None:
        print(f"  ❌ Could not parse version from config.yaml")
        return False
    print(f"  Current config version: {cfg_ver}")

    new_cfg_ver = increment_subpatch(cfg_ver)
    if new_cfg_ver is None:
        print(f"  ⚠️  Pre-release version {cfg_ver!r} — subpatch not incremented")
        new_cfg_ver = cfg_ver

    print(f"  New config version:     {new_cfg_ver}")

    # 4. Apply updates
    ok1 = update_build_from_tag(build_yaml, image, current, new_tag, dry_run)
    ok2 = True
    if cfg_ver != new_cfg_ver:
        ok2 = update_config_subpatch(config_yaml, cfg_ver, new_cfg_ver, dry_run)
    else:
        print(f"  ℹ️  Subpatch unchanged (pre-release), skipping config.yaml update")

    # 5. Update README badges (version string changes due to new subpatch)
    if ok1 and ok2:
        update_readme_md(addon_dir, new_cfg_ver, dry_run=dry_run)

    return ok1


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(config_path: Path) -> dict:
    """Load YAML config (requires PyYAML)."""
    try:
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f)
    except ImportError:
        raise RuntimeError(
            "PyYAML not installed. Run: pip install pyyaml"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check and update base image tags for Home Assistant add-ons",
    )
    parser.add_argument(
        "addon",
        nargs="?",
        default=None,
        help="Process only this add-on (default: all add-ons in config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files",
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "base-image-config.yaml"),
        help="Path to base-image-config.yaml",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"❌ Config not found: {cfg_path}")
        return 1

    cfg = load_config(cfg_path)
    addons_cfg: dict = cfg.get("addons", {})

    if args.addon:
        if args.addon not in addons_cfg:
            print(f"❌ Add-on '{args.addon}' not found in {cfg_path}")
            return 1
        target_addons = {args.addon: addons_cfg[args.addon]}
    else:
        target_addons = addons_cfg

    repo_root = Path(__file__).parent.parent
    updated: list[str] = []
    errors: list[str] = []

    for name, acfg in target_addons.items():
        addon_dir = repo_root / name
        if not addon_dir.is_dir():
            print(f"\n⚠️  Directory not found: {addon_dir} — skipping {name}")
            errors.append(name)
            continue
        try:
            changed = process_addon(
                addon_name=name,
                acfg=acfg,
                addon_dir=addon_dir,
                dry_run=args.dry_run,
            )
            if changed:
                updated.append(name)
        except Exception as exc:
            print(f"\n❌ Unexpected error for {name}: {exc}")
            errors.append(name)

    print(f"\n{'=' * 50}")
    if updated:
        print(f"✅ Updated: {', '.join(updated)}")
    else:
        print("ℹ️  No updates applied")
    if errors:
        print(f"❌ Errors:  {', '.join(errors)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
