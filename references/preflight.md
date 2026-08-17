# Preflight — the mechanics, made executable

Every check in `scripts/preflight.sh` exists because a real run broke on it. Prose guidance
did not prevent any of them; a script that exits non-zero does.

**Run it before writing a single test.**

```bash
eval "$(bash ~/.claude/skills/testing/scripts/preflight.sh /path/to/repo)" || exit 1
```

On success it exports the run's environment. On failure it explains and exits 1.

| Variable | Use |
|---|---|
| `RUN_REPO` | **Every** git command in the run: `git -C "$RUN_REPO" …` |
| `RUN_ID` | `2026-08-17-1305` — the run's identity |
| `RUN_DIR` | `test-results/<RUN_ID>` — the run record. Required by `evidence.md` |
| `RUN_ARTIFACTS` | `.playwright-artifacts/<RUN_ID>` — the runner's scratch |
| `RUN_DIRT_SNAPSHOT` | Paths already modified **before** the run started |

---

## The seven failures it prevents

### 1. Branching the wrong repository

A vendored or nested repository under the working tree captures `git` the moment the shell's
cwd drifts into it. A run once created its test branch inside a cloned dependency and left
the real repo untouched.

Preflight lists every nested `.git` it finds and prints the resolved toplevel. **The fix is
mechanical: never issue a bare `git` command during a run.** Always `git -C "$RUN_REPO"`.
Nested repositories are *separate projects* — never branch, commit, or push in them.

### 2. Committing unrelated deletions

`git add -A` once swept 69 pending deletions from an earlier session into a test commit,
destroying a previous run's record. `git add -u` and `git add .` do the same thing.

Preflight snapshots the pre-existing dirt to `$RUN_DIRT_SNAPSHOT`. **Commit by explicit path
only:**

```bash
git -C "$RUN_REPO" add "$RUN_DIR" e2e/checkout.spec.ts     # named paths, nothing else
git -C "$RUN_REPO" commit -m "test: checkout conformance run"
```

Before committing, diff the staged set against the snapshot. Anything staged that appears in
the snapshot was not yours — unstage it.

### 3. The runner deleting the run record

Playwright's `outputDir` **defaults to `test-results/`, and Playwright wipes it before every
run.** That is the directory holding the deliverable. Preflight fails the run when
`outputDir` is unset or points inside `test-results/`.

```ts
outputDir: process.env.RUN_ARTIFACTS ?? '.playwright-artifacts',
```

### 4. One run destroying the previous run's evidence

Artefacts written to a fixed path are gone the next time anything runs. Preflight namespaces
them per run: `.playwright-artifacts/<RUN_ID>`. Evidence is copied into `$RUN_DIR` and is
never read back out of the runner's scratch.

### 5. Evidence filenames collapsing

Every Playwright failure screenshot is named `test-failed-1.png`. Copying five of them into
one folder yields one file. **Name at capture time, not afterwards** — by then the mapping
from file to case is gone:

```ts
test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status === testInfo.expectedStatus) return
  const id = testInfo.title.match(/TC-\d{4}|SPEC:[A-Z0-9-]+/)?.[0] ?? 'UNTRACED'
  const vp = page.viewportSize()
  const name = `${id}__${testInfo.title.replace(/\W+/g, '-').slice(0, 40)}__${vp?.width}x${vp?.height}.png`
  await page.screenshot({ path: path.join(process.env.RUN_DIR!, 'screenshots', name), fullPage: true })
})
```

An untraceable screenshot is not evidence.

### 6. Config collision between campaigns

Two campaigns sharing `playwright.config.ts` overwrite each other's projects, baseURL, and
auth state. Namespace per campaign — `playwright.<campaign>.config.ts` — and select it
explicitly with `--config`. Never edit a config in place mid-run and never restore one from
memory; recover it from git.

### 7. A harness that exits 0 having run nothing

Observed for real: a Cypress suite failed to start, reported `tests: 0, failing: '?'`, and
**exited 0**. A CI gate keyed on exit status reads that as a pass.

**Assert the count, not the exit code.** A run that executed zero tests is a failed run, and
it is recorded as a harness defect — never as a baseline and never as a pass.

```bash
[ "$(jq '.suites | flatten | length' report.json)" -gt 0 ] || { echo "ran zero tests"; exit 1; }
```

---

## Non-Playwright runners

The process is runner-agnostic; only the adapter changes. Preflight detects Playwright,
Cypress, Vitest, and Jest, and exports `RUN_RUNNER`.

| Runner | Artefact dir | Machine-readable report | Zero-test guard |
|---|---|---|---|
| Playwright | `outputDir` | `--reporter=json` | count `suites` |
| Cypress | `screenshotsFolder`, `videosFolder` | `--reporter json` | `stats.tests > 0` |
| Vitest | — | `--reporter=json` | `numTotalTests > 0` |
| Jest | — | `--json --outputFile` | `numTotalTests > 0` |

If the project's runner is not in this table, record it and adapt — **do not report the
types it would have covered as "Not run" because the tooling was unfamiliar.**

---

## Finishing a run

```bash
git -C "$RUN_REPO" status --porcelain > /tmp/after.txt
diff "$RUN_DIRT_SNAPSHOT" /tmp/after.txt      # everything new must be yours
git -C "$RUN_REPO" add "$RUN_DIR" <explicit test paths>
git -C "$RUN_REPO" commit -m "test: <scope> conformance run"
```

Commit the run record. `branching.md` is the authority on branch lifecycle; the run record is
a deliverable, not a build artefact, and it belongs in history.
