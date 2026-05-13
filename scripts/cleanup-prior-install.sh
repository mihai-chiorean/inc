#!/bin/bash
# cleanup-prior-install.sh — detect and remove leftovers from a prior
# claude-agents (pre-rebrand) or partial inc install.
#
# Subcommands:
#   inventory   (default)  List what would be cleaned. Read-only. Exit 0.
#   clean                  Move ~/.claude/agents/ to a timestamped backup
#                          dir; delete inc-owned symlinks under
#                          ~/.claude/skills/ and ~/.local/bin/ that are
#                          broken or point at the old workspace path.
#                          Prompts for confirmation unless --yes is set.
#
# Flags:
#   --yes        Non-interactive (assume yes to the confirmation prompt).
#   --dry-run    Print what `clean` would do without doing it.
#   -h, --help   This message.
#
# Exit codes:
#   0  success (nothing to clean, OR clean ran cleanly)
#   1  user declined the confirmation prompt
#   2  bad arguments OR refused to clean (e.g. old workspace dir still
#      exists, suggesting the rename hasn't happened yet)
#
# Portability:
#   Bash (3.2+). Works via shebang on both macOS (`/bin/bash` is bash 3.2)
#   and Linux. Matches install.sh's shebang choice. Direct invocation via
#   `zsh script.sh` is NOT supported (zsh's case-statement glob semantics
#   differ from POSIX). Use `./script.sh` or `bash script.sh`. Avoids GNU
#   find extensions (-xtype, -lname) for the snippets the script prints
#   in its inventory — but those snippets aren't executed, just shown.

set -eu

INC_SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_TARGET="${HOME}/.claude/agents"
SKILLS_TARGET="${HOME}/.claude/skills"
BIN_TARGET="${HOME}/.local/bin"

# Anything pointing at one of these substrings is considered "ours":
OLD_WORKSPACE_PATTERN='*workspace/claude-agents*'
INC_WORKSPACE_PATTERN="*workspace/$(basename "$INC_SCRIPT_DIR")*"

CMD="inventory"
ASSUME_YES=0
DRY_RUN=0

usage() {
    cat <<'EOF'
cleanup-prior-install.sh — detect and remove leftovers from a prior
claude-agents (pre-rebrand) or partial inc install.

Usage: cleanup-prior-install.sh [SUBCMD] [FLAGS]

Subcommands:
  inventory   (default)  List what would be cleaned. Read-only. Exit 0.
  clean                  Move ~/.claude/agents/ to a timestamped backup
                         dir; delete inc-owned symlinks under
                         ~/.claude/skills/ and ~/.local/bin/ that are
                         broken or point at the old workspace path.
                         Prompts for confirmation unless --yes is set.

Flags:
  --yes        Non-interactive (assume yes to the confirmation prompt).
  --dry-run    Print what `clean` would do without doing it.
  -h, --help   This message.

Exit codes:
  0  success (nothing to clean, OR clean ran cleanly)
  1  user declined the confirmation prompt
  2  bad arguments OR refused to clean (old workspace dir still exists)

Portability: bash 3.2+. Works on macOS (/bin/bash) and Linux. Invoke via
`./script.sh` or `bash script.sh` — NOT `zsh script.sh` (zsh case-pattern
semantics differ from bash/POSIX).
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        inventory|clean) CMD="$1" ;;
        --yes|-y)        ASSUME_YES=1 ;;
        --dry-run)       DRY_RUN=1 ;;
        -h|--help)       usage; exit 0 ;;
        *) printf 'cleanup-prior-install.sh: unknown argument %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done

# ----- Detection helpers --------------------------------------------------

