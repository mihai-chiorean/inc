#!/bin/bash
# Install claude-agents + skills into ~/.claude/{agents,skills}/
# Usage: ./install.sh [--link] [--dry-run]
#   --link:    symlink instead of copy (keeps repo as source of truth)
#   --dry-run: print what would happen without making any changes
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_TARGET="${HOME}/.claude/agents"
SKILLS_TARGET="${HOME}/.claude/skills"

MODE="copy"
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --link)    MODE="link" ;;
        --dry-run) DRY_RUN=1 ;;
        *)         echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

prefix=""
if (( DRY_RUN )); then
    prefix="[dry-run] "
fi

echo "${prefix}Installing to ${AGENTS_TARGET} and ${SKILLS_TARGET} (mode: ${MODE})"

run() {
    if (( DRY_RUN )); then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

# Install a file via ln -sf or cp, depending on MODE
install_file() {
    local src="$1" dst="$2"
    if [[ "${MODE}" == "link" ]]; then
        run ln -sf "${src}" "${dst}"
    else
        run cp "${src}" "${dst}"
    fi
}

# Install a directory as a whole. If dst exists and isn't a symlink, remove it
# first (skill dirs are one unit, not merged). Then symlink or copy.
install_dir() {
    local src="$1" dst="$2"
    if [[ -e "${dst}" && ! -L "${dst}" ]]; then
        run rm -rf "${dst}"
    fi
    if [[ "${MODE}" == "link" ]]; then
        run ln -sfn "${src}" "${dst}"
    else
        run cp -r "${src}" "${dst}"
    fi
}

run mkdir -p "${AGENTS_TARGET}"
run mkdir -p "${SKILLS_TARGET}"

# ---- Agents ----
CATEGORIES=(bonus design engineering marketing product project-management studio-operations testing writing)

agent_count=0
for category in "${CATEGORIES[@]}"; do
    src="${SCRIPT_DIR}/${category}"
    [[ -d "${src}" ]] || continue
    run mkdir -p "${AGENTS_TARGET}/${category}"
    for file in "${src}"/*.md; do
        [[ -f "${file}" ]] || continue
        name="$(basename "${file}")"
        install_file "${file}" "${AGENTS_TARGET}/${category}/${name}"
        agent_count=$((agent_count + 1))
    done
done

# ---- Skills ----
skill_count=0
if [[ -d "${SCRIPT_DIR}/skills" ]]; then
    for skill_dir in "${SCRIPT_DIR}/skills"/*/; do
        [[ -d "${skill_dir}" ]] || continue
        name="$(basename "${skill_dir}")"
        install_dir "${skill_dir%/}" "${SKILLS_TARGET}/${name}"
        skill_count=$((skill_count + 1))
    done
fi

# ---- README ----
install_file "${SCRIPT_DIR}/README.md" "${AGENTS_TARGET}/README.md"

echo "${prefix}Installed ${agent_count} agents and ${skill_count} skills"
echo "${prefix}Done."
