# Submission validation

Validated on September 9, 2026. Runtime revision: `4d33f5c`.

| Check | Result |
| --- | --- |
| Fresh remote clone, Python 3.13.14, locked all-extras install | Passed |
| Chromium install and installed CLI version command | Passed |
| Full test suite in the fresh clone, run serially | 42 passed |
| Ruff lint and formatting, including demonstration scripts | Passed |
| Strict mypy | Passed, 25 source files |
| Separate replay-only install, Python 3.14.7 | Success and member-not-found passed with OpenAI absent |
| CLI replay from a temporary directory without `.env` or API credentials | Passed |
| README genuine OpenAI discovery command | Success; eight verified actions, correct review outputs |
| README successful replay, missing member, notice, permission commands | Expected statuses and exit codes |
| Exact headed/operator CLI and Take Control / Abort | Passed |
| Same-session Resume through operator web controls | Passed; committed handoff evidence uses a labeled automated actor |
| Structured evidence and artifact consistency tests | Passed |
| Credential-pattern scan of tracked files and historical text blobs | No credentials found |
| Development metadata and local environment tracked-file audit | No private development files tracked |
| Report headings and local documentation links | Passed |

The fresh live discovery verification run was `b20cb96266264a3dac139c5b13239849`. The committed genuine discovery remains `5b5c2111c8754ea4b8c1a5b649ea0fa2`, preserving the nine-step artifact and its original provenance. New discovery runs need not choose identical actions. See [the evidence guide](README.md) for committed run details and source revisions.

The replay-only proof has no SDK available to call. The integration suite additionally rejects planner imports and Python HTTP requests during replay. Linux CI independently runs both the full offline suite and a fresh replay-only installation; live discovery is not part of CI.

One initial navigation exceeded the 5-second timeout during an earlier local audit with concurrent browser workloads. That test passed in isolation and the subsequent complete serial suite passed. A subsequent Linux CI run also exceeded that budget while waiting for a headed Search button to stabilize. The default action timeout was therefore raised to a bounded 15 seconds; the 180-second run deadline and explicit short negative-test deadlines remain unchanged. The suite emits one upstream Starlette/AnyIO deprecation warning. These observations are retained rather than represented as application failures or silently omitted.

The credential audit scans without printing candidate values. Broad matches were limited to the blank environment example, redaction patterns, and deliberately synthetic test fixtures. Screenshots were visually inspected; all depicted records are fictional. This verifies the committed demonstration, not arbitrary real-data redaction.
