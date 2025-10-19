#!/usr/bin/env python3
"""
Update Add-on Version Script
Automatically updates version numbers across all required files for a Home Assistant Add-on.
"""
import re
import sys
import argparse
from pathlib import Path
import yaml


def update_config_yaml(addon_dir: Path, new_version: str) -> bool:
    """Update version in config.yaml"""
    config_file = addon_dir / "config.yaml"
    if not config_file.exists():
        print(f"❌ {config_file} not found")
        return False

    try:
        with open(config_file, 'r') as f:
            content = f.read()

        # Pattern: version: "X.Y.Z-N"
        pattern = r'^(\s*version:\s*["\'])([0-9]+\.[0-9]+\.[0-9]+-[0-9]+)(["\'].*?)$'
        new_content = re.sub(
            pattern,
            f'\\g<1>{new_version}-0\\g<3>',
            content,
            flags=re.MULTILINE
        )

        if new_content != content:
            with open(config_file, 'w') as f:
                f.write(new_content)
            print(f"✅ Updated {config_file}: version → {new_version}-0")
            return True
        else:
            print(f"⚠️  No version found in {config_file}")
            return False

    except Exception as e:
        print(f"❌ Error updating {config_file}: {e}")
        return False


def update_build_yaml(addon_dir: Path, new_version: str) -> bool:
    """Update VERSION in build.yaml"""
    build_file = addon_dir / "build.yaml"
    if not build_file.exists():
        print(f"❌ {build_file} not found")
        return False

    try:
        with open(build_file, 'r') as f:
            content = f.read()

        # Pattern: VERSION: "X.Y.Z"
        pattern = r'^(\s*VERSION:\s*["\'])([0-9]+\.[0-9]+\.[0-9]+)(["\'].*?)$'
        new_content = re.sub(
            pattern,
            f'\\g<1>{new_version}\\g<3>',
            content,
            flags=re.MULTILINE
        )

        if new_content != content:
            with open(build_file, 'w') as f:
                f.write(new_content)
            print(f"✅ Updated {build_file}: VERSION → {new_version}")
            return True
        else:
            print(f"⚠️  No VERSION found in {build_file}")
            return False

    except Exception as e:
        print(f"❌ Error updating {build_file}: {e}")
        return False


def update_readme_md(addon_dir: Path, new_version: str) -> bool:
    """Update version badges and links in README.md"""
    readme_file = addon_dir / "README.md"
    if not readme_file.exists():
        print(f"❌ {readme_file} not found")
        return False

    try:
        with open(readme_file, 'r') as f:
            content = f.read()

        original_content = content

        # Update version badge: version-vX.Y.Z-blue.svg
        content = re.sub(
            r'version-v[0-9]+\.[0-9]+\.[0-9]+-blue\.svg',
            f'version-v{new_version}-blue.svg',
            content
        )

        # Update release tree links: /tree/vX.Y.Z
        content = re.sub(
            r'/tree/v[0-9]+\.[0-9]+\.[0-9]+',
            f'/tree/v{new_version}',
            content
        )

        if content != original_content:
            with open(readme_file, 'w') as f:
                f.write(content)
            print(f"✅ Updated {readme_file}: badges and links → v{new_version}")
            return True
        else:
            print(f"⚠️  No version patterns found in {readme_file}")
            return False

    except Exception as e:
        print(f"❌ Error updating {readme_file}: {e}")
        return False


def validate_version_format(version: str) -> bool:
    """Validate that version follows semantic versioning (X.Y.Z)"""
    pattern = r'^[0-9]+\.[0-9]+\.[0-9]+$'
    return re.match(pattern, version) is not None


def check_github_release(version: str, addon_name: str) -> bool:
    """Check if the GitHub release exists (optional check)"""
    try:
        import urllib.request
        url = f"https://github.com/akentner/{addon_name}/releases/tag/v{version}"
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req) as response:
            return response.status == 200
    except:
        return False  # Don't fail if we can't check


def main():
    parser = argparse.ArgumentParser(description='Update add-on version across all files')
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

    print(f"🔄 Updating {args.addon_name} to version {args.new_version}")

    if args.dry_run:
        print("🏃 DRY RUN MODE - No files will be modified")

    # Optional: Check if GitHub release exists
    if args.check_release:
        print("🔍 Checking if GitHub release exists...")
        if check_github_release(args.new_version, args.addon_name):
            print(f"✅ GitHub release v{args.new_version} found")
        else:
            print(f"⚠️  GitHub release v{args.new_version} not found or not accessible")
            response = input("Continue anyway? [y/N]: ")
            if response.lower() != 'y':
                return 1

    success_count = 0
    total_files = 3

    if args.dry_run:
        print("\n📋 Would update the following files:")
        print(f"   • {addon_dir}/config.yaml: version → {args.new_version}-0")
        print(f"   • {addon_dir}/build.yaml: VERSION → {args.new_version}")
        print(f"   • {addon_dir}/README.md: badges and links → v{args.new_version}")
        return 0

    # Update all files
    print()
    if update_config_yaml(addon_dir, args.new_version):
        success_count += 1

    if update_build_yaml(addon_dir, args.new_version):
        success_count += 1

    if update_readme_md(addon_dir, args.new_version):
        success_count += 1

    print(f"\n📊 Updated {success_count}/{total_files} files")

    if success_count == total_files:
        print("🎉 All files updated successfully!")
        print(f"\n💡 Next steps:")
        print(f"   • Run 'make validate-versions' to verify")
        print(f"   • Run 'make check-all' for full validation")
        print(f"   • Commit changes: git add -A && git commit -m 'Update {args.addon_name} to v{args.new_version}'")
        return 0
    else:
        print("⚠️  Some files could not be updated")
        return 1


if __name__ == '__main__':
    sys.exit(main())
