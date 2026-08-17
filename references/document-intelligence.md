# Document intelligence — reading a project's documents properly

The single most expensive failure in document-driven QA is reporting **"not specified"**
about something that *was* specified, three sections further down a file you skimmed. The
second most expensive is treating two documents that disagree as one document.

This file is the deep-reading pass. `document-map.md` tells you which document holds what
when the standard template set is in use; `documents.md` is the generic fallback. **This
file tells you how to actually comprehend them** — and it runs *before* a single case is
written.

Five passes, in order. Do not start pass N+1 with pass N incomplete.

---

## Pass 1 — Inventory and pin

Produce a table before reading anything in depth. You cannot reason about coverage of a
corpus you have not enumerated.

| Document | Path | Version | Lines | Last change |
|---|---|---|---|---|
| PRD | `docs/PRD.md` | v2.3 | 412 | `a91f2c3`, 6 days ago |
| Slice 04 — Checkout | `docs/slices/04-checkout.md` | v1.1 | 168 | `4b0e1de`, 2 days ago |
| Permissions matrix | `docs/PERMISSIONS.md` | v1.1 | 96 | `77c9a01`, 3 weeks ago |

Three rules that decide whether the rest of the run is sound:

1. **Enumerate from the filesystem *and* from git.** A document deleted last week is still
   the spec the deployed build was written against:
   ```bash
   git ls-tree -r --name-only HEAD | grep -iE '\.(md|pdf|docx)$'
   git log --diff-filter=D --name-only --pretty=format: | sort -u   # deleted docs
   ```
   Never conclude a document is missing until both have been checked.

2. **Pin the revision.** Record the commit each document was read at. Documents change
   mid-run; a finding traced to "the PRD" is worthless if nobody can say which PRD. If a
   document changes while you are testing, say so in the run record and re-read the changed
   sections — do not silently mix two revisions.

3. **Record the version marker, or its absence.** "No version marker" is itself a finding
   worth reporting, because it means drift cannot be attributed later.

---

## Pass 2 — Structural read, one document class at a time

**Read every document completely.** Not the summary, not the acceptance-criteria section,
not the parts that look relevant. Requirements hide in prose, in table footnotes, in a
parenthetical inside a user flow, and in the one bullet under a heading named "Notes".

A **skipped section becomes a missed requirement**, and a missed requirement becomes a
confident "not specified" in your report that is simply wrong. That is the most expensive
error in this whole process, and it is caused entirely by reading selectively.

For each document, extract into a normalised shape rather than reading for gist:

### PRD
Business rules, states and transitions, permitted values, thresholds, error copy, and
non-functional targets. Every sentence containing **must / must not / shall / always /
never / only / at most / at least / within** is a candidate requirement — grep for them
after reading, as a net, not as a substitute for reading.

### Vertical slice specs — the primary source
A slice is the unit a team owns and ships. From each, extract:

- **Routes and screens** it introduces or changes
- **Acceptance examples** — usually four; these are near-ready test cases
- **Required evidence** — the artefacts the slice demands before it can be called done.
  This list is the slice's real exit criterion and it is the part everyone skips.
- **Dependencies** on other slices, and what is stubbed until those land
- **Out of scope** — as load-bearing as the in-scope list, because it tells you what a
  "missing" feature is *not* a defect for

### Permissions matrix — mine it hard
Every cell is two cases, not one: the permitted actor **succeeds**, and every other actor
**is refused by the server**. A matrix of 6 roles × 12 actions is 144 assertions, and it is
the highest-yield document in the set because authorization defects are silent.

### Workflows and user flows
State machines in prose. Extract states, transitions, guards, and — the part that produces
real defects — the transitions that are *not* drawn: what happens on back-navigation, on
refresh mid-flow, on a double submit, on an expired session at step 3.

### Design system
Tokens (colour, spacing, type scale, radius, elevation), component variants, and the states
each component must implement. Feeds `design-conformance.md` and the token checks in
`ui-audit.md`.

### Data model
Entities, cardinality, nullability, uniqueness, cascade behaviour, and enumerations. These
convert directly into boundary and negative cases, and into the integrity checks a UI test
will never reach.

### Architecture and ADRs
Seams — where integration tests belong — plus the decisions that explain why something that
looks wrong is deliberate. An ADR saying "we accept eventual consistency here" turns a bug
report into a documented trade-off.

