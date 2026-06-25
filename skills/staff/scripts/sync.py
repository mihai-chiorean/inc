#!/usr/bin/env python3
"""staff sync — refresh staffed agents against HR HEAD.

For each staffed agent, compares the lockfile pin to current HR HEAD. When
content has changed (HR-DRIFT) or the agent has been renamed (ALIAS-RENAMED)
or removed from HR (MISSING), surfaces the change to the user, accepts a
per-agent decision, and re-applies on accept.

NOT a three-way merge. Sync = diff + overwrite of the HR base content;
overlays (.claude/staff/overlays/<id>.md) are preserved unconditionally.
Manual edits to the merged file under .claude/agents/<id>.md are detected
(MANUAL-EDIT) and require explicit confirmation before being overwritten.

Usage:
  staff sync                      # interactive per-agent prompts (default)
  staff sync --yes                # accept everything, no prompts
  staff sync --agents <ids...>    # only sync these IDs
  staff sync --dry-run            # show what would change, write nothing

Exit codes:
  0   nothing to sync, or all syncs accepted and applied cleanly
  1   user declined one or more changes (informational; not an error)
  2   error (missing lockfile, malformed manifest, dirty HR, etc.)
  5   one or more agents failed to apply during sync
"""

from __future__ import annotations

import argparse
import difflib
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Reuse apply.py's primitives — sync is a special-case re-apply
sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply as apply_mod  # type: ignore  # noqa: E402


# ---------- per-agent change classification ----------


@dataclass
class AgentChange:
    """One agent's status vs HR HEAD."""
    lockfile_id: str  # the id as stored in the lockfile (may be an old alias)
    canonical_id: str | None  # the current canonical id, or None if MISSING
    flags: list[str]  # subset of: NO-CHANGE, HR-DRIFT, ALIAS-RENAMED, MISSING, MANUAL-EDIT, OVERLAY-PRESERVED
    detail: list[str]  # per-flag detail lines for the user
    pinned_body_hash: str
    head_body_hash: str | None  # None if MISSING
    pinned_desc_hash: str
    head_desc_hash: str | None  # None if MISSING


def classify_agent(
    lockfile_id: str,
    lock_entry: dict,
    manifest: dict,
    project_root: Path,
    agents_dir: Path,
    overlays_dir: Path,
) -> AgentChange:
    """Determine what (if anything) needs to change for one staffed agent."""
    pinned_body_hash = lock_entry.get("body_hash_at_pin", "")
    pinned_desc_hash = lock_entry.get("description_hash_at_pin", "")

    # Step 1: resolve canonical id
    agents = manifest.get("agents", {})
    canonical_id: str | None = None
    flags: list[str] = []
    detail: list[str] = []
    if lockfile_id in agents:
        canonical_id = lockfile_id
    else:
        for cid, e in agents.items():
            if lockfile_id in (e.get("aliases") or []):
                canonical_id = cid
                flags.append("ALIAS-RENAMED")
                detail.append(f"lockfile id {lockfile_id!r} is now an alias of {cid!r}")
                break

    if canonical_id is None:
        flags.append("MISSING")
        detail.append(f"agent {lockfile_id!r} no longer exists in HR (and no alias matches)")
        return AgentChange(
            lockfile_id=lockfile_id,
            canonical_id=None,
            flags=flags,
            detail=detail,
            pinned_body_hash=pinned_body_hash,
            head_body_hash=None,
            pinned_desc_hash=pinned_desc_hash,
            head_desc_hash=None,
        )

    head = agents[canonical_id]
    head_body_hash = head.get("body_hash", "")
    head_desc_hash = head.get("description_hash", "")

    # Step 2: HR-DRIFT
    if head_body_hash != pinned_body_hash:
        flags.append("HR-DRIFT")
        detail.append(
            f"body_hash changed: {short(pinned_body_hash)} → {short(head_body_hash)}"
        )
    if head_desc_hash != pinned_desc_hash:
        flags.append("HR-DRIFT")
        detail.append(
            f"description_hash changed: {short(pinned_desc_hash)} → {short(head_desc_hash)}"
        )

    # Step 3: MANUAL-EDIT on the merged file
    generated_path = agents_dir / f"{lockfile_id}.md"
    if generated_path.is_file():
        actual_hash = apply_mod.sha256(generated_path.read_text(encoding="utf-8"))
        expected = lock_entry.get("generated_hash_at_apply")
        if expected and actual_hash != expected:
            flags.append("MANUAL-EDIT")
            detail.append(
                f"generated file {generated_path.relative_to(project_root)} was hand-edited "
                f"(sync will overwrite unless declined)"
            )

    # Step 4: overlay note (informational, not a flag itself)
    overlay_path = overlays_dir / f"{canonical_id}.md"
    if overlay_path.is_file() or (overlays_dir / f"{lockfile_id}.md").is_file():
        # Note: when ALIAS-RENAMED, overlay file may live under the OLD id —
        # sync handles migration in apply_change()
        flags.append("OVERLAY-PRESERVED")

    if not any(f in flags for f in ("HR-DRIFT", "MANUAL-EDIT", "ALIAS-RENAMED", "MISSING")):
        flags.insert(0, "NO-CHANGE")

    return AgentChange(
        lockfile_id=lockfile_id,
        canonical_id=canonical_id,
        flags=flags,
        detail=detail,
        pinned_body_hash=pinned_body_hash,
        head_body_hash=head_body_hash,
        pinned_desc_hash=pinned_desc_hash,
        head_desc_hash=head_desc_hash,
    )


