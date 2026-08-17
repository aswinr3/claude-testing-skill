# MCP tooling — what each one is for

Two servers materially improve this skill. They do **different** jobs, and using either for the other's job makes output worse, not better.

| Job | Use | Not |
|---|---|---|
| Explore the running app, discover flows and selectors, reproduce a bug, drive exploratory testing | **Playwright MCP** | the committed test suite |
| Get current, version-correct API docs before writing test code | **Context7** | runtime behaviour |
| Run the regression suite in CI, in parallel, deterministically | **`npx playwright test`** | an MCP server |

---

## Playwright MCP

```bash
claude mcp add playwright -- npx @playwright/mcp@latest
```

```json
{ "mcpServers": { "playwright": { "command": "npx", "args": ["@playwright/mcp@latest"] } } }
```

It drives a real browser through **Playwright's accessibility tree**, not screenshots — so element identification is deterministic and needs no vision model. `browser_snapshot` returns a structured semantic snapshot with stable refs you act on.

### The rule that keeps this useful

**Playwright MCP is for interactive work. It is never the test runner.**

The committed suite must run as `npx playwright test` — parallel, deterministic, no model in the loop, runnable in CI by someone who isn't you. Driving tests through MCP instead would be slow, nondeterministic, expensive per run, and impossible to run on a merge. Anything MCP discovers gets **written down as a spec file** and from then on runs headless.

Think of MCP as the hands you use while writing the tests, and `playwright test` as what ships.

### Where it earns its place, by mode

**Exploratory (type 8) — the biggest win.** This is the one mode that cannot be scripted, and until now the skill could only tell you to do it by hand. With MCP, Claude can actually run a charter: navigate, try edge inputs, hit back mid-flow, double-submit, and follow what looks wrong. Findings then become permanent functional and regression cases.

**Authoring.** Explore the real app to discover routes, roles, accessible names and real selectors, then write the spec. Tests written from a live snapshot beat tests written from a guess about the DOM — this alone removes most first-run selector churn.

**Triage.** Reproduce a failing case step by step and inspect state at the moment it breaks, instead of re-running the whole suite blind.

**Design conformance and UI audit.** `browser_evaluate` runs the token-extraction and DOM-sweep snippets from `design-conformance.md` and `ui-audit.md` **interactively**, so you can iterate on a check before committing it.

### Tool → task map

| Tool | Use in this skill |
|---|---|
| `browser_snapshot` | Accessibility snapshot — the primary way to see the page. Doubles as a free a11y smell test |
| `browser_navigate`, `browser_navigate_back` | Walk `USER_FLOWS` routes; back-button recovery cases |
| `browser_click`, `browser_type`, `browser_fill_form`, `browser_select_option`, `browser_press_key` | Drive flows; `browser_press_key` for keyboard-only accessibility paths |
| `browser_find` | Locate an element without guessing a selector |
| `browser_evaluate` | Run the UI-audit sweep and token extraction live |
| `browser_console_messages` | Console errors — a UI-audit signal that's invisible in a screenshot |
| `browser_network_requests`, `browser_network_request` | Verify request payloads; catch 4xx/5xx behind a friendly UI |
| `browser_route`, `browser_unroute`, `browser_network_state_set` | **Mock mode (type 3) interactively** — inject 500s, timeouts, offline, and watch the real failure behaviour |
| `browser_resize` | Walk the `DESIGN_SYSTEM §4` breakpoint table, including one pixel either side |
| `browser_highlight`, `browser_take_screenshot` | **Evidence capture** — highlight the offending element, then shoot. Same result as the `captureIssue()` helper in `evidence.md`, without writing code first |
| `browser_start_tracing` / `browser_stop_tracing` | Trace an exploratory session for the defect report |
| `browser_handle_dialog` | Confirmation-dialog matrix cases |
| `browser_cookie_*`, `browser_localstorage_*`, `browser_storage_state` | Role switching; expired-session and stale-auth cases |
| `browser_file_upload` | Upload flows |
| `browser_tabs` | Multi-tab and cross-tab state cases |

