#!/bin/bash
# Install claude-agents into ~/.claude/agents/
# Usage: ./install.sh [--link]
#   --link: symlink instead of copy (keeps repo as source of truth)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${HOME}/.claude/agents"

MODE="copy"
if [[ "${1:-}" == "--link" ]]; then
    MODE="link"
fi

echo "Installing claude-agents to ${TARGET} (mode: ${MODE})"

mkdir -p "${TARGET}"

CATEGORIES=(bonus design engineering marketing product project-management studio-operations testing)

count=0
for category in "${CATEGORIES[@]}"; do
    src="${SCRIPT_DIR}/${category}"
    [[ -d "${src}" ]] || continue
    mkdir -p "${TARGET}/${category}"
    for file in "${src}"/*.md; do
        [[ -f "${file}" ]] || continue
        name="$(basename "${file}")"
        if [[ "${MODE}" == "link" ]]; then
            ln -sf "${file}" "${TARGET}/${category}/${name}"
        else
            cp "${file}" "${TARGET}/${category}/${name}"
        fi
        count=$((count + 1))
    done
done

# Install README
if [[ "${MODE}" == "link" ]]; then
    ln -sf "${SCRIPT_DIR}/README.md" "${TARGET}/README.md"
else
    cp "${SCRIPT_DIR}/README.md" "${TARGET}/README.md"
fi

echo "Installed ${count} agents to ${TARGET}"
echo "Done."
