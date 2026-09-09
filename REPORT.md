# 1. Architecture

LegacyFlow separates exploration from execution. Discovery accepts a natural-language goal and named inputs, observes a live synthetic servicing UI, and asks OpenAI for one schema-validated decision at a time. Successful actions and verified postconditions are compiled into a capability. Replay consumes that capability and fresh inputs without importing the planner. The goal ends at account review; account creation is deliberately protected.

Python keeps the contracts, asynchronous runners, and tests in one language. FastAPI and Jinja produce realistic server-rendered transitions without a frontend build system. Playwright supplies browser lifecycle, semantic locators, explicit assertions, and a headed session a person can operate. `ComputerSurface` defines observation, action execution, verification, reading, and screenshot operations; the engine speaks these concepts rather than Playwright code.

Both runners use the same guarded surface, policy, outcome classification, and evidence boundaries. The OpenAI dependency is optional and loaded only on the discovery path. CI also installs the project without that extra and proves CLI replay from a clean directory without credentials. This is a small state machine, so an orchestration framework or distributed service would obscure rather than strengthen its boundaries.

# 2. Artifact schema

Pydantic rejects unknown fields, invalid action shapes, unknown input references, duplicate step IDs, and unsupported schema versions. Schema version `1.0` is distinct from the capability's semantic version. The artifact contains identity, purpose, application/vendor/variant metadata, typed inputs and outputs, ordered steps, risks, a final checkpoint, and the discovery run ID. The genuine example has nine steps; it is independently reviewable JSON, not a model transcript.

Form typing must reference an input by name. Member IDs are marked sensitive, validated in memory, and redacted before evidence persistence. Deposit values are finite positive decimals up to 100000 with at most two fractional places. Validation runs before discovery actions and replay navigation. Output declarations carry types and locator targets; the extracted deposit must equal the caller's input.

Targets hold ordered role/name, label, text, and stable-attribute strategies, with optional frame and region scopes. Discovery captures characteristics of controls it actually used. Postconditions verify field contents or transition headings; final review is asserted explicitly. Metadata describes the supported base web variant of the demo's 1.x application family. Unsupported variants, vendor families, and application identity/version drift fail conservatively.

# 3. Determinism & error handling

Replay has no planner or OpenAI dependency. Each step substitutes parameters, checks policy, resolves a visible unique target in declared order, executes, classifies state, and verifies its postcondition. An ambiguous match fails rather than choosing an arbitrary element. Playwright navigation completion and explicit assertions provide waits; the known slow demo response does not require a replay sleep. Target resolution is bounded by the finite locator list and action/run deadlines, not an open-ended repair loop.

`member_not_found` is a business outcome with exit code 0. A known System Notice gets exactly one approved dismissal and re-observation per transition. Permission denial, expired session, unknown modal without an operator, missing/ambiguous targets, incompatible artifacts, and failed checkpoints return typed failures. Failure records include capability identity/version, run ID, step ID, expected/observed context, and a screenshot when capture remains possible. Operator abort is a separate status. Raw browser and API exception bodies are not persisted.

Discovery additionally bounds model decisions, elapsed time, and repeated identical actions. The final heading and typed outputs must be verified before it saves an artifact. Tests cover mismatched amounts, wrong checkpoints, invalid inputs before any model decision, recovery, permission failure, and zero Python HTTP/SDK traffic during replay. Determinism means the artifact and explicit state rules govern decisions; browser timing and generated run IDs naturally vary.

# 4. Heterogeneity & multi-tenant

The current implementation supports one synthetic web application. Surface-neutral actions and target descriptors leave room for a Windows UI Automation or accessibility adapter mapping roles, labels, fields, and checkpoints onto desktop controls. Named-frame and region scopes offer a seam for legacy framed web applications; the demo includes a training-notice iframe. Screenshot/coordinate targeting is not implemented and would require explicit confidence and drift checks.

A future deployment would retain a vendor-level canonical capability and apply reviewed tenant/version overlays to locator bundles and entry routes. An overlay should never silently loosen policy. Application/version checks and replay checkpoint failures would mark a variant degraded and route it for review or fresh discovery. A reviewed artifact version would then be promoted explicitly. This repository rejects unsupported variants; it does not pretend to provide tenant isolation, overlay storage, or an artifact registry.

# 5. Escalation & handoff

Unknown modal state or a discovery escalation can request intervention. The manager records the run, step, reason, expected heading, screenshot, ownership, and session correlation ID in timestamped evidence. It pauses automation and exposes Take Control, Resume, and Abort through a loopback operator page. A single owner guards surface operations, preventing automation from competing with operator input.

The original headed Playwright page and browser context remain live. During operator control, fixed event handlers record clicks, navigation, and input occurrence without input values. Resume transfers ownership back, re-observes, and requires the original session ID, expected heading, and no remaining blocking message. A wrong seam, timeout, or abort terminates safely. The seam checks screen state, not a complete semantic diff of all human changes; stronger production workflows would verify selected member and business invariants too.

Committed evidence exercises the actual operator web controls with an explicitly labeled automated demonstrator, and asserts page/context object identity across handoff. It proves the mechanism, not that a person performed the recorded run. Integration tests separately cover abort, invalid resume, and blocked cross-origin requests. The README provides the exact path for a person to operate the same session.

# 6. Safety

The browser adapter enforces origin/route allowlists, permitted action types, target-name risk checks, and destination checks before execution. Browser requests are intercepted, service workers are disabled, and downloads are not accepted. Create Account is blocked by both risk name and its excluded route; a demonstration appends that attempted action and records the rejection while the screen remains at review. The normal workflow does not cross an irreversible boundary.

Central redaction runs before JSON/JSONL persistence and CLI result printing. It handles sensitive dictionary keys, known invocation values, API-key patterns, bearer strings, credential assignments, and authorization/cookie headers. Screenshots mask input and textarea elements; fictional output names and amounts remain visible. The operator recorder omits typed values. API errors become bounded safe error codes, and the local `.env` and runtime directories stay untracked. Discovery sends the synthetic goal, named inputs, and compact observation to OpenAI; evidence retains only concise action summaries, never hidden reasoning.

These controls are suitable for a local synthetic demonstration, not a universal data-loss prevention system. Arbitrary PII in unrecognized free text or screenshots is not guaranteed to be detected. Operator control is trusted, policy files and artifacts require review, and the demo has no production authentication or durable financial effects. Real records, public operator hosting, and arbitrary target websites would require a separate security design.

# 7. Cuts

The project deliberately omits remote co-browsing/streaming, a desktop adapter, production multi-tenancy, distributed queues, an artifact registry, production authentication, and LLM-driven replay recovery. It also omits automatic locator repair and coordinate fallback: a deterministic failure with evidence is preferable to an unreviewed behavioral change. The server-rendered UI and one complete savings-to-review capability keep the assignment inspectable.

Next work would strengthen resume invariants around selected member and form state, add reviewed variant overlays with replay health tracking, and introduce a second real surface to test whether the adapter contract generalizes. None of those extensions is represented as implemented here.
