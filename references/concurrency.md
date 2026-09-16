# Concurrent runs, shared budgets, and shared state

The rest of this skill assumes one session testing one platform. That assumption breaks the moment
a second session starts, and everything in this file comes from watching it break: eight sessions
testing one staging environment lost roughly six hundred recorded cases, produced sixty-three
duplicate case ids, and spent more wall-clock waiting on a shared rate limiter than running tests.

None of those were violations of the rules elsewhere in this skill. They were gaps.

Load this whenever more than one session, agent or suite runs against the same target.

---

## 1. The shared request budget is usually the real bottleneck

Most hosted environments rate-limit **per IP**, not per session. Every session on one machine draws
on one budget. Adding sessions does not add throughput — it splits the same allowance and makes
every session slower.

Measured on a platform allowing 1000 requests per 900 seconds, with six suites live: a module run
that does ~50 seconds of actual work took **12.9 minutes**, of which ~12 was waiting. The window
rolled to full and was drained by other sessions within seconds, so polling for a clear window never
caught one.

**Find the limiter before planning the run.** One request reveals it:

```
ratelimit-limit: 1000
ratelimit-policy: 1000;w=900
ratelimit-remaining: 0
ratelimit-reset: 228
```

Then decide concurrency from the budget, not from how many sessions you can start. Two or three
sessions sharing a 1000/900s budget will finish more modules per hour than eight.

### Wait the advertised reset — never a fixed guess

A wrapper that sleeps a flat interval and then assumes the window rolled will sleep again, and
again. One run took **6.6 hours to do 20 minutes of work** that way. Read `ratelimit-reset` (or
`retry-after`) and sleep exactly that, once.

### 🔴 The runner's per-test timeout must exceed a full window

This is the trap that costs the most and looks like something else entirely.

Playwright's default per-test timeout is **90 seconds**. A rate-limit window can be **900**. A
request wrapper that correctly waits out the advertised reset is useless if the test is killed
mid-wait — and the run reports *test failures*, not a limiter problem.

One observed run produced **25 tests and zero case rows** for exactly this reason.

```
npx playwright test <specs> --timeout=1800000 --global-timeout=21600000
```

Set the per-test timeout above the longest window the platform advertises. Pass it on the command
line rather than editing a shared config other sessions also use.

### A 429 is a precondition, not a defect

Record it `Blocked` with the reason. A spent limiter says nothing about the platform. Recording it
as `Fail` invents a defect and, worse, makes the run record unusable for deciding what to re-run.

---

## 2. 🔴 Any tool that reads all state then writes all state back is unsafe

This single code shape caused every case-log loss observed:

```js
const rows = loadAllModules(dir);   // reads every module's log
await takeScreenshots(rows);        // minutes pass; other sessions append
writeAllModulesBack(rows);          // every row appended meanwhile is destroyed
```

An evidence renderer with that shape rewrote eleven modules' logs from one stale snapshot. A report
builder with that shape overwrote git-tracked, user-facing result files with "Not tested yet" stubs
for any module whose log happened to be empty at read time. A module-reset script wrote an empty
string when every row matched its filter.

**Before running any shared script, ask what it writes.** If the answer is "everything", it is
unsafe while others run.

Rules:

- **Scope a write-back to exactly what the run touched.** Not to everything it read.
- **A scoping flag that filters the *work* does not necessarily scope the *write*.** One tool
  offered `EVIDENCE_MODULE=SLICE-08` that filtered which failures got screenshotted while the
  write-back still iterated every module. Read the code; do not trust the flag's name.
- **Snapshot outside the repository before running one.** Case logs are frequently untracked, which
  means git cannot recover them. A copy costs nothing.
- **Importing a module executes it.** One session syntax-checked a report builder with
  `node -e "import('./report.mjs')"` and fired a full build. Use `node --check` on a copy.
- **Gate destructive tooling on the state it will destroy.** Check for empty logs first, and refuse:

  ```bash
  find test-results/<date>-<time>/cases -name '*.jsonl' -size 0 -print   # non-empty output = do not run
  ```

---

## 3. Case ids come from a fixed block, never from the log's maximum

Deriving the next id by reading the current maximum is the obvious implementation and it collides
immediately: two sessions read the same maximum and both count up from it. Observed twice in one
project — 41 duplicate ids, then 5 more.

Allocate a block per module with no coordination:

```
block = module number x 1000    MODULE-02 -> TC-2001..    MODULE-05 -> TC-5001..
```

Do the same for defect ids: **claim a block up front** rather than taking "the next free number",
which two sessions will both take.

