#!/usr/bin/env bash
# Preflight for a test run. Every check here exists because a real run broke on it.
#
#   bash scripts/preflight.sh [REPO_PATH]
#
# Emits shell assignments on success; exits non-zero and explains on failure.
# Source it to get the environment:
#
#   eval "$(bash scripts/preflight.sh /path/to/repo)" || exit 1
#
# It is deliberately noisy on stderr and machine-readable on stdout.

set -uo pipefail

REPO="${1:-$PWD}"
fail=0
say() { printf '  %-24s %s\n' "$1" "$2" >&2; }
bad() { printf '  %-24s %s\n' "$1" "FAIL — $2" >&2; fail=1; }

printf '\nPreflight — %s\n\n' "$REPO" >&2

# ---------------------------------------------------------------- 1. the repo
# A nested/vendored repository under the working directory will silently capture
# `git` commands when the shell cwd drifts into it. Every git call in the run
# must be pinned with `git -C "$RUN_REPO"`.
if ! git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  bad "repo" "$REPO is not a git repository"
else
  TOPLEVEL=$(git -C "$REPO" rev-parse --show-toplevel)
  say "repo" "$TOPLEVEL"
  if [ "$(cd "$REPO" && pwd -P)" != "$(cd "$TOPLEVEL" && pwd -P)" ]; then
    bad "repo" "$REPO is inside $TOPLEVEL, not its root — pin with git -C"
  fi
fi

# Nested repositories: report them so the run cannot branch the wrong one.
NESTED=$(find "$REPO" -mindepth 2 -maxdepth 4 -name .git -not -path '*/node_modules/*' 2>/dev/null | head -5)
if [ -n "$NESTED" ]; then
  say "nested repos" "$(echo "$NESTED" | tr '\n' ' ')"
  say "" "→ these are SEPARATE repos. Never branch or commit in them."
fi

# ------------------------------------------------------------- 2. the branch
BRANCH=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo UNKNOWN)
if [ "$BRANCH" = "HEAD" ]; then
  bad "branch" "detached HEAD — switch to a branch before testing"
elif [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  bad "branch" "on the default branch ($BRANCH) — create <parent>-test-<slug> first"
else
  say "branch" "$BRANCH"
fi

# ------------------------------------------------------- 3. pre-existing dirt
# Snapshot what was ALREADY modified. Anything in this list must never be swept
# into a run commit: `git add -A` once deleted 69 unrelated files this way.
DIRT_FILE="${TMPDIR:-/tmp}/preflight-dirt-$$.txt"
git -C "$REPO" status --porcelain > "$DIRT_FILE" 2>/dev/null
DIRT_N=$(wc -l < "$DIRT_FILE" | tr -d ' ')
if [ "$DIRT_N" -gt 0 ]; then
  say "pre-existing changes" "$DIRT_N path(s) — snapshot at $DIRT_FILE"
  say "" "→ commit run artefacts by EXPLICIT PATH only. Never git add -A / -u / ."
else
  say "pre-existing changes" "none — tree is clean"
fi

# ------------------------------------------------------------- 4. the run dir
RUN_ID="$(date +%Y-%m-%d-%H%M)"
RUN_DIR="test-results/${RUN_ID}"
if [ -e "$REPO/$RUN_DIR" ]; then
  bad "run dir" "$RUN_DIR already exists — pick another or the record will be mixed"
else
  say "run dir" "$RUN_DIR"
fi

# ---------------------------------------------------- 5. runner + outputDir
RUNNER="none"
CFG=""
for c in playwright.config.ts playwright.config.js playwright.config.mjs; do
  [ -f "$REPO/$c" ] && { RUNNER="playwright"; CFG="$c"; break; }
done
if [ "$RUNNER" = "none" ]; then
  for c in cypress.config.ts cypress.config.js cypress.json; do
    [ -f "$REPO/$c" ] && { RUNNER="cypress"; CFG="$c"; break; }
  done
fi
if [ "$RUNNER" = "none" ] && [ -f "$REPO/package.json" ]; then
  grep -q '"vitest"' "$REPO/package.json" 2>/dev/null && RUNNER="vitest"
  grep -q '"jest"'   "$REPO/package.json" 2>/dev/null && RUNNER="${RUNNER}+jest"
fi
say "runner" "$RUNNER${CFG:+ ($CFG)}"

# The default outputDir is `test-results/`, which Playwright WIPES before every
# run — that is the directory holding the run record. This is the single most
# destructive default in the toolchain.
if [ "$RUNNER" = "playwright" ] && [ -n "$CFG" ]; then
  if ! grep -q 'outputDir' "$REPO/$CFG"; then
    bad "outputDir" "not set in $CFG — defaults to test-results/ and WIPES the run record"
  elif grep -qE "outputDir:\s*['\"]test-results" "$REPO/$CFG"; then
    bad "outputDir" "points into test-results/ — it will delete the run record"
  else
    say "outputDir" "$(grep -oE "outputDir:\s*['\"][^'\"]+" "$REPO/$CFG" | head -1 | cut -d\' -f2)"
  fi
fi

# Per-run artefact namespace, so two campaigns cannot overwrite each other.
ARTIFACTS=".playwright-artifacts/${RUN_ID}"
say "artifacts" "$ARTIFACTS"

# --------------------------------------------------------------- 6. evidence
say "evidence naming" "TC-####__rule__WxH.png, assigned in afterEach"
say "" "→ every Playwright shot is test-failed-1.png; rename AT CAPTURE TIME"

# ----------------------------------------------------------------- 7. verdict
printf '\n' >&2
if [ "$fail" -ne 0 ]; then
  printf 'PREFLIGHT FAILED — fix the above before testing.\n\n' >&2
  exit 1
fi
printf 'Preflight OK.\n\n' >&2

cat <<EOF
export RUN_REPO="$REPO"
export RUN_ID="$RUN_ID"
export RUN_DIR="$RUN_DIR"
export RUN_ARTIFACTS="$ARTIFACTS"
export RUN_BRANCH="$BRANCH"
export RUN_RUNNER="$RUNNER"
export RUN_DIRT_SNAPSHOT="$DIRT_FILE"
EOF