Useful flags: `--isolated` (fresh profile per session — use this for test runs so state never leaks between charters), `--device "iPhone 15"` or `--mobile` for responsive work, `--storage-state` to start authenticated, `--caps` to opt into `vision`, `devtools`, `network`, `storage`, `testing`.

### Two cautions

- **`browser_run_code_unsafe` executes arbitrary code in the browser context.** Don't enable it against anything but a local or throwaway environment, and never against production or a database with real customer data.
- **Never point exploratory MCP sessions at production.** Exploratory testing deliberately does destructive and weird things — that's the point. Use a seeded staging environment with disposable data.

---

## Context7

```bash
npx ctx7 setup --claude
```

Manual: remote HTTP server at `https://mcp.context7.com/mcp`, API key via an `Authorization: Bearer <key>` header.

Tools: **`resolve-library-id`** (library name → Context7 library ID) and **`query-docs`** (library ID + query → current docs). Invoke by adding **`use context7`** to the prompt, or name the library directly: `use library /microsoft/playwright for API docs`.

### Why this specific skill needs it

Test tooling APIs move, and stale API knowledge produces code that looks right and fails. Three real examples already in this skill's history:

- `toMatchSnapshot` vs `toHaveScreenshot` for visual comparison — different APIs, different options, and `threshold` means something different from `maxDiffPixelRatio`.
- `page.clock` for freezing time, which is newer than most training data.
- The Anthropic SDK snippet you brought over used a **retired** model ID that now 404s, plus `response.content[0].text`, which doesn't type-check against the content-block union.

Context7 prevents that class of error at the source. **Invoke it before writing test code against any of:** Playwright, Vitest/Jest, Testing Library, axe-core, and whatever framework the app under test uses.

Worth knowing: it also covers the *app's* libraries, not just the test tools. When you're testing a component built on a UI library, current docs for that library tell you the real accessible roles and props — which is exactly what your locators need.

Cost note: it consumes context. Query it for the specific API you're about to use, not "everything about Playwright".

---

## Others worth evaluating

| Server | Adds | Consider when |
|---|---|---|
| **Chrome DevTools MCP** | Real performance traces, CPU/network throttling, Core Web Vitals from the actual devtools protocol | You're testing `NFR-01`-style performance budgets. More accurate for perf than Playwright MCP; the two are complementary, not competing |
| **GitHub MCP** | File each entry in `defects.md` as an issue; link cases to PRs; read CI results | Your repo is on GitHub — closes the loop from finding to ticket |
| **Sentry (or equivalent) MCP** | Correlate a test failure with production errors | You run Sentry — turns "this test is flaky" into "this is a real race that also fires in prod 40×/day" |

**The gap worth closing:** you have Google **Drive** connected, but not **Sheets**. That's why `test-cases-sheet.md` emits TSV for you to paste rather than writing cells directly. A Sheets MCP would let a run update `Status` / `Last Run` / `Defect Ref` / `Evidence` in place — which is the step most likely to be skipped when it's manual, and the one that makes the sheet go stale. Worth adding if one is available to you; the TSV path stays as the fallback.

I can't install any of these myself — MCP setup needs `claude mcp add` or `/mcp` in an interactive session, and remote servers need you to authorise them.

---

## Putting it together — a run with all three

```
1. Context7      → current Playwright + axe API before writing anything
2. Read docs     → requirements and cases  (document-map.md, documents.md)
3. Playwright MCP → explore the live app: confirm routes, roles, selectors,
                    real screen states; run an exploratory charter
4. Write specs   → committed .spec.ts files from what step 3 found
5. playwright test → the actual run: parallel, deterministic, in CI
6. Playwright MCP → triage each failure interactively; highlight + screenshot
                    the offending element for evidence
7. Result files  → test-results/<date>-<time>/ per test type   (results.md)
8. TSV → Sheets  → statuses and evidence links           (test-cases-sheet.md)
```

Steps 3 and 6 are where MCP belongs. Step 5 is where it must not be.