def short(h: str) -> str:
    if not h:
        return "<missing>"
    if h.startswith("sha256:"):
        return h[7:19]
    return h[:12]


# ---------- diff rendering ----------


def show_diff_for_agent(change: AgentChange, lock_entry: dict,
                        hr_repo: Path, manifest: dict, dest: object = sys.stdout) -> None:
    """Print a unified diff for the agent's HR base content (pinned vs HEAD).

    Uses `git show <pinned_at>:<file>` to retrieve the historical content."""
    print(f"\n=== {change.lockfile_id}", file=dest)
    if change.canonical_id and change.canonical_id != change.lockfile_id:
        print(f"    (now: {change.canonical_id})", file=dest)
    print(f"    flags: {', '.join(change.flags)}", file=dest)
    for d in change.detail:
        print(f"    · {d}", file=dest)

    # Skip diff for MISSING (no HEAD content to diff against)
    if "MISSING" in change.flags:
        return

    if "HR-DRIFT" not in change.flags and "ALIAS-RENAMED" not in change.flags:
        # No content change to show; just the alias rename
        return

    canonical = change.canonical_id
    if canonical is None:
        return
    head_entry = manifest["agents"][canonical]
    pinned_at = lock_entry.get("pinned_at", "")
    pinned_file = lock_entry.get("file", "")
    head_file = head_entry.get("file", "")

    # Read pinned content from git, head content from disk
    pinned_text = git_show_at(hr_repo, pinned_at, pinned_file) if pinned_at and pinned_file else ""
    head_path = hr_repo / head_file if head_file else None
    head_text = head_path.read_text(encoding="utf-8") if head_path and head_path.is_file() else ""

    if not pinned_text and not head_text:
        return

    diff = list(difflib.unified_diff(
        pinned_text.splitlines(keepends=True),
        head_text.splitlines(keepends=True),
        fromfile=f"a/{pinned_file} (pinned at {short(pinned_at)})",
        tofile=f"b/{head_file} (HR HEAD)",
        n=3,
    ))
    if not diff:
        return
    for line in diff:
        print("    " + line.rstrip("\n"), file=dest)


