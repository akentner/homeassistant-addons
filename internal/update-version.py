#!/usr/bin/env python3
"""
Update Add-on Version Script
Automatically updates version numbers across all required files for a Home Assistant Add-on.
"""
import re
import sys
import argparse
from pathlib import Path
from typing import Tuple


def is_prerelease(version: str) -> bool:
    """Return True if version has a pre-release suffix (alpha/beta/rc)."""
    return bool(re.search(r'-(alpha|beta|rc)[0-9]+$', version))


def has_subpatch(version: str) -> bool:
    """Return True if version already carries an explicit numeric subpatch (X.Y.Z-N)."""
    return bool(re.search(r'-[0-9]+$', version))


def base_version(version: str) -> str:
    """Strip numeric subpatch suffix; leave pre-release suffix intact."""
    return re.sub(r'-[0-9]+$', '', version)


def update_config_yaml(addon_dir: Path, new_version: str, dry_run: bool = False) -> Tuple[bool, str, str]:
    """Update version in config.yaml

    Returns:
        (success, old_version, new_version)
    """
    config_file = addon_dir / "config.yaml"
    if not config_file.exists():
        print(f"❌ {config_file} not found")
        return False, "", ""

    try:
        with open(config_file, 'r') as f:
            content = f.read()

        # Pattern: version: "X.Y.Z-N" (stable) or "X.Y.Z-{alpha|beta|rc}N" (pre-release)
        pattern = r'^(\s*version:\s*["\'])([0-9]+\.[0-9]+\.[0-9]+-(?:(?:alpha|beta|rc)[0-9]+|[0-9]+))(["\'].*?)$'
        match = re.search(pattern, content, flags=re.MULTILINE)

        if not match:
            print(f"⚠️  No version found in {config_file}")
            return False, "", ""

        old_version = match.group(2)
        # Pre-release and explicit subpatch (X.Y.Z-N) are written as-is; plain X.Y.Z gets -0
        new_version_full = new_version if (is_prerelease(new_version) or has_subpatch(new_version)) else f"{new_version}-0"

        new_content = re.sub(
            pattern,
            f'\\g<1>{new_version_full}\\g<3>',
            content,
            flags=re.MULTILINE
        )

        if new_content != content:
            if not dry_run:
                with open(config_file, 'w') as f:
                    f.write(new_content)
            print(f"✅ {'Would update' if dry_run else 'Updated'} {config_file.name}: {old_version} → {new_version_full}")
            return True, old_version, new_version_full
        else:
            print(f"⚠️  No changes needed in {config_file}")
            return False, old_version, new_version_full

    except Exception as e:
        print(f"❌ Error updating {config_file}: {e}")
        return False, "", ""


def update_build_yaml(addon_dir: Path, new_version: str, dry_run: bool = False) -> Tuple[bool, str, str]:
    """Update VERSION in build.yaml

    Returns:
        (success, old_version, new_version)
    """
    build_file = addon_dir / "build.yaml"
    if not build_file.exists():
        print(f"❌ {build_file} not found")
        return False, "", ""

    try:
        with open(build_file, 'r') as f:
            content = f.read()

        # Pattern: VERSION: "X.Y.Z" (stable) or "X.Y.Z-{alpha|beta|rc}N" (pre-release)
        pattern = r'^(\s*VERSION:\s*["\'])([0-9]+\.[0-9]+\.[0-9]+(?:-(?:alpha|beta|rc)[0-9]+)?)(["\'].*?)$'
        match = re.search(pattern, content, flags=re.MULTILINE)

        if not match:
            print(f"⚠️  No VERSION found in {build_file}")
            return False, "", ""

        old_version = match.group(2)
        build_ver = base_version(new_version)  # build.yaml never carries the subpatch

        new_content = re.sub(
            pattern,
            f'\\g<1>{build_ver}\\g<3>',
            content,
            flags=re.MULTILINE
        )

        if new_content != content:
            if not dry_run:
                with open(build_file, 'w') as f:
                    f.write(new_content)
            print(f"✅ {'Would update' if dry_run else 'Updated'} {build_file.name}: {old_version} → {build_ver}")
            return True, old_version, build_ver
        else:
            print(f"⚠️  No changes needed in {build_file}")
            return False, old_version, build_ver

    except Exception as e:
        print(f"❌ Error updating {build_file}: {e}")
        return False, "", ""


