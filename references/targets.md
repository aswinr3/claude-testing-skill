# Targets — what you can reach, and what you can therefore claim

Two things vary independently: **is the source code available**, and **is a running instance reachable**. They produce four modes with very different capabilities, and the honest report differs in each.

Establish the mode in Orient, before planning anything.

```
Source present?          package.json / src/ / .git in the working directory
Runnable locally?        a dev/start script, or playwright.config webServer
Hosted URL given?        and which environment is it — local / dev / staging / prod
Credentials per role?    one account per role in PERMISSIONS_MATRIX §3.1
```

## Capability by mode

| | **A** Code + runnable | **B** Code only | **C** URL only | **D** Code + hosted URL |
|---|:--:|:--:|:--:|:--:|
| 1 Unit | ✅ | ✅ | ❌ | ✅ |
| 2 Integration | ✅ | ⚠️ needs test DB | ❌ | ✅ |
| 3 Mock | ✅ | ✅ | ⚠️ browser-side only | ✅ |
| 4 Smoke | ✅ | ❌ | ✅ | ✅ |
| 5 Sanity | ✅ | ⚠️ unit level | ✅ | ✅ |
| 6 Functional | ✅ | ❌ | ✅ | ✅ |
| 7 Regression | ✅ | ⚠️ unit/integration | ✅ | ✅ |
| 8 Exploratory | ✅ | ❌ | ✅ ⚠️ see safety | ✅ |
| 9 Non-functional | ✅ | ❌ | ✅ ⚠️ see safety | ✅ |
| Design conformance | ✅ | ❌ | ✅ | ✅ |
| UI audit | ✅ | ❌ | ✅ | ✅ |
| Coverage / mutation | ✅ | ✅ | ❌ | ✅ |
| Test review | ✅ | ✅ | ❌ | ✅ |
| **Root-cause attribution** | ✅ | ✅ | ❌ observe only | ✅ |

**The last row is the one that changes your report.** With source you write *"`auth/token.ts:12` uses 3600s, PRD §4.3 says 1800"*. Without it you can only write *"observed expiry at 60 minutes; PRD §4.3 specifies 30. Cause not determinable without source access."* Both are valid findings — but never write the first when you're in mode C.

---

## Mode C — hosted URL only (black box)

### Safety first — this is not optional

**Confirm you are authorised to test the URL before doing anything beyond loading a page.** Testing someone else's hosted application without permission is not a technical question. Ask, and get a clear answer, when the target isn't obviously the user's own.

Then classify the environment, because it caps what you may run:

| Environment | Permitted |
|---|---|
| local / dev | Everything |
| staging with disposable data | Everything, including exploratory and load |
| **production** | **Read-only smoke and observation only** |

Against production: **no load or stress testing** (you are DoSing your own service), **no exploratory testing** (its whole purpose is doing destructive and unexpected things), **no test-data creation** (you are polluting real records), **no destructive flows** (deletes, refunds, cancellations, bulk actions). If the only reachable instance is production, say so and scope the run to read-only checks rather than quietly running a full suite against live customers.

Also: throttle. A test suite hammering an endpoint looks exactly like an attack, and may trip WAF or rate limiting and give you false failures.

### Discovery — mapping an app you can't read

```ts
// Routes and structure
GET /robots.txt          → disallowed paths often reveal admin/internal routes
GET /sitemap.xml         → the public route inventory
GET /openapi.json  /swagger.json  /api-docs  /v3/api-docs   → the API contract, if exposed
```

Then from the running app:

- **Crawl internal links** from the entry point to build the route list, and reconcile it against `USER_FLOWS §6` primary navigation. A route in the docs but not the app is *not implemented*; a route in the app but not the docs is an *orphan* and worth asking about.
- **Watch the network** (`browser_network_requests`, or `page.on('response')`) while walking flows — this discovers the real API surface, including endpoints no document mentions.
- **Source maps.** If `.js.map` files are served, the original module structure is recoverable — which upgrades some of mode C toward mode B. Two notes: their presence in production is itself a finding worth reporting, and only do this against an app you're authorised to test.
- **Framework fingerprint** — response headers, `__NEXT_DATA__`, build manifests. Tells you what conventions to expect and which Context7 docs to pull.

### What you can still verify — most of it

Everything in `ui-audit.md` works black-box: overflow, clipping, overlap, touch targets, contrast and axe rules, console errors, failed requests, focus visibility, the ten screen states, responsive behaviour at every breakpoint.

`design-conformance.md` works too — token extraction reads computed styles from the live DOM, so spec-vs-app and design-file-vs-app both run without source.

Authorization testing works **if you have one account per role**. This is the thing to ask for first: without it you're limited to "unauthenticated cannot reach protected routes", which is worth checking but is a fraction of `PERMISSIONS_MATRIX`. With two accounts you can already test IDOR — the highest-value authz check.

Contract testing works if an OpenAPI spec is reachable or supplied.

### What you genuinely cannot do

Unit tests, integration tests, coverage, mutation score, test-suite review, internal dependency mocking, database state verification, and root-cause attribution. **Report these as `Not run — no source access`, never as passing and never omitted.** A summary showing seven green types and two absent reads as "mostly fine"; the same summary with two explicit `Not run — no source access` rows reads correctly.

One partial: mock testing still works at the browser boundary — `page.route` can fake what the *frontend* receives, so frontend failure-state handling is testable. Backend dependency-failure behaviour is not.

---

## Mode B — code only, can't run

Usually a missing service, database, or credential. Say which, since it's often a five-minute fix that unlocks modes A/D.

Meanwhile, genuinely useful work:

- **Unit tests run** — often the whole suite, if it doesn't need infrastructure.
- **Test review** (`review.md`) — audit the existing suite for tests that can't fail, weak assertions, flake sources. This is high value and needs nothing running.
- **Static traceability** — read the source and map requirements to implementations. You can find `BR-` rules with no corresponding code (*not implemented*) and code contradicting a document (*drift*) by reading. You just can't confirm runtime behaviour.
- **Mutation testing** on the modules whose tests do run.

Everything from smoke onward is blocked. Report those types `Not run — application could not be started: <reason>`.

---

## Mode D — code plus a hosted URL

The strongest position, and the one to ask for. Run unit, integration, mutation, and coverage against the source; smoke through non-functional against the deployment.

The discipline that matters here: **know which artefact you tested.** A deployed URL can be several commits behind your checkout, so a "drift" finding may just be a stale deployment.

Pin it in every result file:

```
Source:      commit a91f2c3, branch release/1.4
Deployment:  https://staging.example.com  ·  build 1.4.0-rc2  ·  commit a91f2c3
```

If the deployment doesn't expose a build/commit identifier, say so — and consider it a finding of its own, since it makes every future result ambiguous. A `/health` or `/version` endpoint returning the commit is cheap and removes a whole class of wasted debugging.

---

## Report the mode explicitly

In `00-SUMMARY.md`, above the per-type table:

```markdown
**Target mode:** C — hosted URL, no source access
**URL:** https://staging.example.com (staging, disposable data — full suite authorised)
**Credentials:** admin@test.local, operator@test.local. No viewer account provided.
**Build identifier:** not exposed by the deployment.

**Consequently not run:** unit, integration, coverage, mutation, test review.
**Consequently limited:** authorization (2 of 4 roles available — viewer and
auditor rows of the permissions matrix are unverified); root causes are observed
symptoms only, not located in source.
```

That block is what stops a partial run being read as a full one. Access limits and passing tests are different things, and the summary has to distinguish them — a reader who can't tell the difference will draw the wrong conclusion about release readiness.
