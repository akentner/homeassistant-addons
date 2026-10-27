#!/usr/bin/env bash
# Verify the secrets-sync/ add-on scaffold: manifest sanity, image build, required tools in the image.
# Manual invocation: bash internal/verify-secrets-sync-scaffold.sh
set -euo pipefail

ADDON_DIR="secrets-sync"
IMAGE_TAG="secrets-sync-verify:local"

fail() { echo "✗ $1"; exit 1; }

# yq flavours differ between machines; python3 + PyYAML (HA tags tolerated) behaves the same everywhere.
# usage: yget <file> <dotted.path>  (prints "null" for a missing key, the length for lists)
yget() {
    python3 -I - "$1" "$2" <<'PY'
import sys, yaml
class L(yaml.SafeLoader): pass
L.add_multi_constructor("!", lambda loader, suffix, node: None)
node = yaml.load(open(sys.argv[1]), Loader=L)
for part in sys.argv[2].split("."):
    node = node.get(part) if isinstance(node, dict) else None
print("null" if node is None else len(node) if isinstance(node, list) else node)
PY
}

BW_CLI_VERSION="$(yget "${ADDON_DIR}/build.yaml" args.BW_CLI_VERSION)"

echo "==> Manifest checks"
[ "$(yget "${ADDON_DIR}/config.yaml" slug)" = "secrets_sync" ] || fail "slug is not secrets_sync"
[ "$(yget "${ADDON_DIR}/config.yaml" ingress_port)" = "8099" ] || fail "ingress_port is not 8099"
[ "$(yget "${ADDON_DIR}/config.yaml" arch)" = "1" ] || fail "arch must be amd64 only"
# HA reads a "key?" schema key literally as a required option named "key?" (options could not be saved)
! grep -Eq '^[[:space:]]+[A-Za-z_]+\?:' "${ADDON_DIR}/config.yaml" || fail "config.yaml schema has a key ending in '?'"
[ ! -e "${ADDON_DIR}/.upstream.yaml" ] || fail ".upstream.yaml must not exist (own code)"
for f in config.yaml build.yaml Dockerfile run.sh README.md DOCS.md CHANGELOG.md icon.png logo.png \
    translations/en.yaml translations/de.yaml; do
    [ -f "${ADDON_DIR}/${f}" ] || fail "missing ${ADDON_DIR}/${f}"
done
echo "✓ manifest and files"

# Every option key must be translated in en and de
for lang in en de; do
    for key in providers interval check_interval synthetic_keys collision_policy shrink_guard_percent log_level bitwarden sops; do
        [ "$(yget "${ADDON_DIR}/translations/${lang}.yaml" "configuration.${key}.name")" != "null" ] \
            || fail "translations/${lang}.yaml: no name for ${key}"
    done
done
for lang in en de; do
    for key in source git_url git_branch git_path git_username git_token; do
        [ "$(yget "${ADDON_DIR}/translations/${lang}.yaml" "configuration.sops.fields.${key}.name")" != "null" ] \
            || fail "translations/${lang}.yaml: no name for sops.${key}"
    done
done
# Schema keys must never end with "?" (HA marks optional values, the key must always exist in options)
if grep -E '^\s+[a-z_]+\?:' "${ADDON_DIR}/config.yaml" | grep -vE '^\s+(bitwarden|sops)\?:' | grep -q .; then
    fail "schema key ending with ? (only the bitwarden/sops blocks may be optional)"
fi
echo "✓ translations (en, de)"

echo "==> docker build"
docker build \
    --build-arg BUILD_FROM="$(yget "${ADDON_DIR}/build.yaml" build_from.amd64)" \
    --build-arg BW_CLI_VERSION="${BW_CLI_VERSION}" \
    -t "${IMAGE_TAG}" "${ADDON_DIR}"

echo "==> Tools in image"
docker run --rm --entrypoint sh "${IMAGE_TAG}" -c '
    set -e
    bw --version >/dev/null 2>&1 && echo "bw $(bw --version 2>/dev/null | tail -1)"
    sops --version 2>&1 | head -1
    age --version
    python3 -c "import yaml; print(\"PyYAML\", yaml.__version__)"
    python3 -c "import jinja2.sandbox; print(\"Jinja2\", jinja2.__version__)"
    git --version
    command -v ssh >/dev/null
    [ -x /opt/secrets-sync/app/bin/git-askpass ]
    [ -d /opt/secrets-sync/app ]
' || fail "tool check failed"
echo "✓ bw, sops, age, git, ssh, git-askpass (executable), PyYAML, Jinja2, app/ present"

docker run --rm --entrypoint sh "${IMAGE_TAG}" -c 'bw --version 2>/dev/null | tail -1' |
    grep -qx "${BW_CLI_VERSION}" || fail "bw version differs from BW_CLI_VERSION=${BW_CLI_VERSION}"
echo "✓ bw version matches build arg"

echo ""
echo "All secrets-sync scaffold verifications passed."
