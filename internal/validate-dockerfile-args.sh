#!/usr/bin/env bash
# validate-dockerfile-args.sh
#
# Checks that every ARG used in a FROM instruction is declared in the global
# scope (before the first FROM).  Docker silently resolves undeclared ARGs in
# FROM to an empty string, which causes the build to fail with:
#   "base name (<ARG_NAME>) should not be blank"
#
# Usage:
#   ./internal/validate-dockerfile-args.sh               # checks all add-on Dockerfiles
#   ./internal/validate-dockerfile-args.sh path/to/Dockerfile ...

set -euo pipefail

ERRORS=0

check_dockerfile() {
    local file="$1"
    local first_from_seen=false
    local -A global_args=()
    local lineno=0
    local error_count=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        lineno=$((lineno + 1))
        # Strip leading whitespace and comments
        local stripped
        stripped=$(echo "$line" | sed 's/^[[:space:]]*//' | sed 's/#.*//')
        [[ -z "$stripped" ]] && continue

        # Collect ARG declarations before first FROM (global scope)
        if [[ "$first_from_seen" == false ]] && [[ "$stripped" =~ ^ARG[[:space:]]+([A-Za-z0-9_]+) ]]; then
            global_args["${BASH_REMATCH[1]}"]=1
        fi

        # Check FROM instructions for $VAR or ${VAR} references
        if [[ "$stripped" =~ ^FROM[[:space:]] ]]; then
            if [[ "$first_from_seen" == false ]]; then
                first_from_seen=true
            else
                # Extract the image reference (first token after FROM, ignore AS alias)
                local image
                image=$(echo "$stripped" | awk '{print $2}')
                # Find all variable references in the image name
                local varname
                for varname in $(echo "$image" | grep -oE '\$\{?[A-Za-z0-9_]+\}?' | sed 's/[${}]//g'); do
                    if [[ -z "${global_args[$varname]+_}" ]]; then
                        echo "ERROR: $file:$lineno — \$$varname used in FROM but not declared before the first FROM (global ARG scope)"
                        error_count=$((error_count + 1))
                    fi
                done
            fi
        fi
    done < "$file"

    return "$error_count"
}

# Determine which files to check
if [[ $# -gt 0 ]]; then
    DOCKERFILES=("$@")
else
    # Auto-discover: all Dockerfiles in add-on directories (one level deep)
    mapfile -t DOCKERFILES < <(find . -maxdepth 2 -name "Dockerfile" | grep -v ".git" | sort)
fi

if [[ ${#DOCKERFILES[@]} -eq 0 ]]; then
    echo "No Dockerfiles found."
    exit 0
fi

for dockerfile in "${DOCKERFILES[@]}"; do
    if [[ ! -f "$dockerfile" ]]; then
        echo "WARNING: $dockerfile not found, skipping"
        continue
    fi
    if ! check_dockerfile "$dockerfile"; then
        ERRORS=$((ERRORS + 1))
    fi
done

if [[ $ERRORS -gt 0 ]]; then
    echo ""
    echo "FAIL: $ERRORS Dockerfile(s) have ARG-before-FROM violations."
    echo "      Declare every ARG used in a FROM instruction before the first FROM in the file."
    exit 1
else
    echo "OK: All Dockerfiles pass ARG-before-FROM check."
    exit 0
fi
