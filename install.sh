#!/bin/bash
# Install inc agents + skills into ~/.claude/{agents,skills}/
#
# Usage: ./install.sh [--link] [--dry-run] [--skills-only] [--cleanup|--auto-cleanup|--no-cleanup]
#   --link            Symlink instead of copy (keeps repo as source of truth)
#   --dry-run         Print what would happen without making any changes
#   --skills-only     Install skills only; skip agents. Recommended for the
#                     per-project staffing flow (use /staff to populate
#                     per-project .claude/agents/ instead of dumping all
#                     agents globally).
#   --cleanup         Print the cleanup inventory at startup (preview),
#                     then proceed. Useful for confirming nothing-to-clean
#                     before an install. Does NOT change the prompt
#                     behavior — the prompt fires automatically when
#                     stale items are detected (default --auto mode).
#   --auto-cleanup    Run cleanup-prior-install.sh non-interactively before
#                     install. Useful for CI or re-runs that won't have a TTY.
#   --no-cleanup      Skip the cleanup check entirely. Use when you know the
#                     environment is clean.
#
# Default behavior (interactive): on startup, inventory existing
# ~/.claude/{agents,skills} and ~/.local/bin/ for leftovers from a prior
# claude-agents (pre-rebrand) or partial inc install. If stale items found,
# prompt: "Found N stale items. Clean up first? [y/N/show]". On `y`, run
# scripts/cleanup-prior-install.sh clean --yes (with --dry-run if flagged).
# On `show`, print the inventory and re-prompt. On `n` (default), proceed —
# install.sh will refuse to clobber and report SKIPPED items at the end.
#
# Idempotent: re-running with the same flags is safe. Existing targets that
# already point to the right source are left alone; targets that point
# elsewhere are reported and skipped (no clobbering).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_TARGET="${HOME}/.claude/agents"
SKILLS_TARGET="${HOME}/.claude/skills"
BIN_TARGET="${HOME}/.local/bin"

MODE="copy"
DRY_RUN=0
SKILLS_ONLY=0
CLEANUP_MODE="auto"   # auto (prompt if stale) | force-prompt | auto-yes | skip
for arg in "$@"; do
    case "$arg" in
        --link)          MODE="link" ;;
        --dry-run)       DRY_RUN=1 ;;
        --skills-only)   SKILLS_ONLY=1 ;;
        --cleanup)       CLEANUP_MODE="force-prompt" ;;
        --auto-cleanup)  CLEANUP_MODE="auto-yes" ;;
        --no-cleanup)    CLEANUP_MODE="skip" ;;
        -h|--help)
            sed -n '/^# Usage/,/^set/p' "$0" | sed 's/^# //; /^set/d'
            exit 0 ;;
        *)               echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

prefix=""
if (( DRY_RUN )); then
    prefix="[dry-run] "
fi

