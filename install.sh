#!/bin/bash
# Install inc agents + skills into ~/.claude/{agents,skills}/
#
# Usage: ./install.sh [--link] [--dry-run] [--include-all-agents|--skills-only]
#                     [--cleanup|--auto-cleanup|--no-cleanup] [--codex]
#
#   --link               Symlink instead of copy (keeps repo as source of truth)
#   --dry-run            Print what would happen without making any changes
#   --codex              Also project the org set into $CODEX_HOME (~/.codex):
#                        org agents -> Codex subagent TOML, skills mirrored.
#
#   Agent installation (mutually exclusive):
#
#   (default)            Install ONLY agents tagged `scope: org` in their
#                        frontmatter — the small set that makes sense to load
#                        in every Claude Code session. Currently 7 agents:
#                        hiring-manager, blog-writer, social-amplifier,
#                        product-manager, tpm, tech-lead, security-auditor.
#                        Project-shaped agents stay in this repo; consumer
#                        projects pull a curated subset via /staff.
#
#   --include-all-agents Install all 55 agents to user scope. This is the
#                        old default (pre-MIT-375). NOT recommended: it
#                        defeats /staff's per-project curation, because
#                        all agents will be loaded in every session regardless
#                        of which project you're in.
#
#   --skills-only        Install zero agents (skills + bin only). For
#                        fully-curated setups where every project manages
#                        its own roster via /staff.
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
AGENTS_MODE="org"     # org (default — agents tagged scope: org) | all | none
CLEANUP_MODE="auto"   # auto (prompt if stale) | force-prompt | auto-yes | skip
CODEX_INSTALL=0       # 1 (--codex) — also emit org subagents + skills into ~/.codex
for arg in "$@"; do
    case "$arg" in
        --link)                MODE="link" ;;
        --dry-run)             DRY_RUN=1 ;;
        --skills-only)         AGENTS_MODE="none" ;;
        --include-all-agents)  AGENTS_MODE="all" ;;
        --cleanup)             CLEANUP_MODE="force-prompt" ;;
        --auto-cleanup)        CLEANUP_MODE="auto-yes" ;;
        --no-cleanup)          CLEANUP_MODE="skip" ;;
        --codex)               CODEX_INSTALL=1 ;;
        -h|--help)
            sed -n '/^# Usage/,/^set/p' "$0" | sed 's/^# //; /^set/d'
            exit 0 ;;
        *)                     echo "unknown arg: $arg" >&2; exit 2 ;;
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

case "$AGENTS_MODE" in
    none)
        echo "${prefix}Installing skills only to ${SKILLS_TARGET} (mode: ${MODE})"
        echo "${prefix}Skipping all agents. Use /staff suggest in projects to populate .claude/agents/ per project."
        ;;
    org)
        echo "${prefix}Installing org-scope agents + all skills to ${AGENTS_TARGET} and ${SKILLS_TARGET} (mode: ${MODE})"
        echo "${prefix}Project-shaped agents stay in this repo; use /staff in projects to stage them per-repo."
        ;;
    all)
        echo "${prefix}Installing ALL 55 agents + skills to ${AGENTS_TARGET} and ${SKILLS_TARGET} (mode: ${MODE})"
        echo "${prefix}WARNING: --include-all-agents loads every agent in every session, defeating /staff curation." >&2
        ;;
esac

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
if [[ "$AGENTS_MODE" != "none" ]]; then
    run mkdir -p "${AGENTS_TARGET}"
fi

# Returns 0 if the agent .md at $1 has `scope: org` in its frontmatter
# (between the first two `---` lines). Works on macOS bash3 + Linux.
is_org_agent() {
    # Case-insensitive match on `scope: org`. POSIX awk doesn't have a
    # case-insensitive flag, so we lowercase via tolower() before the regex.
    # Matches `scope: org`, `Scope: Org`, `SCOPE:    Org`, etc.
    awk '
        /^---$/ { n++; if (n==2) exit }
        n==1 { lc = tolower($0); if (lc ~ /^scope:[[:space:]]*org[[:space:]]*$/) { found=1; exit } }
        END { exit !found }
    ' "$1"
}

