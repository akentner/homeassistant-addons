# Makefile for Home Assistant Add-ons Repository
# Provides convenient commands for development and maintenance

.PHONY: help init install-hooks lint test clean format fix lint-markdown lint-markdown-fix check-all validate-versions update-version validate-dockerfiles docker-build-check build-addon

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Examples:"
	@echo "  make update-version ADDON=fritz-callmonitor2mqtt VERSION=1.7.2"
	@echo "  make update-version ADDON=fritz-callmonitor2mqtt VERSION=1.7.2 CHECK_RELEASE=yes"

init: ## Initialize development environment (install dependencies and hooks)
	@echo "🚀 Initializing development environment..."
	@echo "📦 Installing tools via uv..."
	uv tool install pre-commit
	uv tool install yamllint
	uv tool install shellcheck-py
	@echo "🔧 Installing pre-commit hooks..."
	pre-commit install
	pre-commit install --hook-type commit-msg 2>/dev/null || true
	@echo "✅ Installed tools:"
	@command -v pre-commit >/dev/null 2>&1 && echo "  ✅ pre-commit: $$(pre-commit --version)" || echo "  ❌ pre-commit: not found"
	@command -v yamllint >/dev/null 2>&1 && echo "  ✅ yamllint: $$(yamllint --version)" || echo "  ❌ yamllint: not found"
	@command -v shellcheck >/dev/null 2>&1 && echo "  ✅ shellcheck: $$(shellcheck --version | head -1)" || echo "  ❌ shellcheck: not found"
	@echo ""
	@echo "🔍 Running initial check on all files..."
	@pre-commit run --all-files || echo "⚠️  Some files need fixing - run 'make lint' to see details"
	@echo ""
	@echo "🎉 Development environment setup completed!"

install-hooks: ## Install pre-commit hooks
	@echo "🔧 Installing pre-commit hooks..."
	./scripts/setup-hooks.sh

# Removed install-markdownlint target - we use the Python fix-markdown-lines.py script instead

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
	pre-commit run prettier --all-files

lint-markdown-fix: ## Format and fix Markdown files with prettier
	@echo "🔧 Formatting Markdown files with prettier..."
	pre-commit run prettier --all-files

format: ## Format all files
	@echo "🎨 Formatting files..."
	pre-commit run --all-files trailing-whitespace
	pre-commit run --all-files end-of-file-fixer
	pre-commit run --all-files mixed-line-ending

fix: ## Auto-fix all fixable issues
	@echo "🔧 Auto-fixing all fixable issues..."
	pre-commit run --all-files || echo "⚠️  Some issues may require manual fixing"

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
			if ! python3 -c "import yaml; f=open('$${addon_dir}config.yaml'); d=yaml.safe_load(f); f.close(); exit(0 if 'name' in d else 1)" 2>/dev/null; then \
				echo "ERROR: $${addon_dir}config.yaml is invalid or missing 'name' field"; \
				exit 1; \
			fi; \
			echo "✅ $${addon_dir} validation passed"; \
		fi; \
	done

validate-versions: ## Validate add-on versioning consistency
	@echo "🔍 Validating add-on versions..."
	./scripts/validate-versions.sh

validate-dockerfiles: ## Validate ARG-before-FROM scope in all Dockerfiles
	@echo "🔍 Validating Dockerfile ARG scope..."
	./scripts/validate-dockerfile-args.sh

docker-build-check: ## Check Dockerfile correctness without a full build (hadolint + ARG scope validation)
	@echo "🐳 Checking Dockerfile correctness (no full build required)..."
	@echo "  Running hadolint (full ruleset, including DL3006 ARG-before-FROM)..."
	@FAILED=0; \
	for addon_dir in fritz-callmonitor2mqtt phone-logger meridian; do \
		if [ -f "$${addon_dir}/Dockerfile" ]; then \
			if ! hadolint \
				--ignore DL3018 \
				--ignore DL3059 \
				--ignore DL4006 \
				--ignore DL3016 \
				"$${addon_dir}/Dockerfile"; then \
				FAILED=$$((FAILED + 1)); \
			fi; \
		fi; \
	done; \
	if [ "$$FAILED" -gt 0 ]; then \
		echo "❌ $$FAILED Dockerfile(s) failed hadolint check."; \
		exit 1; \
	fi
	@echo "  Running ARG-before-FROM scope check..."
	@./scripts/validate-dockerfile-args.sh
	@echo "✅ All Dockerfile checks passed."

