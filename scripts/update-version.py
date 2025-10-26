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

        # Pattern: version: "X.Y.Z-N"
        pattern = r'^(\s*version:\s*["\'])([0-9]+\.[0-9]+\.[0-9]+-[0-9]+)(["\'].*?)$'
        match = re.search(pattern, content, flags=re.MULTILINE)

        if not match:
            print(f"⚠️  No version found in {config_file}")
            return False, "", ""

        old_version = match.group(2)
        new_version_full = f"{new_version}-0"

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

        # Pattern: VERSION: "X.Y.Z"
        pattern = r'^(\s*VERSION:\s*["\'])([0-9]+\.[0-9]+\.[0-9]+)(["\'].*?)$'
        match = re.search(pattern, content, flags=re.MULTILINE)

        if not match:
            print(f"⚠️  No VERSION found in {build_file}")
            return False, "", ""

        old_version = match.group(2)

        new_content = re.sub(
            pattern,
            f'\\g<1>{new_version}\\g<3>',
            content,
            flags=re.MULTILINE
        )

        if new_content != content:
            if not dry_run:
                with open(build_file, 'w') as f:
                    f.write(new_content)
            print(f"✅ {'Would update' if dry_run else 'Updated'} {build_file.name}: {old_version} → {new_version}")
            return True, old_version, new_version
        else:
            print(f"⚠️  No changes needed in {build_file}")
            return False, old_version, new_version

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

        # Update Shields.io badge: [release-shield]: https://img.shields.io/badge/version-vX.Y.Z-blue.svg
        shield_pattern = r'(\[release-shield\]:\s*https://img\.shields\.io/badge/version-v)([0-9]+\.[0-9]+\.[0-9]+)(-blue\.svg)'
        shield_match = re.search(shield_pattern, content)
        if shield_match:
            old_shield_version = shield_match.group(2)
            content = re.sub(shield_pattern, f'\\g<1>{new_version}\\g<3>', content)
            changes.append(f"Badge: v{old_shield_version} → v{new_version}")

        # Update release tree links: [release]: https://github.com/akentner/homeassistant-addons/tree/vX.Y.Z
        release_pattern = r'(\[release\]:\s*https://github\.com/akentner/homeassistant-addons/tree/v)([0-9]+\.[0-9]+\.[0-9]+)'
        release_match = re.search(release_pattern, content)
        if release_match:
            old_release_version = release_match.group(2)
            content = re.sub(release_pattern, f'\\g<1>{new_version}', content)
            changes.append(f"Release link: v{old_release_version} → v{new_version}")

        if content != original_content:
            if not dry_run:
                with open(readme_file, 'w') as f:
                    f.write(content)
            print(f"✅ {'Would update' if dry_run else 'Updated'} {readme_file.name}:")
            for change in changes:
                print(f"   • {change}")
            return True, changes
        else:
            print(f"⚠️  No version patterns found in {readme_file}")
            return False, []

    except Exception as e:
        print(f"❌ Error updating {readme_file}: {e}")
        return False, []


def validate_version_format(version: str) -> bool:
    """Validate that version follows semantic versioning (X.Y.Z)"""
    pattern = r'^[0-9]+\.[0-9]+\.[0-9]+$'
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


def main():
    parser = argparse.ArgumentParser(
        description='Update add-on version across all files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s fritz-callmonitor2mqtt 1.7.2
  %(prog)s fritz-callmonitor2mqtt 1.7.2 --check-release
  %(prog)s fritz-callmonitor2mqtt 1.7.2 --dry-run
        """
    )
    parser.add_argument('addon_name', help='Name of the add-on directory (e.g., fritz-callmonitor2mqtt)')
    parser.add_argument('new_version', help='New version number (e.g., 1.7.2)')
    parser.add_argument('--check-release', action='store_true', help='Check if GitHub release exists')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')

    args = parser.parse_args()

    # Validate version format
    if not validate_version_format(args.new_version):
        print(f"❌ Invalid version format: {args.new_version}")
        print("   Expected format: X.Y.Z (e.g., 1.7.2)")
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

    # Update all files
    success, old_v, new_v = update_config_yaml(addon_dir, args.new_version, args.dry_run)
    if success:
        success_count += 1

    success, old_v, new_v = update_build_yaml(addon_dir, args.new_version, args.dry_run)
    if success:
        success_count += 1

    success, changes = update_readme_md(addon_dir, args.new_version, args.dry_run)
    if success:
        success_count += 1

    print()
    print(f"📊 {'Would update' if args.dry_run else 'Updated'} {success_count}/{total_files} files")

    if success_count == total_files:
        print("🎉 All files updated successfully!" if not args.dry_run else "🎉 All files would be updated!")
        if not args.dry_run:
            print(f"\n💡 Next steps:")
            print(f"   • Run 'make validate-versions' to verify")
            print(f"   • Run 'make check-all' for full validation")
            print(f"   • Commit: git add {args.addon_name} && git commit -m 'chore: update {args.addon_name} to v{args.new_version}'")
        return 0
    elif success_count == 0:
        print("⚠️  No files needed updating (already at target version?)")
        return 0
    else:
        print("⚠️  Some files could not be updated")
        return 1


if __name__ == '__main__':
    sys.exit(main())
