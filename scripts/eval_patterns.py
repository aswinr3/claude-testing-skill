#!/usr/bin/env python3
"""Pattern grammar for the testing skill's evals.

One grammar, used by both the static checker (does the skill CONTENT teach this?)
and the live checker (did the AGENT'S OUTPUT contain it?), so the two are
comparable.

Grammar
-------
    A OR B OR C     top-level alternation; matches if ANY alternative matches
    (a|b|c)         inline alternation group
    re:<pattern>    an explicit regular expression, compiled as written
    everything else literal substring, case-insensitive, with `.*` as a wildcard

Design notes — each fixes a measured defect in the prior art
------------------------------------------------------------
* Escapes and lookaheads are supported via the explicit `re:` prefix instead of
  being silently matched as literal backslashes. A spec that writes `p\\(95\\)`
  and means a regex previously produced a case that could never pass.
* Markdown emphasis is stripped before matching, so `**not**` still reads as the
  word "not" and a warning is not mistaken for a recommendation.
* Prose patterns that no document contains verbatim are classed SEMANTIC. They
  are never silently counted as passes: a case carrying one is reported
  `deferred` and excluded from the pass rate entirely.
* Python 3.9 compatible. No nested same-quote f-strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# Characters that make a token read as code rather than prose.
_CODEISH = re.compile(r"[(){}\[\].=/<>:_\"'`|$@#\\-]")

# Markdown emphasis / inline code, stripped before matching so that
# `Do **not** expose` still contains the plain word "not".
_EMPHASIS = re.compile(r"[*_`~]+")

_GROUP = re.compile(r"\(([^()]*(?:\||\sOR\s)[^()]*)\)")


def strip_markup(text: str) -> str:
    """Remove emphasis markers so cue words survive bolding."""
    return _EMPHASIS.sub("", text)


def split_alternation(pattern: str) -> List[str]:
    """Split top-level ' OR ', but not ' OR ' inside a (a OR b) group."""
    parts: List[str] = []
    depth = 0
    buf: List[str] = []
    for tok in re.split(r"(\(|\)|\sOR\s)", pattern):
        if tok == "(":
            depth += 1
            buf.append(tok)
        elif tok == ")":
            depth = max(0, depth - 1)
            buf.append(tok)
        elif tok.strip() == "OR" and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(tok)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def is_semantic(pattern: str) -> bool:
    """True when a pattern is prose no document contains verbatim.

    An explicit `re:` pattern is never semantic — the author has said it is a
    regex. Otherwise: strip the scaffolding and ask whether what remains is
    natural language of more than four words with no code-ish token.
    """
    p = pattern.strip()
    if p.startswith("re:"):
        return False
    alts = split_alternation(p)
    if len(alts) > 1:
        return all(is_semantic(a) for a in alts)
    bare = _GROUP.sub(" ", p).replace(".*", " ").replace(".?", " ").strip()
    if _CODEISH.search(bare):
        return False
    return len(bare.split()) > 4


def _compile(alt: str) -> re.Pattern:
    """Compile one alternative into a case-insensitive regex."""
    alt = alt.strip()
    if alt.startswith("re:"):
        return re.compile(alt[3:], re.I)          # explicit regex, as written
    out: List[str] = []
    i = 0
    while i < len(alt):
        if alt.startswith(".*", i):
            out.append(".*")
            i += 2
        elif alt[i] == "(":
            close = alt.find(")", i)
            if close > i and ("|" in alt[i:close] or " OR " in alt[i:close]):
                inner = alt[i + 1:close].replace(" OR ", "|")
                out.append("(?:" + "|".join(re.escape(x.strip()) for x in inner.split("|")) + ")")
                i = close + 1
            else:
                out.append(re.escape(alt[i]))
                i += 1
        else:
            out.append(re.escape(alt[i]))
            i += 1
    return re.compile("".join(out), re.I)


def matches(pattern: str, text: str) -> bool:
    """True if any top-level alternative matches, ignoring markdown emphasis."""
    plain = strip_markup(text)
    for alt in split_alternation(pattern):
        rx = _compile(alt)
        if rx.search(plain) or rx.search(text):
            return True
    return False


@dataclass
class CaseResult:
    case_id: str
    expected_miss: List[str] = field(default_factory=list)
    anti_hit: List[str] = field(default_factory=list)
    semantic: List[str] = field(default_factory=list)

    @property
    def deferred(self) -> bool:
        """A case carrying an uncheckable pattern is deferred, never passed."""
        return bool(self.semantic)

    @property
    def passed(self) -> bool:
        return not self.expected_miss and not self.anti_hit and not self.semantic


def check_case(case: dict, text: str) -> CaseResult:
    r = CaseResult(case_id=case.get("id", "?"))
    for p in case.get("expected_patterns", []):
        if is_semantic(p):
            r.semantic.append(p)
        elif not matches(p, text):
            r.expected_miss.append(p)
    for p in case.get("anti_patterns", []):
        if is_semantic(p):
            continue                      # prose anti-patterns are judge-only
        if matches(p, text):
            r.anti_hit.append(p)
    return r