build-addon: ## Build an add-on image locally, replicating the HA build process (usage: make build-addon ADDON=meridian [TIMEOUT=600])
	@if [ -z "$(ADDON)" ]; then \
		echo "❌ Missing required parameter"; \
		echo "Usage: make build-addon ADDON=meridian"; \
		exit 1; \
	fi
	@if [ ! -f "$(ADDON)/build.yaml" ]; then \
		echo "❌ $(ADDON)/build.yaml not found"; \
		exit 1; \
	fi
	$(eval VERSION   := $(shell grep 'VERSION:' $(ADDON)/build.yaml | awk '{print $$2}' | tr -d '"'))
	$(eval BUILD_FROM := $(shell grep 'amd64:' $(ADDON)/build.yaml | awk '{print $$2}' | tr -d '"'))
	$(eval _TIMEOUT  := $(if $(TIMEOUT),$(TIMEOUT),600))
	@echo "🐳 Building $(ADDON) v$(VERSION) (BUILD_FROM=$(BUILD_FROM), timeout=$(_TIMEOUT)s)..."
	timeout $(_TIMEOUT) docker build \
		--progress=plain \
		--build-arg BUILD_FROM="$(BUILD_FROM)" \
		--build-arg VERSION="$(VERSION)" \
		--build-arg BUILD_ARCH="amd64" \
		--build-arg BUILD_DATE="$(shell date -u +%Y-%m-%dT%H:%M:%SZ)" \
		--build-arg BUILD_DESCRIPTION="local test build" \
		--build-arg BUILD_NAME="$(ADDON)" \
		--build-arg BUILD_REF="$(shell git rev-parse --short HEAD)" \
		--build-arg BUILD_REPOSITORY="$(shell git remote get-url origin | sed 's|.*github.com[:/]||;s|\.git||')" \
		--build-arg BUILD_VERSION="$(VERSION)" \
		-t "local/$(ADDON):$(VERSION)" \
		$(ADDON)/ \
	&& echo "" \
	&& echo "✅ Built image: local/$(ADDON):$(VERSION)" \
	&& echo "   Run with:  docker run --rm -it local/$(ADDON):$(VERSION) sh" \
	|| { EC=$$?; \
	     if [ $$EC -eq 124 ]; then \
	       echo "❌ Build timed out after $(_TIMEOUT)s (increase with TIMEOUT=<seconds>)"; \
	     else \
	       echo "❌ Build failed (exit code $$EC)"; \
	     fi; \
	     exit $$EC; }

update-version: ## Update add-on version (usage: make update-version ADDON=fritz-callmonitor2mqtt VERSION=1.7.2)
	@if [ -z "$(ADDON)" ] || [ -z "$(VERSION)" ]; then \
		echo "❌ Missing required parameters"; \
		echo "Usage: make update-version ADDON=fritz-callmonitor2mqtt VERSION=1.7.2"; \
		echo "       make update-version ADDON=fritz-callmonitor2mqtt VERSION=1.7.2 CHECK_RELEASE=yes"; \
		exit 1; \
	fi
	@echo "🔄 Updating $(ADDON) to version $(VERSION)..."
	@if [ "$(CHECK_RELEASE)" = "yes" ]; then \
		./scripts/update-version.py $(ADDON) $(VERSION) --check-release; \
	else \
		./scripts/update-version.py $(ADDON) $(VERSION); \
	fi
	@echo "🔍 Running validation..."
	@make validate-versions

check-all: lint validate-addons validate-versions validate-dockerfiles ## Run all checks (lint + validate + versions + dockerfile args)

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