### Glossary
Read it first if it exists. Testing the wrong meaning of a domain term produces confident,
wrong findings.

---

## Pass 3 — Build the requirement index

The output of reading is not understanding in your head; it is a **machine-readable index**
that every later artefact joins against.

One row per requirement, with an anchor back to its source so any finding can be audited:

```tsv
ID	Requirement	Source	Anchor	Type	Priority	Status
PRD:BR-03	Discount codes are single-use per account	docs/PRD.md	L142	rule	high	approved
PRD:BR-04	Expired codes are rejected with COD_EXPIRED	docs/PRD.md	L147	rule	high	approved
SLICE-04:S04-02	Checkout shows tax before payment	docs/slices/04-checkout.md	L61	acceptance	high	approved
PERM:P-17	Only owner may delete an organisation	docs/PERMISSIONS.md	R9C4	permission	high	approved
PRD:Q-08	Refund window length	docs/PRD.md	L233	open	—	provisional
```

Rules for the index:

- **Namespace every ID.** The templates reuse `D-` for two different things; a bare ID
  corrupts traceability the moment two documents are in play. `PRD:`, `SLICE-04:`, `PERM:`,
  `FLOW:`, `DM:`.
- **Anchor to a line or cell**, not to a document. "It's in the PRD" is not auditable.
- **Mark derivation.** A requirement you inferred from a diagram is `derived`, not
  `approved`. Label it and say what you inferred it from — an inferred requirement that
  turns out to be wrong must be traceable to your inference, not to the document.
- **Mark open decisions `provisional`.** Anything carrying `Q-`, `PM-`, `UX-`, `DS-`, `DM-`,
  `S[NN]-` is not an approved requirement. Test the safe default if useful; never let it
  gate acceptance.

This index is what `conformance-matrix.md` joins against, and what makes "83% of documented
requirements are exercised" a computed number rather than a feeling.

---

## Pass 4 — Reconcile across documents

Documents are written at different times by different people. Reconciliation is where the
real findings come from, and it is the pass most runs skip entirely.

Four checks, run across the whole index:

| Check | What you are looking for | Outcome |
|---|---|---|
| **Contradiction** | Two documents state incompatible rules for the same behaviour | `CONFLICT` — report both, with anchors. **Never pick a winner.** |
| **Duplication** | The same rule in two places with different wording | Link the IDs; test once; note that a future edit must touch both |
| **Orphan** | A slice route, screen, or endpoint no requirement covers | `GAP — unspecified`; ask, or test the self-evident oracle and label it |
| **Silence** | A requirement with no implementing slice | `NOT IMPLEMENTED` or a planning gap — distinguish them before reporting |

On precedence: **do not invent one.** If the project states an authority order (slice spec
over PRD, ADR over both), follow it and cite it. If it does not, a contradiction is a finding
for a human — the code may be right, the doc may be stale, and choosing silently is how a
test suite ends up enshrining a bug.

---

## Pass 5 — Coverage self-check

Before writing a case, prove the reading was complete. Answer these in the run record:

- [ ] Every document in the pass-1 table read **end to end**, with the revision recorded
- [ ] Every `## ` section of every document accounted for: yielded requirements, or
      explicitly classified as non-testable (repository conventions, rationale, changelog)
- [ ] Every slice has a module entry — **including slices with no cases**, which are
      recorded as `Not tested — <reason>` rather than omitted
- [ ] Every permissions-matrix cell expanded into a permitted case and a refused case
- [ ] Every acceptance example in every slice mapped to a case ID or to a stated reason it
      cannot be automated
- [ ] Every `CONFLICT`, `GAP`, and `provisional` item listed in the summary, not buried

A "not specified" claim in a report is only credible if this checklist is complete. Say so
explicitly: *"§§ Structure, README, Code are repository conventions, not runtime-testable."*

---

## What not to do

- **Do not summarise a document instead of extracting from it.** A summary loses exactly
  the thresholds and permitted values that make cases concrete.
- **Do not infer product decisions.** Wording, thresholds, and permitted values come from
  the spec. Self-evident oracles (a wrong password must not grant a session; an
  unauthenticated call must be denied) are fair game and are labelled as such.
- **Do not treat an absent document as an absent requirement.** Check git history, ask, and
  record `Specification unavailable` as a dependency — not as "nothing was required".
- **Do not let the index drift from the documents.** If you re-read at a new revision,
  re-emit the index. A stale index silently mistraces every finding built on it.
