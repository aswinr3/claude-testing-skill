#!/usr/bin/env python3
"""Eval runner for the testing skill.

Modes
-----
--static   (default; free, deterministic, CI-safe)
    Does the skill's CONTENT teach every checkable pattern, and avoid
    RECOMMENDING any anti-pattern? A proxy for what an agent that read the
    skill would produce. No model calls.

--live     (the real question)
    Run each prompt through `claude -p` with the skill content appended, and
    check the AGENT'S OUTPUT. Requires the `claude` CLI.

--baseline (proves the eval has teeth)
    Same prompts, no skill. If a bare agent already scores well, the case is
    not measuring the skill.

Scoring — three outcomes, never two
-----------------------------------
    pass       every checkable expected pattern present, no anti-pattern recommended
    fail       a checkable pattern missing, or an anti-pattern recommended
    deferred   the case carries a prose pattern no substring check can judge

Deferred cases are EXCLUDED from the pass rate rather than counted as passes.
A harness that silently passes what it did not check reports a number it has
not earned.

Usage
-----
    python3 scripts/run_evals.py --static
    python3 scripts/run_evals.py --static --min-pass-rate 95
    python3 scripts/run_evals.py --static --spec ui-audit --verbose
    python3 scripts/run_evals.py --live --spec ui-audit
    python3 scripts/run_evals.py --static --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_patterns import check_case, matches, strip_markup  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "references"
EVAL_DIR = ROOT / "evals" / "skill"

# Words that mark a line as a WARNING rather than a recommendation. Matched
# against markdown-stripped text, so `**never**` and `__do not__` still count.
_CUES = (
    "avoid", "never", "don't", "do not", "does not", "cannot", "can not",
    "anti-pattern", "instead of", "instead", "bad:", "wrong", "rejected",
    "reject", "forbid", "deprecated", "smell", "fragile", "proves nothing",
    "not enough", "no ", "not ", "stop ", "worse", "fails", "hides",
    "must not", "won't", "will not", "unless", "rather than", "prefer",
)
_META = ("grep", "rg ", "eslint", "forbid", "no-restricted", "ripgrep", "lint")


def load_content(scope: list[str] | None = None) -> str:
    """SKILL.md plus references. `scope` narrows to named reference files.

    Scoping exists because a skill legitimately contains an anti-pattern in a
    companion document — an escape-hatch or migration guide. Grading the whole
    corpus for every case makes correct content fail.
    """
    parts = [(ROOT / "SKILL.md").read_text()]
    names = scope if scope else sorted(p.name for p in REFS.glob("*.md"))
    for n in names:
        p = REFS / n
        if p.exists():
            parts.append(p.read_text())
    return "\n\n".join(parts)


def _warning_lines(text: str) -> list[bool]:
    """Mark lines that sit inside a warning region."""
    lines = text.splitlines()
    flags = [False] * len(lines)
    in_anti = False
    window = 0
    for i, raw in enumerate(lines):
        low = strip_markup(raw).lower()
        if low.startswith("#"):
            in_anti = any(k in low for k in ("anti-pattern", "mistake", "smell",
                                             "never", "avoid", "not "))
        if any(c in low for c in ("// bad", "# bad", "❌", "anti-pattern",
                                  "wrong:", "don't", "do not", "never", "avoid")):
            window = 6
        flags[i] = in_anti or window > 0 or any(c in low for c in _CUES)
        if window:
            window -= 1
    return flags


def recommends(pattern: str, text: str) -> bool:
    """Does the text RECOMMEND this anti-pattern, or warn against it?

    An occurrence inside a warning region, a heading, or a lint/grep command is
    not a recommendation. Only a neutral-prose occurrence counts.
    """
    lines = text.splitlines()
    warn = _warning_lines(text)
    for i, line in enumerate(lines):
        if warn[i]:
            continue
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        low = strip_markup(line).lower()
        if any(m in low for m in _META):
            continue
        if matches(pattern, line):
            return True
    return False


def run_claude(prompt: str, system: str | None) -> str:
    cmd = ["claude", "-p", prompt]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except FileNotFoundError:
        raise SystemExit("ERROR: `claude` CLI not found. --static works without it.")
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    return out.stdout or out.stderr


def eval_spec(path: Path, mode: str) -> dict:
    spec = json.loads(path.read_text())
    results = []
    for case in spec.get("evals", []):
        scope = case.get("scope")
        if mode == "static":
            text = load_content(scope)
        elif mode == "baseline":
            text = run_claude(case["prompt"], None)
        else:
            system = ("You have access to the following QA skill. Apply it when "
                      "answering.\n\n" + load_content(scope))
            text = run_claude(case["prompt"], system)

        r = check_case(case, text)
        anti = r.anti_hit
        if mode == "static" and anti:
            anti = [p for p in anti if recommends(p, text)]
        deferred = bool(r.semantic)
        passed = not r.expected_miss and not anti and not deferred
        results.append({
            "id": r.case_id,
            "passed": passed,
            "deferred": deferred,
            "missing": r.expected_miss,
            "anti_hit": anti,
            "semantic": r.semantic,
        })

    scored = [r for r in results if not r["deferred"]]
    passed = sum(1 for r in scored if r["passed"])
    return {
        "spec": spec.get("capability", path.stem),
        "mode": mode,
        "total": len(results),
        "scored": len(scored),
        "passed": passed,
        "failed": len(scored) - passed,
        "deferred": len(results) - len(scored),
        "cases": results,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--static", action="store_true", default=True)
    g.add_argument("--live", action="store_true")
    g.add_argument("--baseline", action="store_true")
    ap.add_argument("--spec", help="run one capability spec by stem")
    ap.add_argument("--min-pass-rate", type=float, default=None)
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    mode = "live" if args.live else "baseline" if args.baseline else "static"
    specs = sorted(EVAL_DIR.glob("*.json"))
    if args.spec:
        specs = [p for p in specs if p.stem == args.spec]
        if not specs:
            raise SystemExit("no such spec: " + args.spec)

    reports = [eval_spec(p, mode) for p in specs]

    tot = sum(r["total"] for r in reports)
    scored = sum(r["scored"] for r in reports)
    passed = sum(r["passed"] for r in reports)
    deferred = sum(r["deferred"] for r in reports)

    for r in reports:
        flag = "OK  " if r["failed"] == 0 else "FAIL"
        line = "  {} {}: {}/{} pass".format(flag, r["spec"], r["passed"], r["scored"])
        if r["deferred"]:
            line += ", {} deferred (not scored)".format(r["deferred"])
        print(line)
        for c in r["cases"]:
            if not c["passed"] and not c["deferred"]:
                if c["missing"]:
                    print("        {} missing: {}".format(c["id"], c["missing"]))
                if c["anti_hit"]:
                    print("        {} RECOMMENDS anti-pattern: {}".format(c["id"], c["anti_hit"]))
            elif c["deferred"] and args.verbose:
                print("        {} deferred: {}".format(c["id"], c["semantic"]))

    rate = (passed / scored * 100) if scored else 0.0
    print("\nSpecs: {}  Cases: {}  Scored: {}  Pass: {}  Fail: {}  Deferred: {}"
          .format(len(reports), tot, scored, passed, scored - passed, deferred))
    print("Pass rate (scored only): {:.1f}%".format(rate))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(reports, indent=2))
        print("Wrote " + args.json_out)

    if args.min_pass_rate is not None and rate < args.min_pass_rate:
        print("FAIL: pass rate {:.1f}% is below the {:.1f}% floor".format(rate, args.min_pass_rate))
        sys.exit(1)
    sys.exit(0 if scored - passed == 0 else 1)


if __name__ == "__main__":
    main()
