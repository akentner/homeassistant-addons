#!/bin/bash

# Pre-commit and pre-push hook setup script
# Run this script to install hooks locally

set -e

echo "🔧 Setting up hooks for Home Assistant Add-ons repository..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit via uv..."
    uv tool install pre-commit
fi

# Install the hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Install commit-msg hook for conventional commits (optional)
pre-commit install --hook-type commit-msg || true

# Install pre-push hook for version-tag sync
echo "Installing pre-push hook (version tag sync)..."
GIT_ROOT=$(git rev-parse --show-toplevel)
HOOK_TARGET="$GIT_ROOT/.git/hooks/pre-push"
HOOK_SOURCE="$GIT_ROOT/scripts/check-version-tags.sh"
if [[ -f "$HOOK_SOURCE" ]]; then
    cp "$HOOK_SOURCE" "$HOOK_TARGET"
    chmod +x "$HOOK_TARGET"
    echo "  ✓ Installed $HOOK_TARGET"
else
    echo "  ⚠️  $HOOK_SOURCE not found — pre-push hook not installed"
fi

# Run hooks on all files to check setup
echo "Running pre-commit on all files to verify setup..."
pre-commit run --all-files

echo "✅ Hooks successfully installed!"
echo ""
echo "ℹ️  The following hooks will now run:"
echo "   Before commit:"
echo "   • YAML linting (yamllint)"
echo "   • Shell script linting (shellcheck)"
echo "   • Markdown linting (markdownlint)"
echo "   • GitHub Actions workflow linting (actionlint)"
echo "   • Dockerfile linting (hadolint)"
echo "   • General code formatting checks"
echo "   Before push:"
echo "   • Version-tag sync (verifies v<version> tag exists for any bumped addon)"
echo ""
echo "💡 To skip pre-commit hooks temporarily: git commit --no-verify"
echo "💡 To skip pre-push hook temporarily:    git push --no-verify"
echo "💡 To run hooks manually: pre-commit run --all-files"