# ---- Agents ----
# AGENTS_MODE controls which agents (if any) get installed at user scope:
#   none → no agents installed (--skills-only)
#   org  → only agents tagged `scope: org` in their frontmatter (default)
#   all  → every agent .md in the category dirs (--include-all-agents)
agent_count=0
if [[ "$AGENTS_MODE" != "none" ]]; then
    CATEGORIES=(bonus design engineering marketing product project-management sales studio-operations testing writing)
    for category in "${CATEGORIES[@]}"; do
        src="${SCRIPT_DIR}/${category}"
        [[ -d "${src}" ]] || continue
        # Decide if this category has any agents to install before mkdir-ing.
        category_dir_made=0
        for file in "${src}"/*.md; do
            [[ -f "${file}" ]] || continue
            name="$(basename "${file}")"
            [[ "${name}" == "README.md" ]] && continue
            # Filter by scope when in org mode.
            if [[ "$AGENTS_MODE" == "org" ]] && ! is_org_agent "${file}"; then
                continue
            fi
            # Lazy-create the category dir on first matching agent.
            if (( ! category_dir_made )); then
                run mkdir -p "${AGENTS_TARGET}/${category}"
                category_dir_made=1
            fi
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

# ---- README (only if any agents are being installed) ----
if [[ "$AGENTS_MODE" != "none" ]]; then
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
case "$AGENTS_MODE" in
    none)
        echo "${prefix}Summary: ${skill_count} skill dirs + ${bin_count} bins processed (${LINKED} linked, ${COPIED} copied, ${ALREADY} already in place, ${SKIPPED} skipped)" ;;
    org)
        echo "${prefix}Summary: ${agent_count} org agents + ${skill_count} skill dirs + ${bin_count} bins processed (${LINKED} linked, ${COPIED} copied, ${ALREADY} already in place, ${SKIPPED} skipped)" ;;
    all)
        echo "${prefix}Summary: ${agent_count} agents (ALL) + ${skill_count} skill dirs + ${bin_count} bins processed (${LINKED} linked, ${COPIED} copied, ${ALREADY} already in place, ${SKIPPED} skipped)" ;;
esac

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

# Post-install: if we're in org/none mode and there are still non-org agents
# under ~/.claude/agents/ (e.g. user declined the cleanup prompt), surface
# this loudly. Otherwise the installer just installed 7 new symlinks while
# the OLD 48 stayed loaded — install reports success but the user-scope
# router still sees all 55. Codex caught this on MIT-375 review.
if [[ -x "$CLEANUP_SCRIPT" && "$AGENTS_MODE" != "all" ]]; then
    post_rc=0
    "$CLEANUP_SCRIPT" --status 2>/dev/null || post_rc=$?
    if [[ $post_rc -eq 10 ]]; then
        echo >&2
        echo "${prefix}WARNING: ${AGENTS_TARGET}/ contains stale leftovers from a prior install." >&2
        echo "${prefix}         The new ${AGENTS_MODE}-mode install added what it should, but old" >&2
        echo "${prefix}         agents are STILL loaded in every Claude Code session." >&2
        echo "${prefix}         Run: ./scripts/cleanup-prior-install.sh clean --yes" >&2
        echo "${prefix}              ./install.sh --link" >&2
        echo "${prefix}         Or re-run install.sh and answer 'y' to the cleanup prompt." >&2
    fi
fi

# Codex CLI parity (opt-in): emit org-scope agents as Codex subagent TOML and
# mirror skills into $CODEX_HOME. inc stays the source of truth; this is just
# the Codex-format projection of the same org set install.sh put in ~/.claude.
if (( CODEX_INSTALL )); then
    echo
    CODEX_HOME_DIR="${CODEX_HOME:-${HOME}/.codex}"
    if (( DRY_RUN )); then
        echo "${prefix}[dry-run] would emit org subagents + skills into ${CODEX_HOME_DIR}"
    else
        echo "${prefix}Codex: emitting org subagents + skills into ${CODEX_HOME_DIR} …"
        python3 "${SCRIPT_DIR}/skills/staff/scripts/codex_emit.py" \
            --user --skills --hr-repo "${SCRIPT_DIR}" || \
            echo "${prefix}note: codex emit failed (is python3 available?)" >&2
        echo "${prefix}Codex: restart \`codex\` to pick up new subagents/skills." >&2
    fi
fi

echo "${prefix}Done."
