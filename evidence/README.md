# LegacyFlow evidence

All records and screenshots depict fictional training data. Input values are masked in screenshots and member identifiers are redacted before event persistence.

See [submission validation](validation.md) for the clean-install, test, no-OpenAI replay, and hygiene audit results.

- `capabilities/open-savings-subaccount.v1.json`: reusable nine-step capability compiled from the real discovery below, with typed inputs, locator bundles, postconditions and output declarations.
- `discovery-success/`: genuine OpenAI API discovery using `gpt-5.6-terra`, run `5b5c2111c8754ea4b8c1a5b649ea0fa2`. The event stream contains the provider/model record and concise model action summaries; no raw model transcript or hidden reasoning is saved.
- `replay-success/`: the saved artifact replayed for a different synthetic member and a $250 deposit, with no planner in the replay execution path.
- `replay-member-not-found/`: the missing-member invocation returns `business_outcome` with `member_not_found`, rather than a software failure.

These runs used implementation commit `c85e3ba4f4d49cb726a567a12cd49ea5aac90242` on September 9, 2026. They stop at review without creating an account. The final screenshots were inspected and structured files scanned before committing.

Additional demonstrations used implementation commit `235d87d` on September 9, 2026, through `scripts/record_evidence.py`:

- `handoff-demo/`: headed replay pauses at Supervisor Confirmation. The actual operator web page receives Take Control and Resume clicks. The same target `Page` and `BrowserContext` are preserved and asserted by identity. `human_action` records explicitly identify the actor as `automated_demonstrator`; **no person is claimed to have performed this demonstration**. Compare `before-handoff.png`, `operator-console.png`, `after-resume.png`, and `final-screenshot.png`. The session correlation ID remains identical across pause, ownership, action, and resume events; it is a generated diagnostic ID, not an authentication token.
- `replay-notice/`: one logged deterministic notice recovery followed by successful review.
- `replay-permission-denied/`: `PERMISSION_DENIED` with step context and a failure screenshot.
- `policy-blocked/`: the demonstration appends a Create Account attempt to an in-memory artifact copy. Policy blocks it before execution; the screenshot still shows Review New Account. The committed reusable artifact is unchanged.

Structured files were parsed and scanned for credential patterns and unredacted member identifiers; all seven additional screenshots were visually inspected. To reproduce these four demonstrations with the demo server running, use `python scripts/record_evidence.py` in the installed environment. It writes fresh ignored `runs/` directories and never overwrites committed evidence. Use the README's `--operator` command for a person to operate the same headed session.
