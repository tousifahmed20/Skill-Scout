#!/usr/bin/env python3
"""Validate the workspace's routes and ownership. Stdlib only.

Checks
  1. Each stage has CONTEXT.md with Inputs, Process, Outputs, and Done when sections.
  2. Each Inputs path exists, or is a declared output of the same or an earlier stage.
  3. Each Inputs section (#anchor) exists as a heading in that file (when the file exists).
  4. Reads go one way: an input's owner stage is <= the reading stage. docs/ is never an input.
  5. Every output path has exactly one owner; no stage owns a path inside another stage's path.
  6. The root CONTEXT.md "Read set" column matches the stages each Inputs table really uses.
  7. No @path imports in CLAUDE.md or any CONTEXT.md.
  8. SKILL.md: name matches its folder; description <= 1024 chars; routed files exist or are planned.
  9. Every existing file under skills/ has an owner stage.

Usage: python tools/check_routes.py   (exit code 1 on any error)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES = ROOT / "stages"
SKILL_DIR = ROOT / "skills" / "skill-scout"
errors, warnings = [], []


def slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return re.sub(r"\s", "-", s)


def headings(path: Path) -> set:
    out, fence = set(), False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            m = re.match(r"^#{1,6}\s+(.*)$", line)
            if m:
                out.add(slug(m.group(1)))
    return out


def section_lines(text: str, name: str) -> list:
    lines, inside = [], False
    for line in text.splitlines():
        if re.match(r"^##\s+", line):
            inside = slug(line[3:]) == slug(name)
            continue
        if inside:
            lines.append(line)
    return lines


def table_rows(lines: list) -> list:
    rows = []
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows[1:] if rows else []  # drop header row


def backticked(cell: str) -> list:
    return re.findall(r"`([^`]+)`", cell)


def stage_num(name: str) -> int:
    return int(name.split("_", 1)[0])


# ---- 1. load stages -------------------------------------------------------
stages = {}
for d in sorted(p for p in STAGES.iterdir() if p.is_dir() and re.match(r"^\d\d_", p.name)):
    ctx = d / "CONTEXT.md"
    if not ctx.exists():
        errors.append(f"{d.name}: missing CONTEXT.md")
        continue
    text = ctx.read_text(encoding="utf-8")
    for sec in ("Inputs", "Process", "Outputs", "Done when"):
        if not section_lines(text, sec):
            errors.append(f"{d.name}: missing section '## {sec}'")
    inputs = []
    for cells in table_rows(section_lines(text, "Inputs")):
        paths = backticked(cells[0]) if cells else []
        anchors = backticked(cells[1]) if len(cells) > 1 else []
        for p in paths:
            inputs.append((p, [a.lstrip("#") for a in anchors if a.startswith("#")]))
    outputs = []
    for cells in table_rows(section_lines(text, "Outputs")):
        outputs += backticked(cells[0]) if cells else []
    stages[stage_num(d.name)] = {"name": d.name, "dir": d, "inputs": inputs, "outputs": outputs}

# ---- 5. ownership map -----------------------------------------------------
owner = {}
for n, s in stages.items():
    for o in s["outputs"]:
        if o in owner and owner[o] != n:
            errors.append(f"{o}: owned by both stage {owner[o]:02d} and stage {n:02d}")
        owner[o] = n
for a, na in owner.items():
    for b, nb in owner.items():
        if a != b and na != nb and a.endswith("/") and b.startswith(a):
            errors.append(f"{b} (stage {nb:02d}) is inside {a} (stage {na:02d})")


def owner_of(path: str):
    m = re.match(r"^stages/(\d\d)_", path)
    if m:
        return int(m.group(1))
    best = None
    for o, n in owner.items():
        if path == o or (o.endswith("/") and path.startswith(o)):
            if best is None or len(o) > len(best[0]):
                best = (o, n)
    return best[1] if best else None


# ---- 2-4. inputs ----------------------------------------------------------
used = {}
for n, s in stages.items():
    used[n] = set()
    for path, anchors in s["inputs"]:
        if path.startswith("docs/"):
            errors.append(f"{s['name']}: docs/ must never be an input ({path})")
            continue
        own = owner_of(path)
        if own is None:
            errors.append(f"{s['name']}: input {path} has no owner stage")
            continue
        if own > n:
            errors.append(f"{s['name']}: reads {path} owned by later stage {own:02d}")
        if own != n:
            used[n].add(own)
        f = ROOT / path
        if f.exists():
            if anchors:
                hs = headings(f)
                for a in anchors:
                    if a not in hs:
                        errors.append(f"{s['name']}: {path} has no section '#{a}'")
        else:
            warnings.append(f"{s['name']}: {path} is planned (created by stage {own:02d})")

# ---- 6. root routing table ------------------------------------------------
root_ctx = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
seen = set()
for line in root_ctx.splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if not line.startswith("|") or not cells or not re.fullmatch(r"\d\d", cells[0]):
        continue
    n = int(cells[0])
    seen.add(n)
    declared = cells[-1]
    want = set() if declared == "single" else {int(x) for x in re.findall(r"\d\d", declared)}
    have = used.get(n, set())
    if want != have:
        fmt = lambda xs: ", ".join(f"{x:02d}" for x in sorted(xs)) or "single"
        errors.append(f"CONTEXT.md row {n:02d}: says '{fmt(want)}' but Inputs use '{fmt(have)}'")
for n in stages:
    if n not in seen:
        errors.append(f"CONTEXT.md: no routing row for stage {n:02d}")

# ---- 7. no @imports -------------------------------------------------------
for f in [ROOT / "CLAUDE.md", ROOT / "CONTEXT.md", *STAGES.glob("*/CONTEXT.md")]:
    fence = False
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith("```"):
            fence = not fence
            continue
        bare = re.sub(r"`[^`]*`", "", line)
        if not fence and re.search(r"(^|\s)@[\w./~-]+", bare):
            errors.append(f"{f.relative_to(ROOT)}:{i}: @import found — write the path in backticks")

# ---- 8. SKILL.md ----------------------------------------------------------
skill_md = SKILL_DIR / "SKILL.md"
if skill_md.exists():
    text = skill_md.read_text(encoding="utf-8")
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not fm:
        errors.append("SKILL.md: missing frontmatter")
    else:
        name = re.search(r"^name:\s*(.+)$", fm.group(1), re.M)
        desc = re.search(r"^description:\s*(.+)$", fm.group(1), re.M)
        if not name or name.group(1).strip() != SKILL_DIR.name:
            errors.append("SKILL.md: name must match folder name")
        if not desc or len(desc.group(1).strip()) > 1024:
            errors.append("SKILL.md: description missing or > 1024 characters")
        allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
        keys = set(re.findall(r"^([A-Za-z_-]+):", fm.group(1), re.M))
        extra = keys - allowed
        if extra:
            errors.append(f"SKILL.md: non-spec frontmatter keys {sorted(extra)} (skill must stay portable)")
    for rel in sorted(set(re.findall(r"`((?:steps|references|scripts)/[^`\s]+)`", text))):
        p = f"skills/skill-scout/{rel}"
        if not (ROOT / p).exists() and owner_of(p) is None:
            errors.append(f"SKILL.md routes to {rel}, which is neither present nor planned")

# ---- 9. every skill file has an owner -------------------------------------
for f in SKILL_DIR.rglob("*"):
    if f.is_file():
        rel = f.relative_to(ROOT).as_posix()
        if owner_of(rel) is None:
            errors.append(f"{rel}: no owner stage")

# ---- report ---------------------------------------------------------------
for w in warnings:
    print("note :", w)
for e in errors:
    print("ERROR:", e)
singles = [n for n in stages if not used.get(n)]
print(f"\n{len(stages)} stages · {len(singles)} single-folder · {len(stages) - len(singles)} multi · "
      f"{len(errors)} errors · {len(warnings)} planned inputs")
sys.exit(1 if errors else 0)
