# UI-audit eval

Scores the deterministic sweep in `references/ui-audit.md` against two fixtures.

- **GOOD** — correct markup carrying 15 shapes that classically trip naive sweeps:
  `overflow: visible` text, an ellipsized cell, a `visibility: hidden` drawer over content,
  an inline link in a sentence, a `pointer-events: none` decorative overlay, an
  `overflow: auto` scroller, a label-wrapped 20px checkbox, an `aria-label`-only input, an
  icon button named by `aria-label`, white-on-black text, text over a gradient (contrast is
  *unknowable* there, so it must be skipped rather than guessed), a properly labelled
  `<select>` whose option text must not be mistaken for a name, and unique ids.
  **Any finding here is a false positive.**

- **BAD** — 13 seeded defects: clipped text with no affordance (D1), a link under an opaque
  div (D2), a 16px standalone button (D3), a 404 image (D4), an image with no alt (D5), a
  button under a fully transparent overlay (D6), an unlabelled text input (D7), a duplicate
  id (D8), a 2200px element forcing horizontal page scroll (D9), 2.8:1 grey-on-white text
  (D10), an empty button (D11), an unlabelled `<select>` (D12), and a placeholder-only
  input (D13). **Any miss is a false negative.**

## Run

From any project with `@playwright/test` installed:

    node evals/ui-audit/harness.mjs

## Scores

| Version | Rule families | Precision | Recall | Notes |
|---|---:|---|---|---|
| v1 — originally shipped | 5 | 0.50 | 0.31 | invented overlaps between hidden elements; missed both occlusions and every a11y-shaped defect |
| v4 — current | 10 | **1.00** | **1.00** | overflow-gated clipping, hit-test occlusion, SC 2.5.8 exceptions, accessible-name computation, duplicate ids, page overflow, gated contrast |

## The rule that keeps precision where it is

**Every false positive a real run produces becomes a new GOOD-fixture shape; every false
negative becomes a new BAD defect.** Two of the current shapes came from a live run against
`saucedemo.com`:

- an unlabelled `<select>` was *missed*, because the name computation wrongly accepted the
  control's own `textContent` — which for a `<select>` is its option list. Now `INPUT`,
  `SELECT`, and `TEXTAREA` never use `textContent` as a name → **D12**.
- placeholder-only inputs were *falsely* reported as having no accessible name. Per HTML-AAM
  a `placeholder` **is** part of the name computation, so this became its own rule,
  `placeholder-as-only-label`, rather than a missing-name error → **D13**.

Re-run this before trusting any run's UI findings, and after any edit to the sweep. CI fails
the build if precision or recall drops below 1.00.