# ---- Cleanup check (delegated to scripts/cleanup-prior-install.sh) ----
# Detect prior-install leftovers BEFORE doing the install. Uses the helper's
# --status mode (exit 0 = clean, 10 = stale) instead of parsing summary text.
CLEANUP_SCRIPT="${SCRIPT_DIR}/scripts/cleanup-prior-install.sh"
maybe_run_cleanup() {
    [[ -x "$CLEANUP_SCRIPT" ]] || return 0
    [[ "$CLEANUP_MODE" == "skip" ]] && return 0

    # Machine-readable status check. Capture the exit code via `|| rc=$?`
    # — `if ! cmd; then` would corrupt $? (the `!` operator's negation
    # becomes the result, so $? inside the then-branch is always 0 or 1,
    # not the script's actual exit code). Codex caught this in MIT-372
    # review: --status exit 10 (stale) was always being read as 0 and the
    # gate was silently skipping the prompt.
    local has_stale=0
    local rc=0
    "$CLEANUP_SCRIPT" --status 2>/dev/null || rc=$?
    if [[ $rc -eq 10 ]]; then
        has_stale=1
    elif [[ $rc -ne 0 ]]; then
        echo "${prefix}cleanup status check failed (rc=$rc); skipping cleanup gate." >&2
        return 0
    fi

    if (( ! has_stale )); then
        case "$CLEANUP_MODE" in
            auto)            return 0 ;;   # quiet: nothing to do
            auto-yes)        echo "${prefix}cleanup check: nothing to clean."; return 0 ;;
            force-prompt)    "$CLEANUP_SCRIPT" inventory; return 0 ;;
        esac
    fi

    # has_stale=1 — show the inventory and decide.
    echo
    "$CLEANUP_SCRIPT" inventory
    echo

    local clean_args=("clean")
    (( DRY_RUN )) && clean_args+=("--dry-run")

    case "$CLEANUP_MODE" in
        auto-yes)
            echo "${prefix}--auto-cleanup set; running cleanup non-interactively."
            "$CLEANUP_SCRIPT" "${clean_args[@]}" --yes
            echo
            ;;
        *)
            # auto (with stale found) OR force-prompt: ask the user.
            while true; do
                read -r -p "Clean up these leftovers before installing? [y/N/show] " ans
                # Normalize: trim whitespace, lowercase (bash 3.2-compatible).
                ans="$(echo "$ans" | tr '[:upper:]' '[:lower:]' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                case "$ans" in
                    y|yes)
                        "$CLEANUP_SCRIPT" "${clean_args[@]}" --yes
                        echo
                        break ;;
                    n|no|"")
                        echo "Skipping cleanup; install will SKIP any conflicting targets."
                        echo
                        break ;;
                    show|s)
                        "$CLEANUP_SCRIPT" inventory
                        echo
                        ;;
                    *)
                        echo "Answer y, n, or show." ;;
                esac
            done
            ;;
    esac
}

# Run cleanup gate before any install action.
maybe_run_cleanup

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

# Returns 0 if dst already points to src (i.e., no-op needed).
# Compares the symlink's raw target against src. install.sh creates symlinks
# with absolute paths (the SCRIPT_DIR computation produces an absolute path),
# so the target string equals src for our-symlinks. NOTE: this used to use
# `readlink -f`, but that's a GNU extension — macOS readlink (BSD) doesn't
# support -f, and `readlink -f` would silently fail with "illegal option" and
# break the install on a fresh Mac.
already_pointing_at() {
    local src="$1" dst="$2"
    [[ -L "${dst}" ]] || return 1
    [[ "$(readlink "${dst}")" == "${src}" ]]
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

# ---- Skill binaries on PATH ----
# Each skill that ships a bin/ directory gets its executables symlinked
# into ~/.local/bin/ so they're invokable as plain commands instead of
# `python3 ~/.claude/skills/<skill>/scripts/foo.py`.
bin_count=0
if [[ -d "${SCRIPT_DIR}/skills" ]]; then
    run mkdir -p "${BIN_TARGET}"
    for skill_dir in "${SCRIPT_DIR}/skills"/*/; do
        bin_dir="${skill_dir}bin"
        [[ -d "${bin_dir}" ]] || continue
        for entry in "${bin_dir}"/*; do
            [[ -f "${entry}" && -x "${entry}" ]] || continue
            name="$(basename "${entry}")"
            install_file "${entry}" "${BIN_TARGET}/${name}"
            bin_count=$((bin_count + 1))
        done
    done
fi

echo
if (( SKILLS_ONLY )); then
    echo "${prefix}Summary: ${skill_count} skill dirs + ${bin_count} bins processed (${LINKED} linked, ${COPIED} copied, ${ALREADY} already in place, ${SKIPPED} skipped)"
else
    echo "${prefix}Summary: ${agent_count} agents + ${skill_count} skill dirs + ${bin_count} bins processed (${LINKED} linked, ${COPIED} copied, ${ALREADY} already in place, ${SKIPPED} skipped)"
fi

if (( bin_count > 0 )); then
    case ":${PATH}:" in
        *":${BIN_TARGET}:"*) : ;;
        *) echo "${prefix}note: ${BIN_TARGET} is not on your PATH; binaries won't be invokable until you add it" >&2 ;;
    esac
fi

if (( SKIPPED > 0 )); then
    echo
    echo "Some entries were skipped because the target exists and is not our symlink." >&2
    echo "Inspect them under ${AGENTS_TARGET} or ${SKILLS_TARGET} and remove or rename, then re-run." >&2
    exit 2
fi

echo "${prefix}Done."
