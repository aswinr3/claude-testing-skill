#!/usr/bin/env python3
"""Structural and consistency validator for the testing skill.

Two kinds of check:

  STRUCTURAL  — generic, and true of any skill: cited files exist, no orphan
                reference files, frontmatter present, line budgets respected.

  CONSISTENCY — the skill contradicting itself. These are the failures that
                cost a real run: two files prescribing different column orders,
                different default paths, or a stated count that disagrees with
                the table beneath it. Every contradiction found by hand becomes
                a permanent check here so it cannot come back.

    python3 scripts/validate.py            # human output, exit 1 on error
    python3 scripts/validate.py --json     # machine output
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
REFS = ROOT / "references"
MAX_SKILL_LINES = 450

Error = tuple[str, str]  # (check, message)


# ---------------------------------------------------------------- structural

def check_frontmatter(errors: list[Error]) -> None:
    text = SKILL.read_text()
    if not text.startswith("---"):
        errors.append(("frontmatter", "SKILL.md has no YAML frontmatter"))
        return
    fm = text.split("---", 2)[1]
    for field in ("name", "description"):
        if not re.search(rf"^{field}:", fm, re.M):
            errors.append(("frontmatter", f"missing '{field}'"))


def check_line_budget(errors: list[Error]) -> None:
    n = len(SKILL.read_text().splitlines())
    if n > MAX_SKILL_LINES:
        errors.append(("budget", f"SKILL.md is {n} lines (max {MAX_SKILL_LINES})"))


def _cited(text: str) -> set[str]:
    """Files cited AS references — i.e. written with the `references/` prefix.

    Deliberately narrow. A bare `defects.md` is a file the skill tells you to
    PRODUCE, not one it ships; matching those made this check useless noise.
    """
    return set(re.findall(r"references/([a-z0-9-]+\.md)", text))


def check_references_resolve(errors: list[Error]) -> None:
    on_disk = {p.name for p in REFS.glob("*.md")}
    all_text = SKILL.read_text() + "".join(p.read_text() for p in REFS.glob("*.md"))
    for name in sorted(_cited(all_text) - on_disk):
        errors.append(("dangling-ref", f"cited but missing: references/{name}"))


def check_no_orphans(errors: list[Error]) -> None:
    text = SKILL.read_text()
    # SKILL.md cites its own reference files both as `references/x.md` (the
    # routing table) and bare `x.md` (prose). Accept either here.
    cited = _cited(text) | set(re.findall(r"`([a-z0-9-]+\.md)`", text))
    for p in sorted(REFS.glob("*.md")):
        if p.name not in cited:
            errors.append(("orphan", f"references/{p.name} is never cited from SKILL.md"))


# --------------------------------------------------------------- consistency

def check_column_count_claims(errors: list[Error]) -> None:
    """'20 columns, `A`-`T`' must match the letter range AND the table rows."""
    for p in sorted(REFS.glob("*.md")):
        text = p.read_text()
        m = re.search(r"(\d+)\s+columns?,\s*`([A-Z])`\s*[–-]\s*`([A-Z])`", text)
        if not m:
            continue
        claimed, lo, hi = int(m.group(1)), m.group(2), m.group(3)
        span = ord(hi) - ord(lo) + 1
        rows = len(re.findall(r"^\|\s*`?([A-Z])`?\s*\|", text, re.M))
        if claimed != span:
            errors.append(("column-count",
                           f"{p.name}: says {claimed} columns but range {lo}-{hi} spans {span}"))
        if rows and claimed != rows:
            errors.append(("column-count",
                           f"{p.name}: says {claimed} columns but the table defines {rows}"))


def check_first_column_agreement(errors: list[Error]) -> None:
    """Files must agree on which column is first in the case register."""
    claims: dict[str, str] = {}
    for p in [SKILL, *sorted(REFS.glob("*.md"))]:
        text = p.read_text()
        m = re.search(r"`?([A-Za-z() ]+?)`?\s+(?:is|as)\s+(?:its|the)\s+first column", text)
        if m:
            claims[p.name] = m.group(1).strip().strip("`")
        m2 = re.search(r"^\|\s*A\s*\|\s*`?([A-Za-z() ]+?)`?\s*\|", text, re.M)
        if m2:
            claims.setdefault(p.name + " (column table)", m2.group(1).strip())
    values = {v.lower().replace("(slice)", "").strip() for v in claims.values()}
    if len(values) > 1:
        detail = "; ".join(f"{k} -> '{v}'" for k, v in claims.items())
        errors.append(("column-order", f"files disagree on the first column: {detail}"))


def check_path_templates(errors: list[Error]) -> None:
    """One artifact directory, one template. `<date>` vs `<date>-<time>` loses runs."""
    seen: dict[str, set[str]] = {}
    pat = re.compile(r"test-results/(<[a-z-]+>|\d{4}-\d{2}-\d{2}(?:-\d{4})?)/")
    for p in [SKILL, *sorted(REFS.glob("*.md"))]:
        for tok in pat.findall(p.read_text()):
            shape = "dated+time" if re.match(r"^\d{4}-\d{2}-\d{2}-\d{4}$", tok) else (
                "dated" if re.match(r"^\d{4}-\d{2}-\d{2}$", tok) else tok)
            seen.setdefault(shape, set()).add(p.name)
    if len(seen) > 1:
        detail = "; ".join(f"{k} in {sorted(v)}" for k, v in sorted(seen.items()))
        errors.append(("path-template", f"run directory is written several ways: {detail}"))


# A contradiction registry. Each entry: two rules that cannot both be followed.
# Add one every time a run trips over conflicting guidance.
CONTRADICTIONS = [
    {
        "name": "gitignore-default",
        "a": ("branching.md", r"Default to yes on a test branch"),
        "b": ("results.md", r"Add `test-results/` to `\.gitignore` unless"),
        "why": "opposite defaults for whether the run record is committed",
    },
    {
        "name": "outputdir-collision",
        "a": ("results.md", r"Write to a `test-results/` directory at the \*\*project root\*\*"),
        "b": ("evidence.md", r"process\.env\.RUN_DIR \?\? path\.join\('test-results', 'latest'\)"),
        "why": "evidence defaults into the directory Playwright wipes before each run",
    },
]


def check_contradictions(errors: list[Error]) -> None:
    for c in CONTRADICTIONS:
        (fa, pa), (fb, pb) = c["a"], c["b"]
        A, B = REFS / fa, REFS / fb
        if not (A.exists() and B.exists()):
            continue
        if re.search(pa, A.read_text()) and re.search(pb, B.read_text()):
            errors.append(("contradiction", f"{c['name']}: {fa} vs {fb} — {c['why']}"))


def check_round_trip_contiguous(errors: list[Error]) -> None:
    """Columns the run writes back must be contiguous, or they cannot be pasted.

    Sheets pastes a rectangular block. If `Notes` sits between `Defect Ref` and
    `Evidence`, the documented round-trip is impossible as written.
    """
    text = (REFS / "test-cases-sheet.md").read_text()
    letters = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*([A-Z])\s*\|\s*`([^`]+)`", line)
        if m:
            letters[m.group(2)] = m.group(1)
    written = ["Status", "Last Run", "Defect Ref", "Evidence", "Evidence Path"]
    idx = sorted(ord(letters[c]) for c in written if c in letters)
    if len(idx) == len(written) and idx != list(range(idx[0], idx[0] + len(idx))):
        gap = [chr(c) for c in range(idx[0], idx[-1] + 1)
               if chr(c) not in [letters[c2] for c2 in written if c2 in letters]]
        errors.append(("round-trip",
                       f"run-updated columns are not contiguous; {gap} sits between them"))


CHECKS = [
    check_frontmatter, check_line_budget, check_references_resolve, check_no_orphans,
    check_column_count_claims, check_first_column_agreement, check_path_templates,
    check_round_trip_contiguous,
    check_contradictions,
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    errors: list[Error] = []
    for fn in CHECKS:
        fn(errors)

    if args.json:
        print(json.dumps([{"check": c, "message": m} for c, m in errors], indent=2))
    else:
        for c, m in errors:
            print(f"  [{c}] {m}")
        print(f"\n{len(list(REFS.glob('*.md')))} reference files · {len(errors)} error(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
