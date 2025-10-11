# Makefile for Home Assistant Add-ons Repository
# Provides convenient commands for development and maintenance

.PHONY: help init install-hooks lint test clean format check-all

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

init: ## Initialize development environment (install dependencies and hooks)
	@echo "🚀 Initializing development environment..."
	@echo "📦 Installing development dependencies..."
	@if command -v apt-get >/dev/null 2>&1; then \
		echo "Installing via apt-get (Debian/Ubuntu)..."; \
		sudo apt-get update && sudo apt-get install -y yamllint python3-venv || echo "⚠️  Package installation failed"; \
		echo "Setting up Python virtual environment..."; \
		python3 -m venv ~/.local/venv-lint || echo "⚠️  Failed to create virtual environment"; \
		if [ -f ~/.local/venv-lint/bin/pip ]; then \
			~/.local/venv-lint/bin/pip install pre-commit shellcheck-py || echo "⚠️  Some Python dependencies failed to install"; \
			echo "Creating symlinks..."; \
			mkdir -p ~/.local/bin; \
			ln -sf ~/.local/venv-lint/bin/pre-commit ~/.local/bin/pre-commit 2>/dev/null || echo "pre-commit symlink exists"; \
		fi; \
		if command -v npm >/dev/null 2>&1; then \
			echo "Installing markdownlint-cli2 via npm..."; \
			npm install -g markdownlint-cli2 || echo "⚠️  markdownlint-cli2 installation failed"; \
		else \
			echo "⚠️  npm not found, skipping markdownlint-cli2 installation"; \
		fi; \
	elif command -v pip3 >/dev/null 2>&1; then \
		echo "Using pip3 with --user..."; \
		pip3 install --user pre-commit yamllint shellcheck-py markdownlint-cli2 || \
		pip3 install --user --break-system-packages pre-commit yamllint shellcheck-py markdownlint-cli2 || \
		echo "⚠️  Python dependencies installation failed"; \
	elif command -v pip >/dev/null 2>&1; then \
		echo "Using pip with --user..."; \
		pip install --user pre-commit yamllint shellcheck-py markdownlint-cli2 || echo "⚠️  Some Python dependencies failed to install"; \
	else \
		echo "⚠️  No package manager found. Please install Python dependencies manually:"; \
		echo "   pip install --user pre-commit yamllint shellcheck-py markdownlint-cli2"; \
	fi
	@echo "📥 Installing actionlint..."
	@if command -v go >/dev/null 2>&1; then \
		echo "Installing actionlint via go install..."; \
		go install github.com/rhymond/actionlint/cmd/actionlint@latest || echo "⚠️  Failed to install actionlint via go"; \
	elif command -v curl >/dev/null 2>&1; then \
		echo "Trying direct download..."; \
		mkdir -p /tmp/actionlint-install; \
		curl -L https://github.com/rhymond/actionlint/releases/download/v1.7.3/actionlint_1.7.3_linux_amd64.tar.gz -o /tmp/actionlint-install/actionlint.tar.gz 2>/dev/null || true; \
		if [ -f /tmp/actionlint-install/actionlint.tar.gz ] && tar -tf /tmp/actionlint-install/actionlint.tar.gz >/dev/null 2>&1; then \
			cd /tmp/actionlint-install && tar -xzf actionlint.tar.gz 2>/dev/null && \
			(sudo mv actionlint /usr/local/bin/ 2>/dev/null || \
			 mkdir -p ~/.local/bin && mv actionlint ~/.local/bin/ 2>/dev/null || \
			 echo "⚠️  Could not install actionlint. Please add it to your PATH manually."); \
		else \
			echo "⚠️  actionlint download failed. You can install it manually later."; \
		fi; \
		rm -rf /tmp/actionlint-install 2>/dev/null || true; \
	else \
		echo "⚠️  Neither go nor curl found, skipping actionlint installation"; \
	fi
	@echo "🔧 Installing pre-commit hooks..."
	@if command -v pre-commit >/dev/null 2>&1; then \
		pre-commit install || echo "⚠️  Failed to install pre-commit hooks"; \
		pre-commit install --hook-type commit-msg 2>/dev/null || echo "ℹ️  commit-msg hook not available"; \
	else \
		echo "⚠️  pre-commit not found. Please install it first: pip install pre-commit"; \
	fi
	@echo "✅ Checking installation..."
	@echo "Installed tools:"
	@command -v pre-commit >/dev/null 2>&1 && echo "  ✅ pre-commit: $$(pre-commit --version)" || echo "  ❌ pre-commit: not found"
	@command -v yamllint >/dev/null 2>&1 && echo "  ✅ yamllint: $$(yamllint --version)" || echo "  ❌ yamllint: not found"
	@command -v shellcheck >/dev/null 2>&1 && echo "  ✅ shellcheck: $$(shellcheck --version | head -1)" || echo "  ❌ shellcheck: not found"
	@command -v markdownlint-cli2 >/dev/null 2>&1 && echo "  ✅ markdownlint-cli2: found" || echo "  ❌ markdownlint-cli2: not found"
	@command -v actionlint >/dev/null 2>&1 && echo "  ✅ actionlint: $$(actionlint --version)" || echo "  ❌ actionlint: not found"
	@echo ""
	@if command -v pre-commit >/dev/null 2>&1; then \
		echo "🔍 Running initial check on all files..."; \
		pre-commit run --all-files || echo "⚠️  Some files need fixing - run 'make lint' to see details"; \
	else \
		echo "⚠️  Skipping initial check (pre-commit not available)"; \
	fi
	@echo ""
	@echo "🎉 Development environment setup completed!"
	@echo ""
	@echo "📋 Next steps:"
	@echo "   • If any tools are missing, install them manually"
	@echo "   • Run 'make lint' to check code quality"
	@echo "   • Run 'make validate-addons' to validate add-on configurations"
	@echo "   • Run 'make check-all' to run all checks"
	@if command -v pre-commit >/dev/null 2>&1; then \
		echo "   • Pre-commit hooks are now active for git commits"; \
	else \
		echo "   • Install pre-commit to enable automatic git hooks"; \
	fi

