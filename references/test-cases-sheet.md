# Test cases in Google Sheets

Cases live in Google Sheets. This defines the column contract, how to emit rows that paste cleanly, and a ready-to-use Gemini prompt for generating them from the document set.

## Column contract

One row per case. 22 columns, `A`–`V`. Header row exactly as below.
**`Module (Slice)` is column `A`** — the register groups and filters by the thing a
team owns, so it leads. `SKILL.md` and `results.md` state the same rule.

| Col | Header | Content | Rules |
|---|---|---|---|
| A | `Module (Slice)` | `SLICE-09 Order Management` | Feature area; **first column** so the sheet groups by it |
| B | `Case ID` | `TC-0001` | Zero-padded, never reused, never renumbered |
| C | `Requirement ID` | `PRD:BR-03` | **Namespaced** (see `document-map.md`). Multiple separated by `; ` |
| D | `Source` | `PRD §9` / `SLICE-04 Rules` | Document + section, so a reviewer can find it |
| E | `Test Type` | `Functional` | One of: Unit, Integration, Mock, Smoke, Sanity, Functional, Regression, Exploratory, Non-Functional |
| F | `Level` | `E2E` | One of: Unit, API, E2E, Manual |
| G | `Title` | `Rejects reset for unregistered email without leaking existence` | Behaviour + condition. Never "test login" |
| H | `Preconditions` | `User u_1 exists, verified. Clock frozen at 2026-01-01T00:00:00Z.` | State, seed data, role, flags |
| I | `Test Data` | `email=nobody@test.local` | Concrete values, never "some user" |
| J | `Steps` | `1. POST /auth/reset with email → 2. Read response` | **Single line.** Number and separate with ` → ` |
| K | `Expected Result` | `202; body {ok:true}; identical to registered-email response` | The oracle. Observable, specific |
| L | `Must Not Happen` | `No email sent; no row written to reset_tokens` | The negative oracle. `—` if none |
| M | `Technique` | `Equivalence partition` | BVA, Equivalence partition, Decision table, State transition, Pairwise, Error guessing, Direct |
| N | `Priority` | `P0` | P0 / P1 / P2, matching the PRD §5 scope table |
| O | `Automated` | `Yes` | Yes / No / Planned |
| P | `Automation Ref` | `e2e/auth.spec.ts › rejects unregistered` | File › test name. `—` when manual |
| Q | `Status` | `Not run` | Not run / Pass / Fail / Blocked / Skipped |
| R | `Last Run` | `2026-08-14` | ISO date |
| S | `Defect Ref` | `BUG-112` | `—` when none |
| T | `Evidence` | `=HYPERLINK("...", "TC-0142 ▸ text-clipped")` | Screenshot / trace link. `—` when none. See `evidence.md` |
| U | `Evidence Path` | `test-results/2026-08-14-1432/screenshots/TC-0142__text-clipped__375x812.png` | Offline record — survives dead links |
| V | `Notes` | `Provisional — pending PM:PM-01` | Flag provisional cases here. Last, so `Q`–`U` paste as one block |

### Rules that keep the sheet usable

- **One assertion per row.** If `Expected Result` needs "and" joining unrelated things, split the row.
- **`Requirement ID` is mandatory.** A row without one is an orphan — either find its requirement or delete it.
- **Never renumber `Case ID`.** Retired cases get `Status: Skipped` and a note; they do not vacate their number.
- **Provisional cases** (asserting a safe default while a `Q-`/`PM-`/`UX-`/`DS-` decision is open) say so in `Notes` and take `Priority: P1` at most — they must not gate MVP acceptance.

---

## Emitting rows that paste cleanly

**Use TSV, not CSV.** Test steps and expected results contain commas constantly; CSV quoting breaks on the first unescaped one and shifts every column right.

Two hard rules for Sheets paste:

