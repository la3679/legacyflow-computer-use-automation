# LegacyFlow evidence

All records and screenshots depict fictional training data. Input values are masked in screenshots and member identifiers are redacted before event persistence.

- `capabilities/open-savings-subaccount.v1.json`: reusable nine-step capability compiled from the real discovery below, with typed inputs, locator bundles, postconditions and output declarations.
- `discovery-success/`: genuine OpenAI API discovery using `gpt-5.6-terra`, run `5b5c2111c8754ea4b8c1a5b649ea0fa2`. The event stream contains the provider/model record and concise model action summaries; no raw model transcript or hidden reasoning is saved.
- `replay-success/`: the saved artifact replayed for a different synthetic member and a $250 deposit, with no planner in the replay execution path.
- `replay-member-not-found/`: the missing-member invocation returns `business_outcome` with `member_not_found`, rather than a software failure.

These runs used implementation commit `c85e3ba4f4d49cb726a567a12cd49ea5aac90242` on September 9, 2026. They stop at review without creating an account. The final screenshots were inspected and structured files scanned before committing.

Handoff and additional exceptional-state evidence are pending; the headed-browser integration tests currently exercise a clearly labeled simulated operator. This evidence set is not yet the complete submission.
