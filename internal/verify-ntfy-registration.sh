#!/usr/bin/env bash
# Offline gate for the ntfy add-on: registration, translations, docs and assets stay complete (no docker).
# Manual invocation: bash internal/verify-ntfy-registration.sh
set -euo pipefail

ADDON_DIR="ntfy"

fail() { echo "✗ $1"; exit 1; }

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

echo "==> Registration"
python3 -I - <<'PY' || fail "base-image-config: ntfy block differs from gatus"
import sys, yaml
d = yaml.safe_load(open("internal/base-image-config.yaml"))["addons"]
sys.exit(0 if "ntfy" in d and d["ntfy"] == d["gatus"] else 1)
PY
[ "$(grep -c '^### \[ntfy\](./ntfy)' README.md)" = "1" ] || fail "root README needs exactly one ntfy heading"
echo "✓ root README and base-image config"

echo "==> Translations and docs"
python3 -I - <<'PY' || exit 1
import sys, yaml
cfg = yaml.safe_load(open("ntfy/config.yaml"))
keys = set(cfg["options"])
for lang in ("en", "de"):
    got = set(yaml.safe_load(open(f"ntfy/translations/{lang}.yaml"))["configuration"])
    if got != keys:
        print(f"✗ translation {lang} differs from options: {sorted(got ^ keys)}")
        sys.exit(1)
docs = open("ntfy/DOCS.md").read()
for key in sorted(keys):
    if f"`{key}`" not in docs:
        print(f"✗ DOCS.md does not mention option `{key}`")
        sys.exit(1)
for needle in ("72a005f5-ntfy", "f6c6b703-ntfy-server", "baseline_users",
               "reset acls", "clear cache", "reset everything"):
    if needle not in docs:
        print(f"✗ DOCS.md lacks '{needle}'")
        sys.exit(1)
PY
echo "✓ translations en/de and DOCS.md cover every option"

echo "==> Manifest"
for k in repository version_pattern version_strip; do
    [ "$(yget "${ADDON_DIR}/.upstream.yaml" "upstream.${k}")" != "null" ] || fail ".upstream.yaml lacks upstream.${k}"
done
[ "$(yget "${ADDON_DIR}/config.yaml" options.listen_port)" = "null" ] || fail "config.yaml has a listen_port option"
[ "$(yget "${ADDON_DIR}/config.yaml" host_network)" = "False" ] || fail "host_network must be false"
version="$(yget "${ADDON_DIR}/config.yaml" version)"
grep -q "^## \[${version}\]" "${ADDON_DIR}/CHANGELOG.md" || fail "CHANGELOG.md has no header for ${version}"
build_version="$(yget "${ADDON_DIR}/build.yaml" args.VERSION)"
grep -q "^\[release-shield\]:.*version-v${build_version}-" "${ADDON_DIR}/README.md" \
    || fail "README release-shield does not match build.yaml version ${build_version}"
echo "✓ upstream tracking, version links, network mode"

echo "==> Assets"
python3 -I - <<'PY' || exit 1
import struct, sys
d = open("ntfy/icon.png", "rb").read()
w, h = struct.unpack(">II", d[16:24])
if w != h:
    print(f"✗ icon.png is not square: {w}x{h}")
    sys.exit(1)
if d != open("ntfy/app/web/static/icon.png", "rb").read():
    print("✗ GUI icon differs from ntfy/icon.png")
    sys.exit(1)
PY
echo "✓ icon is square and the GUI copy is identical"
echo "All ntfy registration checks passed"