1. **No newline inside any cell.** A newline starts a new row mid-record and corrupts everything after it. Steps go on one line separated by ` → `.
2. **No literal tab inside any cell.** A tab starts a new column.

Paste path: copy the TSV → select cell `A1` → **Edit ▸ Paste special ▸ Paste values only**. A plain paste can let Sheets re-interpret `1. Open page` as a list or `2026-01-01` as a date in the wrong locale.

If a run produces more than ~500 rows, save as `.tsv` and use **File ▸ Import ▸ Replace current sheet**, with separator "Tab" and **"Convert text to numbers, dates, and formulas" set to No** — otherwise IDs like `1-2` become dates.

---

## The Gemini prompt

Paste this into Gemini with the documents attached. It is written to be strict about the failure modes that make generated test cases useless — vague oracles, invented requirements, and cases that can't be traced.

````text
You are a senior QA engineer. Generate test cases from the attached product
documents and output them as TSV for pasting into Google Sheets.

## Read first
Read every attached document completely before writing any case. Do not skim
and do not extrapolate from section titles. The documents follow a fixed
template set: PRD, Permissions Matrix, Workflows, User Flows, Design System,
Data Model, Architecture, Glossary, ADRs, and per-feature Vertical Slice specs.

## Absolute rules
1. Every case traces to a requirement ID that EXISTS in the documents. Never
   invent a requirement. If behaviour seems required but no document states it,
   do not write a case — list it under AMBIGUITIES instead.
2. Namespace every requirement ID by its source document, because `D-` is used
   for two different things across the template set:
   PRD:BR-03, PRD:NFR-01, PRD:AC-02, PRD:D-01, PM:PM-01, WF:D-01, UX:UX-01,
   DS:DS-01, DM:DM-01, AR:AR-01, SLICE-04:S04-02, ADR-007
3. One assertion per case. If the expected result needs "and" to join unrelated
   outcomes, split it into two cases.
4. The expected result must be an OBSERVABLE oracle. "Login works" is rejected.
   "Redirects to /dashboard and header shows the user's email" is accepted.
   State the exact status code, message, field, element, or record change.
5. Use concrete test data. Never "a user" or "some value". Write
   user_verified@test.local, amount=0, amount=-1, quantity=999999.
6. Anything undecided — an open Q-, PM-, UX-, DS-, DM-, or S[NN]- decision —
   is NOT an approved requirement. If you write a case for its safe default,
   put "Provisional — pending <ID>" in Notes and set Priority no higher than P1.
7. Only generate cases for P0 (MVP) scope items unless the document marks them
   otherwise. Note P1/P2 items in a separate list rather than as rows.

## Derivation techniques — apply deliberately, name the one you used
- Boundary value analysis: for every numeric or time limit, generate n-1, n, n+1.
- Equivalence partitioning: one case per input class, not one per input value.
- Decision table: when 2+ conditions combine, enumerate reachable combinations.
- State transition: for every status flow, cover each legal transition plus one
  representative ILLEGAL transition per state.
- Pairwise: when many independent parameters combine (browser × role × locale),
  cover every pair rather than every combination.
- Error guessing: after the systematic passes, add unicode input, double-submit,
  browser back after submit, expired session mid-flow, network drop, clock skew.

## Required coverage — do not stop before all of these are covered
- PRD §9: every BR- rule.
- PRD §10: every NFR-, with the measurable target stated in Expected Result.
- PRD §11: every AC-, matching the verification type in its Evidence column.
- Permissions Matrix: EVERY CELL of every role × permission grid.
  ✓ → a positive case. — → a denial case. C → denied-by-default, marked provisional.
  Then, per protected capability, also cover the seven cases named in its §9:
  allowed, denied, wrong-scope, deactivated-user, self-approval, stale-state,
  repeated-request.
  Also: for every control hidden by permission in the UI, a case that calls the
  endpoint DIRECTLY and asserts server-side denial — a hidden control is not an
  authorization control. And a case asserting scope applies to lists, searches,
  totals, exports, and notifications, not only detail views.
