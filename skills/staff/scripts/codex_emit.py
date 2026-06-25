#!/usr/bin/env python3
"""codex_emit — generate Codex CLI subagent TOML from inc agent .md files.

`inc` is the single source of truth. Claude Code consumes the `.md` agents
directly; Codex CLII (0.142+) needs them as TOML subagent definitions:

    ~/.codex/agents/<name>.toml          (user / org scope)
    <project>/.codex/agents/<name>.toml  (project scope)

A Codex subagent file is flat TOML with three required keys — `name`,
`description`, `developer_instructions` — plus optional tuning. We map an inc
agent's markdown body into `developer_instructions` and its `model` tier into
`model_reasoning_effort`. See skills/staff/docs/codex.md for the full mapping.

This module is usable three ways:
  1. CLI:   `python3 codex_emit.py --user`         (org agents -> ~/.codex/agents)
            `python3 codex_emit.py --project PATH`  (staffed agents -> PATH/.codex/agents)
  2. via `staff codex ...` (the dispatcher forwards here)
  3. imported by apply.py / sync.py as a guarded post-step (emit_codex: true)

v1 scope: subagent TOML only. Skills are mirrored verbatim (same SKILL.md
spec) when --skills is passed. No companion routing skills yet — on Codex,
subagents are explicit-spawn (`description` is selection guidance, not an
auto-delegation trigger), which is the documented platform behaviour.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Reuse the strict frontmatter parser + durable writer from apply.py. apply.py
# guards its main() behind __main__, so importing it only runs module-level
# setup (already loaded when apply.py calls us back via the post-step hook).
import apply  # noqa: E402  (same scripts/ dir is on sys.path)

# inc model tier -> Codex reasoning effort. Codex inherits the user's configured
# model (gpt-5.x); opus/sonnet/haiku are not Codex model ids, so we drop `model`
# and translate the *intent* (how hard to think) instead.
_EFFORT_BY_MODEL = {"opus": "high", "sonnet": "medium", "haiku": "low"}

GENERATED_HEADER = (
    "# Generated from inc agent {id!r} by `staff codex` — do not edit.\n"
    "# Source of truth: the .md in the inc HR repo. Regenerate after changes.\n"
)


def _toml_basic(s: str) -> str:
    """A single-line TOML basic string (quotes, backslashes, newlines escaped)."""
    esc = (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{esc}"'


def _toml_multiline(s: str) -> str:
    """A multiline TOML basic string. Escaping every backslash and double-quote
    is correct (TOML decodes them back to the originals) and bulletproof against
    accidental triple-quote runs in markdown/code bodies."""
    esc = s.replace("\\", "\\\\").replace('"', '\\"')
    # The newline right after the opening delimiter is trimmed by TOML, so the
    # body is preserved exactly.
    return '"""\n' + esc + '"""'


def agent_md_to_toml(text: str) -> tuple[str, str]:
    """Convert one inc agent .md (frontmatter + body) -> (name, toml_string)."""
    _fm_block, body, fm = apply.split_agent_file(text)
    name = (fm.get("name") or "").strip()
    if not name:
        raise ValueError("agent frontmatter has no `name`")
    description = (fm.get("description") or "").strip()
    if not description:
        raise ValueError(f"agent {name!r} has empty `description`")
    instructions = body.strip()
    if not instructions:
        raise ValueError(f"agent {name!r} has empty body (developer_instructions)")

    lines = [GENERATED_HEADER.format(id=name)]
    lines.append(f"name = {_toml_basic(name)}")
    lines.append(f"description = {_toml_basic(description)}")
    effort = _EFFORT_BY_MODEL.get(str(fm.get("model", "")).strip().lower())
    if effort:
        lines.append(f"model_reasoning_effort = {_toml_basic(effort)}")
    lines.append(f"developer_instructions = {_toml_multiline(instructions)}")
    return name, "\n".join(lines) + "\n"


def emit_agent(md_path: Path, out_dir: Path) -> Path:
    """Read an inc agent .md, write <out_dir>/<name>.toml. Returns the path."""
    name, toml = agent_md_to_toml(md_path.read_text(encoding="utf-8"))
    out_path = out_dir / f"{name}.toml"
    apply.atomic_write(out_path, toml)
    return out_path


def emit_from_text(text: str, out_dir: Path) -> Path:
    """Emit from already-loaded merged .md text (used by the apply/sync hook)."""
    name, toml = agent_md_to_toml(text)
    out_path = out_dir / f"{name}.toml"
    apply.atomic_write(out_path, toml)
    return out_path


# --- skill mirroring (verbatim — Codex honours the same SKILL.md spec) --------

def mirror_skill(skill_dir: Path, dest_root: Path) -> Path:
    """Copy an inc skill dir to <dest_root>/<name>/ (full subtree)."""
    import shutil

    dest = dest_root / skill_dir.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill_dir, dest, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".git", "tests"))
    return dest


# --- batch emitters -----------------------------------------------------------

def _default_hr_repo() -> Path:
    """HR repo for `--user` (org) emits. The inc repo is the one this script
    lives in — `<inc>/skills/staff/scripts/codex_emit.py` — so default to that
    (the installed `staff` symlink resolves back here too). Fall back to project/
    env discovery only if the script isn't sitting in a recognisable HR repo."""
    root = Path(__file__).resolve().parents[3]
    if (root / "agent.manifest.yaml").is_file():
        return root
    return apply.resolve_hr_repo(Path.cwd(), None)


