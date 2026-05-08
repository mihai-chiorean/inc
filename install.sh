#!/bin/bash
# Install claude-agents + skills into ~/.claude/{agents,skills}/
#
# Usage: ./install.sh [--link] [--dry-run] [--skills-only]
#   --link         Symlink instead of copy (keeps repo as source of truth)
#   --dry-run      Print what would happen without making any changes
#   --skills-only  Install skills only; skip agents. Recommended for the
#                  per-project staffing flow (use /staff to populate
#                  per-project .claude/agents/ instead of dumping all
#                  agents globally).
#
# Idempotent: re-running with the same flags is safe. Existing targets that
# already point to the right source are left alone; targets that point
# elsewhere are reported and skipped (no clobbering).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_TARGET="${HOME}/.claude/agents"
SKILLS_TARGET="${HOME}/.claude/skills"

MODE="copy"
DRY_RUN=0
SKILLS_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --link)         MODE="link" ;;
        --dry-run)      DRY_RUN=1 ;;
        --skills-only)  SKILLS_ONLY=1 ;;
        -h|--help)
            sed -n '/^# Usage/,/^set/p' "$0" | sed 's/^# //; /^set/d'
            exit 0 ;;
        *)              echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

prefix=""
if (( DRY_RUN )); then
    prefix="[dry-run] "
fi

if (( SKILLS_ONLY )); then
    echo "${prefix}Installing skills only to ${SKILLS_TARGET} (mode: ${MODE})"
    echo "${prefix}Skipping agents. Use /staff suggest in projects to populate .claude/agents/ per project."
else
    echo "${prefix}Installing to ${AGENTS_TARGET} and ${SKILLS_TARGET} (mode: ${MODE})"
fi

# Counters for the summary
LINKED=0
COPIED=0
ALREADY=0
SKIPPED=0

run() {
    if (( DRY_RUN )); then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

# Returns 0 if dst already points to src (i.e., no-op needed). Robust to
# symlinks resolved through readlink -f (tracks both relative and absolute).
already_pointing_at() {
    local src="$1" dst="$2"
    [[ -L "${dst}" ]] || return 1
    [[ "$(readlink -f "${dst}")" == "$(readlink -f "${src}")" ]]
}

# Install a file via ln or cp, depending on MODE. Idempotent: leaves existing
# correct symlinks alone; refuses to clobber unrelated targets.
install_file() {
    local src="$1" dst="$2"
    if [[ "${MODE}" == "link" ]]; then
        if already_pointing_at "${src}" "${dst}"; then
            ALREADY=$((ALREADY + 1))
            return 0
        fi
        if [[ -e "${dst}" && ! -L "${dst}" ]]; then
            echo "  SKIP    ${dst} — exists and is not a symlink (refusing to clobber)" >&2
            SKIPPED=$((SKIPPED + 1))
            return 0
        fi
        run ln -sf "${src}" "${dst}"
        LINKED=$((LINKED + 1))
    else
        run cp "${src}" "${dst}"
        COPIED=$((COPIED + 1))
    fi
}

# Install a directory as a whole. Idempotent in --link mode: leaves correct
# symlinks alone, refuses to clobber unrelated targets. In --copy mode: rm
# the target first (skill dirs are one unit, not merged).
install_dir() {
    local src="$1" dst="$2"
    if [[ "${MODE}" == "link" ]]; then
        if already_pointing_at "${src}" "${dst}"; then
            ALREADY=$((ALREADY + 1))
            return 0
        fi
        if [[ -e "${dst}" && ! -L "${dst}" ]]; then
            echo "  SKIP    ${dst} — exists and is not a symlink (refusing to clobber)" >&2
            SKIPPED=$((SKIPPED + 1))
            return 0
        fi
        run ln -sfn "${src}" "${dst}"
        LINKED=$((LINKED + 1))
    else
        if [[ -e "${dst}" && ! -L "${dst}" ]]; then
            run rm -rf "${dst}"
        fi
        run cp -r "${src}" "${dst}"
        COPIED=$((COPIED + 1))
    fi
}

run mkdir -p "${SKILLS_TARGET}"
if (( ! SKILLS_ONLY )); then
    run mkdir -p "${AGENTS_TARGET}"
fi

# ---- Agents (skipped if --skills-only) ----
agent_count=0
if (( ! SKILLS_ONLY )); then
    CATEGORIES=(bonus design engineering marketing product project-management studio-operations testing writing)
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
fi

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

# ---- README (only with full agent install) ----
if (( ! SKILLS_ONLY )); then
    install_file "${SCRIPT_DIR}/README.md" "${AGENTS_TARGET}/README.md"
fi

echo
if (( SKILLS_ONLY )); then
    echo "${prefix}Summary: ${skill_count} skill dirs processed (${LINKED} linked, ${COPIED} copied, ${ALREADY} already in place, ${SKIPPED} skipped)"
else
    echo "${prefix}Summary: ${agent_count} agents + ${skill_count} skill dirs processed (${LINKED} linked, ${COPIED} copied, ${ALREADY} already in place, ${SKIPPED} skipped)"
fi

if (( SKIPPED > 0 )); then
    echo
    echo "Some entries were skipped because the target exists and is not our symlink." >&2
    echo "Inspect them under ${AGENTS_TARGET} or ${SKILLS_TARGET} and remove or rename, then re-run." >&2
    exit 2
fi

echo "${prefix}Done."