# Print broken symlinks (one path per line) under the given dir.
# Portable: [ -L "$l" ] && [ ! -e "$l" ].
broken_symlinks() {
    dir="$1"
    [ -d "$dir" ] || return 0
    # Quote the glob carefully so we don't expand "$dir"/*
    for l in "$dir"/*; do
        [ -e "$l" ] || [ -L "$l" ] || continue   # skip nonexistent glob non-matches
        if [ -L "$l" ] && [ ! -e "$l" ]; then
            printf '%s\n' "$l"
        fi
    done
}

# Print symlinks whose target matches *workspace/claude-agents*.
old_name_symlinks() {
    dir="$1"
    [ -d "$dir" ] || return 0
    for l in "$dir"/*; do
        [ -L "$l" ] || continue
        target="$(readlink "$l")"
        case "$target" in
            $OLD_WORKSPACE_PATTERN) printf '%s -> %s\n' "$l" "$target" ;;
        esac
    done
}

# Classify ~/.claude/agents/ contents:
#   - "clean"  — empty, OR all symlinks point into the current inc workspace
#                (i.e. the user re-ran install.sh and everything is good).
#   - "stale"  — contains copies (regular files/dirs that aren't symlinks),
#                OR symlinks pointing at the old workspace, OR symlinks
#                pointing somewhere outside the current inc workspace.
#                In any of these cases the whole tree is a candidate for
#                backup before re-installing.
# Echoes one of: "clean" "empty" "missing" "stale:<N>".
agents_dir_classify() {
    if [ ! -d "$AGENTS_TARGET" ]; then
        echo "missing"
        return 0
    fi
    count="$(ls -A "$AGENTS_TARGET" 2>/dev/null | wc -l | tr -d ' ')"
    if [ "$count" = "0" ]; then
        echo "empty"
        return 0
    fi
    # Walk the tree. install.sh --link creates category directories
    # (bonus/, engineering/, etc.) containing symlinks. So we have to
    # recurse: a category dir is "clean" iff every file inside is a
    # symlink into the current inc clone. A category dir is "stale" iff
    # any entry inside is a regular file (copy) or a symlink pointing
    # outside our inc clone.
    stale=0
    for entry in "$AGENTS_TARGET"/*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        if [ -L "$entry" ]; then
            target="$(readlink "$entry")"
            case "$target" in
                $INC_WORKSPACE_PATTERN) : ;;            # ours — clean
                *) stale=$((stale + 1)) ;;
            esac
        elif [ -d "$entry" ]; then
            # Recurse one level into the category dir.
            for sub in "$entry"/*; do
                [ -e "$sub" ] || [ -L "$sub" ] || continue
                if [ -L "$sub" ]; then
                    subtarget="$(readlink "$sub")"
                    case "$subtarget" in
                        $INC_WORKSPACE_PATTERN) : ;;    # ours — clean
                        *) stale=$((stale + 1)) ;;
                    esac
                else
                    # Regular file (copy) — pre-link install leftover.
                    stale=$((stale + 1))
                fi
            done
        else
            # A regular file at the root (e.g. copied README.md).
            stale=$((stale + 1))
        fi
    done
    if [ "$stale" -eq 0 ]; then
        echo "clean"
    else
        echo "stale:$stale"
    fi
}

agents_dir_status() {
    cls="$(agents_dir_classify)"
    case "$cls" in
        missing) echo "  $AGENTS_TARGET — does not exist (clean)" ;;
        empty)   echo "  $AGENTS_TARGET — exists but empty (clean)" ;;
        clean)
            count="$(ls -A "$AGENTS_TARGET" 2>/dev/null | wc -l | tr -d ' ')"
            echo "  $AGENTS_TARGET — $count entries, all current inc symlinks (clean)" ;;
        stale:*)
            n="${cls#stale:}"
            count="$(ls -A "$AGENTS_TARGET" 2>/dev/null | wc -l | tr -d ' ')"
            echo "  $AGENTS_TARGET — $count entries total, $n look stale (copies OR pointing outside this inc clone)."
            echo "  The whole tree will be moved to backup; install.sh re-links the rest on next run."
            ls -A "$AGENTS_TARGET" 2>/dev/null | sed 's/^/    - /' | head -10
            if [ "$count" -gt 10 ]; then
                echo "    ... ($((count - 10)) more)"
            fi ;;
    esac
}

# ----- Inventory output ---------------------------------------------------

print_inventory() {
    echo "=== cleanup-prior-install.sh: inventory ==="
    echo
    echo "Inc workspace (this clone): $INC_SCRIPT_DIR"
    echo "Old workspace path (pre-rebrand): \$HOME/workspace/claude-agents"
    if [ -d "$HOME/workspace/claude-agents" ]; then
        echo "  ^^ STILL EXISTS — the rename hasn't happened. Refusing to clean."
        echo "     'mv ~/workspace/claude-agents ~/workspace/inc' first."
    fi
    echo

    echo "Broken symlinks (any source):"
    found_broken=0
    for d in "$SKILLS_TARGET" "$AGENTS_TARGET" "$BIN_TARGET"; do
        for l in $(broken_symlinks "$d"); do
            printf '  %s -> %s\n' "$l" "$(readlink "$l" 2>/dev/null || echo '<unreadable>')"
            found_broken=$((found_broken + 1))
        done
    done
    [ "$found_broken" -eq 0 ] && echo "  (none)"
    echo

    echo "Symlinks pointing at OLD workspace path ($OLD_WORKSPACE_PATTERN):"
    found_old=0
    for d in "$SKILLS_TARGET" "$AGENTS_TARGET" "$BIN_TARGET"; do
        for line in $(old_name_symlinks "$d" 2>/dev/null | sed 's/ -> /|/'); do
            l="${line%%|*}"
            tgt="${line##*|}"
            printf '  %s -> %s\n' "$l" "$tgt"
            found_old=$((found_old + 1))
        done
    done
    [ "$found_old" -eq 0 ] && echo "  (none)"
    echo

    echo "Agents directory state:"
    agents_dir_status
    echo

    total_symlinks="$((found_broken + found_old))"
    cls="$(agents_dir_classify)"
    agents_needs_backup=0
    case "$cls" in stale:*) agents_needs_backup=1 ;; esac

    if [ "$total_symlinks" -eq 0 ] && [ "$agents_needs_backup" -eq 0 ]; then
        echo "Summary: nothing to clean."
        return 0
    fi
    summary="$total_symlinks stale symlinks"
    if [ "$agents_needs_backup" -eq 1 ]; then
        summary="$summary; agents/ dir would be moved to backup"
    fi
    echo "Summary: $summary."
    echo
    echo "Run 'cleanup-prior-install.sh clean' to apply (with --dry-run to preview, --yes for non-interactive)."
}

# ----- Cleanup ------------------------------------------------------------

do_clean() {
    # Refuse to clean if the old workspace dir still exists.
    if [ -d "$HOME/workspace/claude-agents" ]; then
        echo "cleanup-prior-install.sh: \$HOME/workspace/claude-agents still exists." >&2
        echo "  Run 'mv ~/workspace/claude-agents ~/workspace/inc' first; cleanup is only" >&2
        echo "  meant for AFTER the workspace rename." >&2
        exit 2
    fi

    prefix=""
    [ "$DRY_RUN" -eq 1 ] && prefix="[dry-run] "

    # 1) Backup agents/ only if it looks stale (contains copies or
    #    symlinks pointing outside this inc clone). A current/clean
    #    agents/ — all symlinks into ${INC_SCRIPT_DIR} — is left alone.
    cls="$(agents_dir_classify)"
    case "$cls" in
        stale:*)
            ts="$(date -u '+%Y%m%dT%H%M%SZ')"
            backup="${AGENTS_TARGET}.bak-pre-inc-${ts}"
            echo "${prefix}mv $AGENTS_TARGET → $backup"
            if [ "$DRY_RUN" -eq 0 ]; then
                mv "$AGENTS_TARGET" "$backup"
                mkdir -p "$AGENTS_TARGET"
            fi
            ;;
        clean|empty|missing)
            echo "${prefix}agents dir already clean — leaving in place"
            ;;
    esac

    # 2) Delete broken + old-name symlinks under skills/ and bin/.
    for d in "$SKILLS_TARGET" "$BIN_TARGET"; do
        [ -d "$d" ] || continue
        for l in "$d"/*; do
            [ -L "$l" ] || continue
            target="$(readlink "$l")"
            # Broken?
            if [ ! -e "$l" ]; then
                echo "${prefix}rm broken symlink: $l -> $target"
                [ "$DRY_RUN" -eq 0 ] && rm "$l"
                continue
            fi
            # Old name?
            case "$target" in
                $OLD_WORKSPACE_PATTERN)
                    echo "${prefix}rm old-name symlink: $l -> $target"
                    [ "$DRY_RUN" -eq 0 ] && rm "$l"
                    ;;
            esac
        done
    done

    echo "${prefix}Done."
}

# ----- Main ---------------------------------------------------------------

case "$CMD" in
    inventory)
        print_inventory
        ;;
    clean)
        # Show what we're about to do, then confirm unless --yes.
        print_inventory
        echo
        if [ "$ASSUME_YES" -ne 1 ]; then
            printf "Proceed with cleanup? [y/N] "
            read -r answer || answer=""
            case "$answer" in
                y|Y|yes|YES) : ;;
                *) echo "Aborted."; exit 1 ;;
            esac
        fi
        do_clean
        ;;
esac
