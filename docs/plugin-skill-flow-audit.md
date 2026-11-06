# Plugin skill flow source audit — 2026-11-05

## Scope and evidence

The configured organization selects Git mode and `yarinTag/t-skills`, not the adjacent
local checkout. Read-only GitHub source retrieval resolved HEAD to
`683b503edd0cfb5dcf309e9307b25af6d06838c9`. A source-only audit of that immutable snapshot
covered all 58 discoverable skill definitions in the manifest: core 28, shared 6,
tech-backend 12, and tech-devops/frontend/security/testing 3 each. The adjacent local
checkout contains uncommitted changes, including engineering-review sequencing, so it
was not used as the authority for Git-mode behavior. No plugin files were changed.

Inspected source: full skill definitions and named inter-skill references, the PRD
router's lifecycle overview, `references/skill-dependency-dag.json`,
`references/lifecycle-state-machine.md`, and blueprint handoff sections. This was text
and data inspection, not execution of skill scripts or application runtime verification.

## Concrete corrections

| Source in pinned repository | Evidence | Correct interpretation |
|---|---|---|
| `core/skills/product-eng-review/SKILL.md:15` | Link to a storage protocol under `product-idea-to-blueprint/references` | Documentation dependency; not an outgoing invocation of blueprint |
| Same file, lines 25 and 84 | Trigger spike evaluation if technology is unverified | Conditional review → spike evaluator handoff |
| Same file, line 85 | Trigger ADR evaluation for an architectural trade-off | Conditional review → ADR handoff |
| Same file, line 94 | If all checks pass, certify and hand off to architecture | Conditional review → architecture handoff |
| `core/skills/product-prd-writer/SKILL.md:108` | After alignment, hand off to engineering review and architecture | Explicit instruction context, not every mention of another skill |
| PRD router dependency JSON, `PHASE_1_PUBLISH.nextNodes` | Publish → engineering review node | Declared lifecycle transition; evidence belongs to the JSON, not the publisher's own SKILL.md |
| `product-spec-drift-detector/SKILL.md:40` | If PASS, emit report. Hand off to planning | Conditional even though the condition precedes a sentence boundary |
| Architecture/planning/coverage definitions | Reuse blueprint validator scripts | Resource references, not execution of the whole blueprint skill |
| Shared finance router, Routing table | Request signals select a named finance skill | Conditional routing; ordinary boundary/comparison tables remain references |
| Dependency JSON coverage → `tech-frontend / tech-backend` | Package group, not a unique skill ID | Unresolved transition warning; no invented target or shortcut to code review |

## Representation and limits

`plugins/connections.py` emits evidence-bearing `skill_connections` objects:
`source`, `target`, `kind`, optional `conditional`, and `evidence` containing path,
line or JSON node ID, exact source text, optional heading and source tree revision.
Kinds are `handoff`, `conditional_handoff`, `declared_transition`, and `reference`.

Only conservative positive imperative syntax and explicit routing-table rows become
instruction handoffs. Frontmatter, fenced examples, path/script references, negation,
non-goals, ambiguous aliases and preview-only content cannot establish a flow edge.
The named dependency JSON supplies transitions dynamically; it is never embedded as
hardcoded Core edges in the frontend. Optional source/target DAG nodes remain optional.
Unknown group targets are not guessed. Bare mentions are optional dotted references.

The graph is evidence-backed **documented relationships**, not proof of a single runtime
execution order or exhaustive semantic understanding of arbitrary English. The source
itself has multiple modes: the generic router orders engineering review before architecture,
while blueprint Step 6 invokes engineering review after architecture. These cannot be
flattened into a universal, unconditional chain. Handoffs issued by an orchestrator mean
that orchestrator invokes the target, not that its sibling targets run consecutively.
Evidence and conditions remain inspectable so mode/gate differences are not concealed.
Unrecognized prose remains a reference rather than a guessed transition; absence of an
edge does not certify that no relationship exists. No claim of 100% semantic completeness.

Git scanning now decodes immutable blob SHAs from the selected tree, preventing a moving
HEAD from mixing skill/DAG versions. Local metadata reads up to one million characters
instead of silently using only 16 KiB; incomplete/unreadable content warns and cannot
establish prose flow. Tree revision is returned for Git skills/evidence. Refresh plugins
after updating the backend to replace old browser/server summaries.

## Plugin filter repair

Previous focus added its immediate neighbours back into the visible set regardless of
package filter. The new visibility function is strictly package/search based. Changing
the package clears selection and search, cancels pending focus reveals and resets scrolling.
Cross-package inspector navigation explicitly changes the dropdown to the target package;
it does not leave nodes from the previous package mixed into the canvas. Changing the
source remounts graph state. Search also clears focus.

## Validation status

Source-reviewed the projection, scanner/content ownership, edge aggregation, condition
preservation and filter transitions. Added unexecuted backend contracts in
`poc/tests/test_skill_connections.py`, updated frontend projection cases, and added
`pluginGraphModel.test.mjs` for strict filters, optional references, direction and aggregation.
`git diff --check` is the permitted whitespace check. No tests, lint, typecheck, build,
application startup, model calls, skill scripts or notifications were executed.
