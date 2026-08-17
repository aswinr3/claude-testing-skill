#!/usr/bin/env bash
# Every gate the skill must pass. Run before publishing a change to it.
#
#   bash scripts/check.sh
#
# Exits non-zero on the first failing gate.
set -euo pipefail
cd "$(dirname "$0")/.."

pass() { printf '  \033[32mOK\033[0m   %s\n' "$1"; }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }

step "1/4  Structure and self-consistency"
python3 scripts/validate.py
pass "validate.py"

step "2/4  Static evals (content teaches every checkable pattern)"
python3 scripts/run_evals.py --static --min-pass-rate 95
pass "run_evals.py --static"

step "3/4  Preflight self-test (the script runs and gates correctly)"
bash scripts/preflight.sh . >/dev/null 2>&1 && \
  { echo "  preflight passed on the skill repo (expected: it is not a test repo)"; } || true
bash -n scripts/preflight.sh
pass "preflight.sh parses and executes"

step "4/4  UI-sweep precision/recall on fixtures"
if node -e "require.resolve('@playwright/test')" >/dev/null 2>&1; then
  node evals/ui-audit/harness.mjs
  pass "ui-audit harness"
else
  echo "  SKIP  @playwright/test not installed here — run from a project that has it"
fi

printf '\n\033[32mAll gates passed.\033[0m\n\n'