- Workflows: every normal flow; every status transition; every exception; and
  the three integrity rules per state-changing workflow (atomic, no duplicate on
  repeat, no silent overwrite on concurrent); plus §4.6's six validation
  failures, each asserting NO PARTIAL CHANGE.
- User Flows: every ◇ decision branch (both arms) and every ! recovery path.
  Apply the Shared Screen-State Matrix to every screen: Loading, Empty,
  Validation error, Permission denied, Stale/conflicting, Network failure,
  Action in progress, Completion uncertain, Success, Read-only.
  Every row of the Confirmation Dialog Matrix.
- Design System: token values as computed-style assertions; the 11 accessibility
  bullets in §9; error copy following "what happened → why → what to do next".
- Slice specs: the four acceptance examples verbatim; every Rules and Invariants
  entry; every row of Failure and Recovery States.

## Output format
Output ONE TSV block, tab-separated, with this exact header row:

Module (Slice)	Case ID	Requirement ID	Source	Test Type	Level	Title	Preconditions	Test Data	Steps	Expected Result	Must Not Happen	Technique	Priority	Automated	Automation Ref	Status	Last Run	Defect Ref	Evidence	Evidence Path	Notes

Formatting rules — violating these corrupts the paste:
- Separate columns with a REAL TAB character. Never a comma.
- NEVER put a newline inside a cell. Steps go on one line, numbered and
  separated by " → ", e.g.  1. Open /login → 2. Enter email → 3. Submit
- NEVER put a tab inside a cell.
- Case IDs sequential and zero-padded from TC-0001.
- Multiple requirement IDs in one cell separated by "; ".
- Use "—" for genuinely empty cells, never leave one blank.
- Status = "Not run", Last Run = "—", Defect Ref = "—" for all new cases.
- Evidence = "—" and Evidence Path = "—" for all new cases; these are filled in
  by the test run, not by you.
- Automated = "Planned" and Automation Ref = "—" unless the document names an
  existing test.

After the TSV block, output these three sections as plain markdown:

### AMBIGUITIES
Requirements too vague to test, one per line, each with the document and section
and a proposed concrete interpretation. Do not invent a threshold — propose one
and mark it as needing a decision.

### CONFLICTS
Any two documents that disagree. Quote both, with document and section.

### NOT COVERED
Anything in the required-coverage list above that you could not cover, and why
(missing document, section absent, behaviour unspecified). Be explicit — an
omission you don't declare will be read as covered.
````

### Using it well

- **Attach the documents; don't paste them.** Pasted text loses section numbering, which breaks the `Source` column.
- **Run it per slice, not for the whole product at once.** One slice plus the PRD, permissions matrix, and design system produces cases you can actually review. Whole-product runs produce volume and lose precision.
- **Read the three trailing sections first.** `NOT COVERED` and `CONFLICTS` are worth more than the rows — they're the findings a human has to act on.
- **Spot-check ten rows against the documents** before trusting the batch. Check specifically that the `Requirement ID` really says what the case claims: a fabricated-but-plausible trace is the failure mode to watch for.

---

## Round-tripping results back

After a run, update `Status`, `Last Run`, `Defect Ref`, `Evidence`, and `Evidence Path` in place — don't append new rows for re-runs, or the sheet doubles every cycle and `Case ID` stops being unique.

Evidence links are produced by the run, never by case generation: a screenshot is captured at the moment of failure, mirrored into the run folder, uploaded, and the link written into column `U`. Capture, naming, upload, and the `=HYPERLINK()` vs `=IMAGE()` decision: `evidence.md`.

The run also emits result files (see `results.md`). Keep the sheet as the case **register** and the result files as the run **record**: the sheet answers "what do we test", the files answer "what happened on 2026-08-14". Reconcile by `Case ID`.