def update_readme_md(addon_dir: Path, new_version: str, dry_run: bool = False) -> Tuple[bool, list]:
    """Update version badges and links in README.md

    Returns:
        (success, list of changes)
    """
    readme_file = addon_dir / "README.md"
    if not readme_file.exists():
        print(f"❌ {readme_file} not found")
        return False, []

    try:
        with open(readme_file, 'r') as f:
            content = f.read()

        original_content = content
        changes = []

        readme_ver = base_version(new_version)  # README never shows the subpatch
        # shields.io uses "--" to represent "-" in badge text
        badge_version = readme_ver.replace('-', '--') if is_prerelease(readme_ver) else readme_ver
        # Update Shields.io badge: [release-shield]: https://img.shields.io/badge/version-vX.Y.Z-COLOR.svg
        shield_pattern = r'(\[release-shield\]:\s*https://img\.shields\.io/badge/version-v)([0-9]+\.[0-9]+\.[0-9]+(?:--(?:alpha|beta|rc)[0-9]+)?)(-\w+\.svg)'
        shield_match = re.search(shield_pattern, content)
        if shield_match:
            old_shield_version = shield_match.group(2).replace('--', '-')
            content = re.sub(shield_pattern, f'\\g<1>{badge_version}\\g<3>', content)
            changes.append(f"Badge: v{old_shield_version} → v{readme_ver}")

        # Update release tree links: [release]: https://github.com/akentner/homeassistant-addons/tree/vX.Y.Z
        release_pattern = r'(\[release\]:\s*https://github\.com/akentner/homeassistant-addons/tree/v)([0-9]+\.[0-9]+\.[0-9]+(?:-(alpha|beta|rc)[0-9]+)?)'
        release_match = re.search(release_pattern, content)
        if release_match:
            old_release_version = release_match.group(2)
            content = re.sub(release_pattern, f'\\g<1>{readme_ver}', content)
            changes.append(f"Release link: v{old_release_version} → v{readme_ver}")

        if content != original_content:
            if not dry_run:
                with open(readme_file, 'w') as f:
                    f.write(content)
            print(f"✅ {'Would update' if dry_run else 'Updated'} {readme_file.name}:")
            for change in changes:
                print(f"   • {change}")
            return True, changes
        else:
            print(f"⚠️  No changes needed in {readme_file.name} (already at target version)")
            return False, []

    except Exception as e:
        print(f"❌ Error updating {readme_file}: {e}")
        return False, []


def validate_version_format(version: str) -> bool:
    """Validate version: X.Y.Z, X.Y.Z-N (stable) or X.Y.Z-{alpha|beta|rc}N (pre-release)"""
    pattern = r'^[0-9]+\.[0-9]+\.[0-9]+(?:-(?:(?:alpha|beta|rc)[0-9]+|[0-9]+))?$'
    return re.match(pattern, version) is not None


def check_github_release(version: str, addon_name: str) -> bool:
    """Check if the GitHub release exists (optional check)"""
    try:
        import urllib.request
        url = f"https://github.com/akentner/{addon_name}/releases/tag/v{version}"
        print(f"   Checking: {url}")
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except Exception as e:
        print(f"   ⚠️  Could not verify release: {e}")
        return False