Note the failure mode this does *not* cover: if two processes run the same suite concurrently with
the same case-log path, each numbers from the same block start and produces **identical ids with
identical content**. Exact-duplicate rows are the signature. Guard by ensuring one instance —
a lock file, or a check for a running worker — and by refusing to install a result set that contains
rows from a module the run did not test.

---

## 4. A session that writes gets its own account

The cheapest fix for the whole class of cross-session data collisions. If one session places orders
while another verifies "total orders = 47", the second records a failure that is really the first
session's write — a finding that looks real and is not, which is worse than a slow run.

- Register a dedicated account per session, per module where the module is destructive.
- Name it so it is attributable (`qa-<module>-<purpose>-<suffix>`).
- Treat any shared, seeded account as **read-only** unless the module under test owns it.
- **State which account each case used in its precondition.** A result that does not say which
  merchant it ran against cannot be reproduced or trusted.

Never run two modules that share a data fixture at the same time — order modules against one
merchant's orders, credit modules against its balance.

---

## 5. 🔴 Your own earlier cases mutate the fixtures your later cases need

"Prove the fixture" elsewhere in this skill treats fixtures as static. A suite mutates its own.

Two observed instances, both of which initially presented as defects:

- An authorization matrix exercised `POST /mark-all-read` as a permission-less user. The platform
  allowed it — a real finding — and the account's unread count went to zero. A later UI case then
  failed to find a "Mark all as read" button that is conditionally rendered and was **correctly**
  absent.
- The first discount tier written on a product was stored open-ended (`upper_quantity: null`), so
  every later tier on that product legitimately returned `409 OVERLAPPING_TIER` — before any
  percentage validation ran. Four boundary cases "failed" for a reason that had nothing to do with
  the bound.

The rule:

- **A case that depends on fixture state asserts that state first, and Blocks when it is absent** —
  naming the interference, not reporting a defect.
- **A refusal for an unrelated reason is neither a pass nor a fail.** It is `Blocked`. Recording it
  as a pass is a refusal for the wrong reason; recording it as a fail invents a defect out of your
  own suite.
- **Destructive cases run last, or on a disposable account**, so they cannot strand later cases.
- **Cycle the resource, not the value**, when a write is refused for colliding with an earlier one.
  Distinct quantities did not help above; distinct products did.

---

## 6. Findings belong in a file that generators consume, never one they produce

A generated file will be regenerated, and everything hand-written into it disappears. Observed:
eight defect write-ups placed into a `defects.md` that a report builder recreates wholesale from a
hardcoded array — erased twice, silently, with no error.

- Write findings into a **per-module source file the generator appends verbatim**
  (`notes/MODULE-NN.md` or equivalent).
- Populate the machine-readable `defect` field on each failing case row so the generator can emit
  the reference itself.
- Keep a copy outside the repository until it is committed.
- **Before trusting that a write landed, grep it back.** `grep -c '^## DEF-19' <file>`.

---

## 7. Confirm the effect, not the tool that reports it

A command's exit code says the command ran, not that it worked.

A runaway suite was reported killed **three times** while it kept writing. `pkill -f` never matched
the process, and the PID column had shifted. The giveaway was not the process list — it was that the
output file kept growing.

- **Verify a kill by checking the artefact stopped changing**, not by checking the process list went
  quiet. The tool that misreported the process is not the tool to confirm it died.
- **Never parse tool output positionally when a field can contain a space.** On a machine whose
  account name is `Aswin Rajasekar`, both of these are silently wrong:

  ```bash
  ls -l … | awk '$5==0'        # $5 is the group id, not the size — guard never fires
  ps -ef  | awk '{print $2}'   # PID is $3 — kill targets nothing
  ```

  Use `find … -size 0 -print` for files, and a structured process query
  (`Get-CimInstance Win32_Process … | Select ProcessId, CommandLine` on Windows) for processes.

---

## 8. Claim a module before starting, on evidence

Assignments made by inferring ownership from session state landed on already-running modules **four
times** in one project. Check the artefacts instead — it takes seconds:

```bash
ls tests/e2e/*sNN-*          # specs
ls tests/lib/sNN.ts          # harness
ls tests/plans/sNN.mjs       # register
ls <date>-<time>/cases/<slug>.jsonl  # case log
```

All four absent, and no process referencing the module, means cold. Anything present means someone
is there — a module file still reading "Not tested yet" proves nothing, because the file that says
so is generated and may simply be stale.

---

## 9. Record what the run changed

Concurrent sessions inherit each other's state. A run that does not say what it consumed leaves the
next session debugging a fixture nobody can account for.

Every run record gets a **"What this run changed"** section naming the irreversible parts: which
records were emptied, which counters were spent, which flags were set and whether they were
restored, which accounts were created. Identify them by id, so the state is attributable rather than
mysterious.
