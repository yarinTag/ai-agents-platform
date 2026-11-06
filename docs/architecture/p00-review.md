# P00 review bundle — AI-13, AI-14 and AI-15

Status: completed planning artifacts / ready for implementation review; not deployed features.
[AI-13](https://trello.com/c/SZTb19BB) · [AI-14](https://trello.com/c/EFq5kgnT) ·
[AI-15](https://trello.com/c/piRgSBUJ). Overall epic: [AI-12](https://trello.com/c/HqVN3GDu).

## Review deliverables

| Ticket | Concrete output | Boundary |
|---|---|---|
| AI-13 | [Source audit and proposed shared contract](connector-governance-contract.md), [executed API baseline](ai-13-api-audit.md) | Current versus partial/missing, no new production policy |
| AI-14 | [UX/role journeys](../design/governance-ux.md), [wireframe PNG](../design/governance-wireframes.png), [editable SVG](../design/governance-wireframes.svg) | Static proposed UI, no browser/app changes |
| AI-15 | [Architecture decision record](adr-ai-15-generic-connector-governance.md), owning module AGENTS.md/CLAUDE.md guidance | Shared engine/adapter/authority/approval boundaries and release gates |

The target is reusable connector governance, not a Dependabot-only engine. Illustrative CRM,
Tracker and PR actions require real trusted adapters; adding an integration name is not enough.
No current schema, grants, runtime prompt, saved workflow, webhook or provider configuration
was changed by AI-14/AI-15. Upcoming P01 implementation must publish exact API/schema contracts
before FE wiring and preserve current denials/receipt history.

## Verification

On 2026-11-06 the existing isolated API audit passed **39 tests, 0 failures, 6 existing
library deprecation warnings, 14.42 seconds** after the P00 document/guide work. Command:

```sh
rtk proxy python3 poc/tests/run_api_audit.py \
  --report-dir /private/tmp/ai14-ai15-api-regression-2026-11-06
```

Report files: `api-audit.xml`, `api-audit.log`, `api-audit-summary.json` in that external
report directory. FastAPI/SQLite are real; the runtime capability is disabled and the
interpreter guard rejects network/DNS and child processes. Only static agent ownership
records exist. No agents/models/provider writes, live sends, app startup or UI/browser
runtime verification occurred. Tests verify current HTTP contracts, not proposed capabilities.

Static relative links and SVG structure were checked. The four-screen PNG was visually
inspected for readable layout, correct existing theme and prominent proposed/static labels.
That is documentation review, not a UI accessibility/RTL/rendering test. Those acceptance
journeys are assigned to the later implementing FE tickets.

## Next implementation milestone

P01 / AI-16 (BE), AI-17 (FE), AI-18 (DOC): typed/versioned action/resource policy and trusted
capability descriptors, with real API role/tenant/revocation/unknown-capability tests.
Do not expose planned channel triggers, channel-native approvals or resumable middle-DAG
gates until their owning P04–P08 identity/ingress/checkpoint work is implemented and tested.