install-hooks: ## Install pre-commit hooks
	@echo "🔧 Installing pre-commit hooks..."
	./scripts/setup-hooks.sh

lint: ## Run all linting checks
	@echo "🔍 Running lint checks..."
	pre-commit run --all-files

lint-yaml: ## Lint only YAML files
	@echo "🔍 Linting YAML files..."
	find . -name "*.yaml" -o -name "*.yml" | grep -v ".git" | xargs yamllint -d relaxed

lint-actions: ## Lint GitHub Actions workflows
	@echo "🔍 Linting GitHub Actions workflows..."
	actionlint

lint-shell: ## Lint shell scripts
	@echo "🔍 Linting shell scripts..."
	find . -name "*.sh" | grep -v ".git" | xargs shellcheck -e SC1091 -e SC2034

lint-markdown: ## Lint Markdown files
	@echo "🔍 Linting Markdown files..."
	markdownlint-cli2 "**/*.md" "#node_modules" "#.git"

format: ## Format all files
	@echo "🎨 Formatting files..."
	pre-commit run --all-files trailing-whitespace
	pre-commit run --all-files end-of-file-fixer
	pre-commit run --all-files mixed-line-ending

validate-addons: ## Validate add-on configurations
	@echo "✅ Validating add-on configurations..."
	@for addon_dir in */; do \
		if [ -f "$${addon_dir}config.yaml" ]; then \
			echo "Validating $${addon_dir}..."; \
			for required_file in "config.yaml" "Dockerfile" "run.sh"; do \
				if [ ! -f "$${addon_dir}$${required_file}" ]; then \
					echo "ERROR: $${addon_dir} missing required file: $${required_file}"; \
					exit 1; \
				fi; \
			done; \
			if ! yq eval '.name' "$${addon_dir}config.yaml" >/dev/null 2>&1; then \
				echo "ERROR: $${addon_dir}config.yaml is invalid or missing 'name' field"; \
				exit 1; \
			fi; \
			echo "✅ $${addon_dir} validation passed"; \
		fi; \
	done

check-all: lint validate-addons ## Run all checks (lint + validate)

test: check-all ## Run all tests and checks

clean: ## Clean cache and temporary files
	@echo "🧹 Cleaning up..."
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	rm -rf .mypy_cache/
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*~" -delete

install-dev: ## Install development dependencies (deprecated, use 'make init')
	@echo "⚠️  'make install-dev' is deprecated. Please use 'make init' instead."
	@$(MAKE) init

ci: ## Run CI pipeline locally
	@echo "🚀 Running CI pipeline..."
	$(MAKE) check-all