def _org_agent_files(hr_repo: Path) -> list[Path]:
    """Agent .md files marked `scope: org` (same set install.sh installs user-wide)."""
    out: list[Path] = []
    manifest = apply.load_manifest(hr_repo)
    for agent_id, entry in (manifest.get("agents") or manifest).items():
        if not isinstance(entry, dict) or "file" not in entry:
            continue
        src = hr_repo / entry["file"]
        if not src.is_file():
            continue
        try:
            _b, _body, fm = apply.split_agent_file(src.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if str(fm.get("scope", "")).strip().lower() == "org":
            out.append(src)
    return out


def _is_generated(toml_path: Path) -> bool:
    """True iff this .toml was emitted by us (carries the generated header).
    Guards pruning so we never delete a hand-written subagent."""
    try:
        with open(toml_path, "r", encoding="utf-8") as f:
            return f.readline().startswith("# Generated from inc agent")
    except OSError:
        return False


def _prune_stale(out_dir: Path, expected: set[str]) -> int:
    """Remove inc-generated *.toml in out_dir not in `expected` (unstaffed /
    renamed agents). Only touches files we generated — hand-made ones survive."""
    if not out_dir.is_dir():
        return 0
    removed = 0
    for f in sorted(out_dir.glob("*.toml")):
        if f.name not in expected and _is_generated(f):
            f.unlink()
            print(f"  prune  {f}")
            removed += 1
    return removed


def emit_user(hr_repo: Path, codex_home: Path, do_skills: bool) -> int:
    agents_dir = codex_home / "agents"
    expected: set[str] = set()
    count = 0
    for src in _org_agent_files(hr_repo):
        try:
            p = emit_agent(src, agents_dir)
            expected.add(p.name)
            count += 1
            print(f"  agent  {p}")
        except ValueError as exc:
            print(f"  skip   {src.name}: {exc}", file=sys.stderr)
    pruned = _prune_stale(agents_dir, expected)
    if do_skills:
        skills_root = codex_home / "skills"
        for skill_md in sorted((hr_repo / "skills").glob("*/SKILL.md")):
            dest = mirror_skill(skill_md.parent, skills_root)
            print(f"  skill  {dest}")
    print(f"emitted {count} org subagents ({pruned} pruned) -> {agents_dir}")
    return 0


def emit_project(project_root: Path, hr_repo: Path | None = None) -> int:
    """Emit each staffed agent into .codex/agents/ from the *already-applied*
    Claude artifact (.claude/agents/<id>.md), so the Codex projection is byte-
    faithful to what the project accepted — pinned commit + overlays — never HR
    HEAD. Then prune inc-generated TOML for agents no longer staffed.

    `hr_repo` is accepted for call-site compatibility but unused: the source of
    truth here is the project's own generated Claude agents, not HR."""
    lock_path = project_root / apply.REPO_DEFAULTS["lock_path"]
    if not lock_path.exists():
        print(f"no staff lockfile at {lock_path} — run `staff apply` first", file=sys.stderr)
        return 2
    staffed = apply.load_lockfile(lock_path).get("staffed") or {}
    agents_dir = project_root / apply.REPO_DEFAULTS["agents_dir"]
    out_dir = project_root / ".codex" / "agents"
    expected: set[str] = set()
    count = 0
    for agent_id in sorted(staffed):
        md = agents_dir / f"{agent_id}.md"
        if not md.is_file():
            print(f"  skip   {agent_id}: not applied ({md} missing)", file=sys.stderr)
            continue
        try:
            p = emit_agent(md, out_dir)
            expected.add(p.name)
            count += 1
            print(f"  agent  {p}")
        except ValueError as exc:
            print(f"  skip   {agent_id}: {exc}", file=sys.stderr)
    pruned = _prune_stale(out_dir, expected)
    print(f"emitted {count} subagents ({pruned} pruned) -> {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="staff codex",
        description="Generate Codex CLI subagent TOML from inc agents (v1: subagents only).",
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--user", action="store_true",
                   help="emit `scope: org` agents into $CODEX_HOME/agents (default ~/.codex)")
    g.add_argument("--project", metavar="PATH",
                   help="emit the project's staffed agents into PATH/.codex/agents")
    ap.add_argument("--hr-repo", metavar="PATH", help="inc HR repo (else config/env)")
    ap.add_argument("--skills", action="store_true",
                    help="also mirror inc skills into $CODEX_HOME/skills (with --user)")
    ap.add_argument("--codex-home", metavar="PATH",
                    help="override $CODEX_HOME (default ~/.codex)")
    args = ap.parse_args(argv)

    codex_home = Path(args.codex_home or os.environ.get("CODEX_HOME") or
                      Path.home() / ".codex").expanduser()
    hr_override = Path(args.hr_repo).expanduser().resolve() if args.hr_repo else None

    if args.user:
        return emit_user(hr_override or _default_hr_repo(), codex_home, args.skills)
    project_root = Path(args.project).expanduser().resolve()
    return emit_project(project_root, hr_override)


if __name__ == "__main__":
    sys.exit(main())
