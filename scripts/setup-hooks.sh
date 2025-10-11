#!/bin/bash

# Pre-commit hook setup script
# Run this script to install pre-commit hooks locally

set -e

echo "🔧 Setting up pre-commit hooks for Home Assistant Add-ons repository..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit..."
    pip install pre-commit
fi

# Install the hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Install commit-msg hook for conventional commits (optional)
pre-commit install --hook-type commit-msg || true

# Run hooks on all files to check setup
echo "Running pre-commit on all files to verify setup..."
pre-commit run --all-files

echo "✅ Pre-commit hooks successfully installed!"
echo ""
echo "ℹ️  The following hooks will now run before each commit:"
echo "   • YAML linting (yamllint)"
echo "   • Shell script linting (shellcheck)"
echo "   • Markdown linting (markdownlint)"
echo "   • GitHub Actions workflow linting (actionlint)"
echo "   • Dockerfile linting (hadolint)"
echo "   • General code formatting checks"
echo ""
echo "💡 To skip hooks temporarily, use: git commit --no-verify"
echo "💡 To run hooks manually: pre-commit run --all-files"