def create_and_push_tag(version: str, addon_name: str, push: bool = True, dry_run: bool = False) -> bool:
    """Create an annotated git tag for the new version and push it to origin.

    Tag format is '<addon>/v<version>' (e.g. 'authentik/v2026.8.0'). The tag is required
    because per-addon build workflows (.github/workflows/build-<addon>.yml) trigger on
    paths under the addon directory and are additionally re-runnable via `make release`,
    which pushes a matching tag. Without a consistent tag name, the HA supervisor cannot
    map the version to an image in ghcr.io.

    Returns True on success.
    """
    import subprocess

    tag = f"{addon_name}/v{version}"
    message = f"{addon_name}: {version}"

    if dry_run:
        print(f"🏷️  [DRY RUN] Would create tag: {tag}")
        if push:
            print(f"   [DRY RUN] Would push: git push origin {tag}")
        return True

    existing_local = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag}"],
        capture_output=True, text=True
    )
    # Check origin for the tag. refs/remotes/origin/<tag> is only populated after
    # `git fetch --tags`, so fall back to ls-remote which queries the registry.
    existing_remote_ref = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/remotes/origin/{tag}"],
        capture_output=True, text=True
    )
    existing_remote_ls = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{tag}"],
        capture_output=True, text=True
    )
    remote_exists = existing_remote_ref.returncode == 0 or existing_remote_ls.returncode == 0
    if existing_local.returncode == 0 or remote_exists:
        source = "locally" if existing_local.returncode == 0 else "on origin"
        print(f"⚠️  Tag {tag} already exists {source} — skipping create (won't force-push)")
        # If the tag exists locally but not on origin, push it; if it's only on
        # origin there's nothing to do. Force-push is intentionally avoided —
        # it would re-associate an existing SemVer tag with a subpatch commit,
        # which is wrong (the build workflow fires on tag push and would publish
        # the wrong image).
        if push and existing_local.returncode == 0 and not remote_exists:
            push_result = subprocess.run(
                ["git", "push", "origin", tag],
                capture_output=True, text=True
            )
            if push_result.returncode != 0:
                print(f"❌ Failed to push existing tag: {push_result.stderr.strip()}")
                return False
            print(f"🚀 Pushed existing tag: {tag}")
        return True

    create_result = subprocess.run(
        ["git", "tag", "-a", tag, "-m", message],
        capture_output=True, text=True
    )
    if create_result.returncode != 0:
        print(f"❌ Failed to create tag {tag}: {create_result.stderr.strip()}")
        return False
    print(f"🏷️  Created tag: {tag} ({message})")

    if not push:
        return True

    push_result = subprocess.run(
        ["git", "push", "origin", tag],
        capture_output=True, text=True
    )
    if push_result.returncode != 0:
        print(f"❌ Failed to push tag {tag}: {push_result.stderr.strip()}")
        print(f"   Tag exists locally — push manually with: git push origin {tag}")
        return False
    print(f"🚀 Pushed tag: {tag} → build workflow will trigger")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Update add-on version across all files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s fritz-callmonitor2mqtt 1.7.2
  %(prog)s fritz-callmonitor2mqtt 1.7.2 --check-release
  %(prog)s fritz-callmonitor2mqtt 1.7.2 --dry-run
  %(prog)s fritz-callmonitor2mqtt 1.7.2 --no-tag   # update files only, no tag
        """
    )
    parser.add_argument('addon_name', help='Name of the add-on directory (e.g., fritz-callmonitor2mqtt)')
    parser.add_argument('new_version', help='New version number (e.g., 1.7.2)')
    parser.add_argument('--check-release', action='store_true', help='Check if GitHub release exists')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--no-tag', dest='no_tag', action='store_true',
                        help='Skip creating and pushing the <addon>/v<version> tag (default: tag is created and pushed)')
    parser.add_argument('--no-push', dest='no_push', action='store_true',
                        help='Create the tag locally but do not push it to origin')

    args = parser.parse_args()

    # Validate version format
    if not validate_version_format(args.new_version):
        print(f"❌ Invalid version format: {args.new_version}")
        print("   Stable:      X.Y.Z            (e.g., 1.7.2)    → config: 1.7.2-0")
        print("                X.Y.Z-N          (e.g., 1.7.2-1)  → config: 1.7.2-1")
        print("   Pre-release: X.Y.Z-alphaN     (e.g., 1.0.0-alpha9)")
        print("                X.Y.Z-betaN      (e.g., 2.0.0-beta1)")
        print("                X.Y.Z-rcN        (e.g., 1.5.0-rc2)")
        return 1

    # Find add-on directory
    addon_dir = Path(args.addon_name)
    if not addon_dir.exists() or not addon_dir.is_dir():
        print(f"❌ Add-on directory not found: {addon_dir}")
        return 1

    if not (addon_dir / "config.yaml").exists():
        print(f"❌ Not a valid add-on directory (no config.yaml): {addon_dir}")
        return 1

    print(f"🔄 {'[DRY RUN] ' if args.dry_run else ''}Updating {args.addon_name} to version {args.new_version}")
    print()

    # Optional: Check if GitHub release exists
    if args.check_release:
        print("🔍 Checking if GitHub release exists...")
        if check_github_release(args.new_version, args.addon_name):
            print(f"✅ GitHub release v{args.new_version} found")
        else:
            print(f"⚠️  GitHub release v{args.new_version} not found or not accessible")
            if not args.dry_run:
                response = input("Continue anyway? [y/N]: ")
                if response.lower() != 'y':
                    print("❌ Aborted")
                    return 1
        print()

    success_count = 0
    total_files = 3

    success, old_v, new_v = update_config_yaml(addon_dir, args.new_version, args.dry_run)
    if success:
        success_count += 1

    success, old_v, new_v = update_build_yaml(addon_dir, args.new_version, args.dry_run)
    if success:
        success_count += 1

    success, changes = update_readme_md(addon_dir, args.new_version, args.dry_run)
    if success:
        success_count += 1

    # ── Cross-artifact Provider bump (TOFU-03: Bridge+Provider share one release cycle) ──
    # When the addon being bumped is terraform-bridge, also touch
    # terraform-provider-homeassistant/build.yaml's VERSION field with the
    # same X.Y.Z. Provider has no config.yaml, no README, and no git tag of
    # its own — it's a co-located Go module, not a separately-released add-on.
    if args.addon_name == "terraform-bridge":
        provider_dir = Path("terraform-provider-homeassistant")
        provider_build = provider_dir / "build.yaml"
        if provider_build.exists():
            ok, old_pv, new_pv = update_build_yaml(
                provider_dir, args.new_version, dry_run=args.dry_run
            )
            if ok:
                print(
                    f"   • Co-located Provider bumped: "
                    f"terraform-provider-homeassistant/build.yaml {old_pv} → {new_pv}"
                )
            else:
                print(
                    f"⚠️  Failed to bump Provider build.yaml — Bridge and Provider are out of sync. "
                    f"Run validate-versions to confirm and fix manually."
                )
                return 1
        else:
            print(
                f"ℹ️  terraform-provider-homeassistant/build.yaml not found; "
                f"skipping Provider bump (post-Phase-9 repo state)."
            )

    print()
    print(f"📊 {'Would update' if args.dry_run else 'Updated'} {success_count}/{total_files} files")

    # Tag creation is independent of how many files needed updating. Subpatch-only
    # bumps only touch config.yaml (build.yaml/README stay on the same SemVer), and
    # no-op confirmations shouldn't silently drop the tag request.
    if args.dry_run:
        if not args.no_tag:
            print(f"\n🏷️  Would also create and push tag {args.addon_name}/v{new_v}")
        return 0

    if success_count == total_files:
        print("🎉 All files updated successfully!")
    elif success_count == 0:
        print("✅ Already at target version — confirming tag")
    else:
        print(f"ℹ️  {success_count}/{total_files} files needed updating (others already matched target)")

    if not args.no_tag:
        print()
        print("🏷️  Creating and pushing git tag...")
        tag_ok = create_and_push_tag(
            new_v,
            args.addon_name,
            push=not args.no_push,
            dry_run=False,
        )
        if not tag_ok:
            print()
            print("⚠️  Tag push failed — push manually:")
            print(f"   git push origin {args.addon_name}/v{new_v}")
            return 1

    print(f"\n💡 Next steps:")
    print(f"   • Run 'make validate-versions' to verify")
    print(f"   • Run 'make check-all' for full validation")
    print(f"   • Commit: git add {args.addon_name} && git commit -m 'chore: update {args.addon_name} to v{args.new_version}'")
    print(f"   • Push:  git push origin main {args.addon_name}/v{new_v}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