def git_show_at(hr_repo: Path, commit: str, file_path: str) -> str:
    """Best-effort `git show <commit>:<file>` against HR. Returns '' on failure."""
    try:
        out = subprocess.check_output(
            ["git", "show", f"{commit}:{file_path}"],
            cwd=hr_repo,
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8", errors="replace")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


# ---------- decision interface ----------


def prompt_for_change(change: AgentChange, *, default_yes: bool, assume_yes: bool) -> str:
    """Returns 'accept', 'skip', or 'remove'.

    For HR-DRIFT / ALIAS-RENAMED: accept means re-apply; skip means leave pinned.
    For MISSING: accept means remove from lockfile; skip means leave (will keep
                 surfacing as MISSING in /staff status next time).
    """
    if assume_yes:
        return "remove" if "MISSING" in change.flags else "accept"

    if "MANUAL-EDIT" in change.flags:
        prompt = "Overwrite the hand-edited file with HR HEAD content? [y/N]: "
        default = "skip"
    elif "MISSING" in change.flags:
        # Default to skip: a "missing" agent could also mean a typo'd alias,
        # a wrong HR repo, or a commit that lost the file. Removal is destructive
        # (drops the lockfile entry + deletes the generated file). Make the
        # operator type 'y' to remove. --yes overrides for CI use cases.
        prompt = f"Remove {change.lockfile_id!r} from the lockfile? [y/N]: "
        default = "skip"
    elif "NO-CHANGE" in change.flags:
        return "skip"
    else:
        prompt = "Apply HR HEAD content? [Y/n]: "
        default = "accept" if default_yes else "skip"

    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        # No interactive consent available (stdin closed). Treat as a
        # decline rather than the prompt's default — a user who runs
        # `staff sync < /dev/null` should NOT mutate files without
        # explicit `--yes`.
        return "skip"

    if not answer:
        return default
    if answer in ("y", "yes"):
        return "remove" if "MISSING" in change.flags else "accept"
    return "skip"


# ---------- two-phase apply ----------


@dataclass
class PlannedChange:
    """A fully-computed change that's ready to write but hasn't yet.

    Atomicity: all PlannedChange instances for accepted changes are built in
    phase 1 (no I/O writes; only reads). If any phase-1 build fails, the
    sync aborts before any file is touched. Phase 2 walks the planned
    changes and performs the writes; the lockfile is written last."""

    change: AgentChange
    canonical_id: str
    new_lock_entry: dict | None  # None means "remove this agent"

    # Generated agent file
    generated_path: Path  # write target for the merged file
    generated_content: str

    # Old paths to clean up after the new write succeeds
    old_generated_path: Path | None = None  # set on alias rename to remove the old file

    # Overlay migration (alias rename + overlay present)
    overlay_rewrite_path: Path | None = None  # the new path
    overlay_rewrite_content: str | None = None
    overlay_remove_path: Path | None = None  # the old path

    # Lockfile re-key (alias rename)
    drop_lockfile_id: str | None = None  # the old key to remove from staffed
    add_lockfile_id: str | None = None  # the new key to add (canonical)

    # Pure removal (MISSING accepted)
    remove_lockfile_id: str | None = None
    remove_generated_path: Path | None = None


def _rewrite_overlay_agent_id(overlay_text: str, new_id: str) -> str:
    """Rewrite the `agent_id:` frontmatter line to point at new_id.
    Preserves the rest of the overlay content verbatim."""
    fm, body = apply_mod.parse_overlay(overlay_text)
    fm["agent_id"] = new_id
    new_fm = yaml.safe_dump(fm, sort_keys=False).strip()
    return f"---\n{new_fm}\n---\n{body}"


def plan_change(change: AgentChange, lock_entry: dict, paths: apply_mod.Paths,
                manifest: dict, hr_commit: str) -> PlannedChange:
    """Build a PlannedChange WITHOUT doing any I/O writes. Reads HR + project
    state, validates the migration is safe, returns the plan. Raises ValueError
    if the change can't be planned safely (caller should abort)."""
    # MISSING accepted -> pure removal
    if "MISSING" in change.flags:
        return PlannedChange(
            change=change,
            canonical_id="",  # unused for removal
            new_lock_entry=None,
            generated_path=paths.agents_dir / f"{change.lockfile_id}.md",
            generated_content="",  # unused
            remove_lockfile_id=change.lockfile_id,
            remove_generated_path=paths.agents_dir / f"{change.lockfile_id}.md",
        )

    canonical = change.canonical_id
    if canonical is None:
        raise ValueError(f"{change.lockfile_id}: cannot plan; canonical_id is None")
    manifest_entry = manifest["agents"][canonical]

    is_rename = change.lockfile_id != canonical
    overlay_rewrite_path: Path | None = None
    overlay_rewrite_content: str | None = None
    overlay_remove_path: Path | None = None

    if is_rename:
        old_overlay = paths.overlays_dir / f"{change.lockfile_id}.md"
        new_overlay = paths.overlays_dir / f"{canonical}.md"
        if old_overlay.exists():
            if new_overlay.exists():
                # Silent skip would lose content. Fail loudly.
                raise ValueError(
                    f"{change.lockfile_id}: overlay collision — both "
                    f"{old_overlay.relative_to(paths.project_root)} and "
                    f"{new_overlay.relative_to(paths.project_root)} exist. "
                    f"Resolve by hand (merge or pick one) before re-running sync."
                )
            # Rewrite the overlay's frontmatter agent_id to the new canonical
            try:
                rewritten = _rewrite_overlay_agent_id(
                    old_overlay.read_text(encoding="utf-8"), canonical,
                )
            except (ValueError, yaml.YAMLError) as exc:
                raise ValueError(
                    f"{change.lockfile_id}: overlay {old_overlay} could not be rewritten: {exc}"
                ) from exc
            overlay_rewrite_path = new_overlay
            overlay_rewrite_content = rewritten
            overlay_remove_path = old_overlay

        # Refuse to clobber a generated file at the new canonical id that's
        # NOT owned by an active lockfile entry — could be an orphan or
        # manual file. Owned-by-this-rename case is fine: when we sync
        # alias→canonical and the canonical lockfile entry doesn't exist,
        # any file at .claude/agents/<canonical>.md is unexpected and
        # should be reviewed by the human.
        new_generated = paths.agents_dir / f"{canonical}.md"
        if new_generated.exists():
            raise ValueError(
                f"{change.lockfile_id}: generated-file collision — "
                f"{new_generated.relative_to(paths.project_root)} already exists "
                f"(orphan or hand-written). Inspect and remove (or `staff add {canonical}` "
                f"if it was already staffed elsewhere) before re-running sync."
            )

    # Stage the rewritten overlay BEFORE compute_agent reads it, AND record
    # the staged path on the PlannedChange before any other code can fail.
    # The aggregate rollback at main() iterates over plans and removes
    # staged overlays — without this assignment, rollback can't see them.
    plan = PlannedChange(
        change=change,
        canonical_id=canonical,
        new_lock_entry=None,  # filled in below
        generated_path=paths.agents_dir / f"{canonical}.md",  # filled in below
        generated_content="",  # filled in below
    )
    if overlay_rewrite_path is not None:
        plan.overlay_rewrite_path = overlay_rewrite_path

    staged = False
    try:
        if overlay_rewrite_path is not None and overlay_rewrite_content is not None:
            apply_mod.atomic_write(overlay_rewrite_path, overlay_rewrite_content)
            staged = True

        out_path, merged, new_entry = apply_mod.compute_agent(
            paths, canonical, hr_commit, manifest_entry,
        )
    except Exception:
        if staged and overlay_rewrite_path is not None and overlay_rewrite_path.exists():
            overlay_rewrite_path.unlink()
        raise

    plan.new_lock_entry = new_entry
    plan.generated_path = out_path
    plan.generated_content = merged

    if is_rename:
        plan.old_generated_path = paths.agents_dir / f"{change.lockfile_id}.md"
        plan.drop_lockfile_id = change.lockfile_id
        plan.add_lockfile_id = canonical
    if overlay_remove_path is not None:
        plan.overlay_remove_path = overlay_remove_path
    return plan


def execute_plan(plan: PlannedChange, paths: apply_mod.Paths,
                 staffed: dict[str, dict]) -> None:
    """Apply a single PlannedChange to disk + the in-memory staffed map.
    The lockfile is NOT written here (caller writes it once after all plans
    execute). Mutates `staffed`."""
    if plan.remove_lockfile_id is not None:
        # Pure removal
        staffed.pop(plan.remove_lockfile_id, None)
        if plan.remove_generated_path and plan.remove_generated_path.exists():
            plan.remove_generated_path.unlink()
        return

    # Write the new generated file (compute_agent already wrote it during plan
    # via atomic_write, but compute writes via apply.atomic_write too).
    # Re-write to be defensive — atomic_write is idempotent.
    apply_mod.atomic_write(plan.generated_path, plan.generated_content)

    # Clean up old generated file on rename
    if plan.old_generated_path is not None and plan.old_generated_path != plan.generated_path:
        if plan.old_generated_path.exists():
            plan.old_generated_path.unlink()

    # Remove the old overlay path (the new one was already written during plan)
    if plan.overlay_remove_path is not None and plan.overlay_remove_path.exists():
        plan.overlay_remove_path.unlink()

    # Lockfile re-key
    if plan.drop_lockfile_id is not None and plan.add_lockfile_id is not None:
        # Refuse to silently overwrite an existing canonical entry. If both
        # the alias key and the canonical key are in staffed, the lockfile
        # is in an invalid state — surface it instead of clobbering.
        if (plan.add_lockfile_id in staffed
                and plan.add_lockfile_id != plan.drop_lockfile_id):
            raise ValueError(
                f"lockfile re-key collision: both alias {plan.drop_lockfile_id!r} "
                f"and canonical {plan.add_lockfile_id!r} are in staffed[]. "
                f"Hand-edit the lockfile to resolve before re-running sync."
            )
        staffed.pop(plan.drop_lockfile_id, None)
        staffed[plan.add_lockfile_id] = plan.new_lock_entry  # type: ignore[assignment]
    else:
        staffed[plan.change.lockfile_id] = plan.new_lock_entry  # type: ignore[assignment]


# ---------- main ----------


def main() -> int:
    parser = argparse.ArgumentParser(description="refresh staffed agents against HR HEAD")
    parser.add_argument("--project-root", default=".", help="project root (default: cwd)")
    parser.add_argument("--hr-repo", help="HR repo (else config or env or lockfile)")
    parser.add_argument("--agents", nargs="+", default=None,
                        help="only sync these agent ids (subset of staffed)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="accept all changes without prompting")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change; write nothing")
    parser.add_argument("--allow-dirty-hr", action="store_true",
                        help="proceed even if HR has uncommitted changes")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"not a directory: {project_root}", file=sys.stderr)
        return 2

    lock_path = project_root / ".claude/staff/lock.yaml"
    if not lock_path.exists():
        print(f"error: no lockfile at {lock_path}; run /staff apply first", file=sys.stderr)
        return 2

    try:
        existing_lock = apply_mod.load_lockfile(lock_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Resolve HR with the same priority chain as add: --hr-repo > config > lockfile > env
    cfg = {}
    try:
        cfg = apply_mod.load_project_config(project_root)
    except ValueError as exc:
        if not args.hr_repo:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    try:
        if args.hr_repo:
            hr_repo = apply_mod.parse_hr_repo_path(args.hr_repo)
        elif cfg.get("hr_repo"):
            hr_repo = apply_mod.parse_hr_repo_path(str(cfg["hr_repo"]))
        elif existing_lock.get("hr_repo"):
            hr_repo = apply_mod.parse_hr_repo_path(existing_lock["hr_repo"])
        elif os.environ.get("STAFF_HR_REPO"):
            hr_repo = apply_mod.parse_hr_repo_path(os.environ["STAFF_HR_REPO"])
        else:
            raise ValueError(
                "HR repo not specified — pass --hr-repo, set STAFF_HR_REPO, "
                "or ensure config.yaml or lock.yaml has hr_repo:"
            )
        if not (hr_repo / "agent.manifest.yaml").is_file():
            raise ValueError(f"not an HR repo (missing agent.manifest.yaml): {hr_repo}")
        manifest = apply_mod.load_manifest(hr_repo)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Refuse dirty HR (sync writes new pins; pinning a dirty tree would confuse
    # future status checks)
    if not apply_mod.hr_is_clean(hr_repo) and not args.allow_dirty_hr:
        print(
            f"error: HR repo at {hr_repo} has uncommitted changes\n"
            f"Commit or stash them, or pass --allow-dirty-hr.",
            file=sys.stderr,
        )
        return 2

    paths = apply_mod.Paths.from_project(project_root, hr_repo)
    try:
        hr_commit = apply_mod.hr_head_sha(hr_repo)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Classify every staffed agent (or the requested subset)
    staffed = dict(existing_lock.get("staffed") or {})
    target_ids = args.agents if args.agents else list(staffed.keys())

    if args.agents:
        unknown = [t for t in args.agents if t not in staffed]
        if unknown:
            # Any unknown id fails loudly. A targeted sync with mixed typos
            # is more dangerous than helpful (operator typed `alpha aplha` and
            # got a partial sync of `alpha` only). Force the user to fix the
            # invocation.
            print(
                f"error: requested agents not in lockfile: {', '.join(unknown)}\n"
                f"hint: run `staff status` to see what's actually staffed; "
                f"`staff sync` (no --agents) covers everything.",
                file=sys.stderr,
            )
            return 2

    changes: list[tuple[AgentChange, dict]] = []  # (change, lock_entry)
    for lock_id in target_ids:
        if lock_id not in staffed:
            continue
        change = classify_agent(
            lock_id, staffed[lock_id], manifest, project_root,
            paths.agents_dir, paths.overlays_dir,
        )
        changes.append((change, staffed[lock_id]))

    actionable = [(c, e) for c, e in changes
                  if "NO-CHANGE" not in c.flags or "ALIAS-RENAMED" in c.flags]
    if not actionable:
        print(f"all {len(changes)} staffed agent(s) are up to date with HR HEAD ({short(hr_commit)})")
        # Still refresh Codex artifacts for opted-in projects: a no-op sync must
        # honour `emit_codex` (e.g. just enabled, or .codex/agents was deleted).
        # But never under --dry-run — that contract is "nothing written".
        if not args.dry_run:
            apply_mod._maybe_emit_codex(project_root, hr_repo)
        return 0

    print(f"{len(actionable)} agent(s) have changes vs HR HEAD ({short(hr_commit)}):\n")

    # In dry-run mode, render diffs + the planned default action without
    # asking for input. This unblocks scripted use ("what would sync do?")
    # without requiring a TTY.
    if args.dry_run:
        for change, lock_entry in actionable:
            show_diff_for_agent(change, lock_entry, hr_repo, manifest)
            default = "accept"
            if "MANUAL-EDIT" in change.flags or "MISSING" in change.flags:
                default = "skip" if not args.yes else ("remove" if "MISSING" in change.flags else "accept")
            print(f"    [dry-run default: {default}]")
        print(f"\ndry-run: {len(actionable)} change(s) would be evaluated; nothing written")
        return 0

    # Walk each change with the prompt
    accepted: list[tuple[AgentChange, dict]] = []
    declined = 0
    for change, lock_entry in actionable:
        show_diff_for_agent(change, lock_entry, hr_repo, manifest)
        decision = prompt_for_change(change, default_yes=True, assume_yes=args.yes)
        if decision in ("accept", "remove"):
            accepted.append((change, lock_entry))
        else:
            declined += 1

    if not accepted:
        print(f"\nNothing accepted ({declined} declined). Lockfile unchanged.")
        return 1 if declined else 0

    # Phase 1: plan all changes. If any plan fails, abort BEFORE writing.
    plans: list[PlannedChange] = []
    plan_failures: list[str] = []
    for change, lock_entry in accepted:
        try:
            plans.append(plan_change(change, lock_entry, paths, manifest, hr_commit))
        except (ValueError, OSError) as exc:
            plan_failures.append(f"{change.lockfile_id}: {exc}")

    if plan_failures:
        for f in plan_failures:
            print(f"error: {f}", file=sys.stderr)
        print(
            f"\n{len(plan_failures)} agent(s) failed to plan. "
            f"No files were modified; lockfile unchanged.",
            file=sys.stderr,
        )
        # Roll back any overlays that plan_change pre-staged. plan_change writes
        # rewritten overlays at the new path during planning so compute_agent
        # can read them; if a later plan fails, we need to undo those writes.
        # The plans list contains successfully-planned ones; the failed ones
        # already rolled back in plan_change's except branch.
        for plan in plans:
            if plan.overlay_rewrite_path is not None and plan.overlay_remove_path is not None:
                # The new overlay was staged but the old one is still there.
                # Restoring requires removing the staged new overlay (it'll be
                # re-staged on next sync attempt).
                if plan.overlay_rewrite_path.exists():
                    plan.overlay_rewrite_path.unlink()
        return 5

    # Phase 2: execute. The lockfile is the LAST thing written, so a partial
    # phase-2 failure leaves files plus an unchanged lockfile (status will
    # report this as ORPHAN-FILE / drift, which is detectable + recoverable).
    new_staffed = dict(staffed)
    exec_failures: list[str] = []
    for plan in plans:
        try:
            execute_plan(plan, paths, new_staffed)
        except (ValueError, OSError) as exc:
            exec_failures.append(f"{plan.change.lockfile_id}: {exc}")

    if exec_failures:
        for f in exec_failures:
            print(f"error: {f}", file=sys.stderr)
        print(
            f"\n{len(exec_failures)} agent(s) failed during write phase. "
            f"Some files may have been advanced; lockfile NOT written. "
            f"Run `staff status` to inspect; orphans are surfaced as ORPHAN-FILE.",
            file=sys.stderr,
        )
        return 5

    # Lockfile last. If THIS write fails, the OS-level failure leaves staged
    # files but unchanged lockfile state — still recoverable via status.
    apply_mod.write_lockfile(paths, hr_commit, new_staffed)

    print(f"\nsynced {len(accepted)} agent(s) to HR {short(hr_commit)} → {paths.agents_dir}")
    print(f"lock: {paths.lock_path}")
    apply_mod._maybe_emit_codex(project_root, hr_repo)
    if declined:
        print(f"({declined} declined; rerun /staff sync to revisit)")
    return 1 if declined else 0


if __name__ == "__main__":
    sys.exit(main())
