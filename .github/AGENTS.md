# GitHub automation

## Required checks and execution boundaries
`workflows/ci.yml` runs on pull requests, main/master pushes, manual dispatch and reusable
calls. Read-only GitHub permissions, disabled checkout credential persistence, job deadlines
and fail-fast:false preserve independent failure evidence. No production secrets, cloud
credentials, provider keys or live notification destinations are supplied. Python uses 3.11,
frozen uv.lock with the dev extra and --no-install-project. All backend tests use --noconftest
to avoid the shared default-database reset hook. Each matrix job has its own disposable runner.

Backend tests are selected explicitly after source review:
- core: workflow_revisions, workflow_origin, workflow_playground, direct_reasoning,
  direct_pricing, repo_cache (six test_*.py files).
- security: organization_provider_credentials, connector_execution_security, workflow_chat,
  workflow_pr_authoring (four files).
- runtime: execution_backends, claude_hosted, completion_validation, sandbox_diagnostics,
  direct_runtime, workflow_notification_modes (six files).

Real SQLite, local Git/files, FastAPI/JWT and local Unix HTTP contracts are used. Hosted SDK
contracts do not start the SDK or Docker or call a provider. Other unreviewed legacy suites
remain outside CI; this is not full-system or live integration coverage. JUnit artifacts have
unique per-suite names and 14-day retention, uploaded even on test failure.

Dashboard checks use Node22/npm ci, named lint/TypeScript/unit-test/build steps. All
`tests/*.test.mjs` files run, rather than only one named file. Build does not replace tsc.
PR-only Container build matrix checks API/worker/dashboard Dockerfiles with push:false,
no registry login and separate pr-* cache scopes. CI required runs with always(), requires
both test jobs to succeed, and requires all container builds on PR events. Non-PR calls
require container checks to be skipped; actual publish builds live in images.yml.
Failures, cancellation and unexpected skips cannot turn the aggregate check green.

## Immutable Actions and updates
All external uses references are pinned to full commit hashes with readable version comments.
Dependabot checks github-actions weekly and opens reviewable update PRs; no automatic merge.
Pinned commits were resolved from the upstream GitHub API. No untrusted PR text is interpolated
into shell or script source. The matrix test list is passed as environment data.

## Image publishing
images.yml first calls the same CI; publishing requires CI including its aggregate to pass.
Only image jobs receive packages:write and GHCR credentials. API/worker/dashboard images
publish to lowercase ghcr.io/<owner>/<repository>-<component> with full sha-<commit>,
branch/tag tags and no implicit latest. Main/master, v* tags and manual dispatch are supported.
Root/dashboard Docker ignore files exclude environment files, databases and local outputs.
No deployment or automatic PR merge is configured.

## PR labeling
pr-labels.yml uses pull_request_target opened/reopened/synchronize/edited/ready_for_review.
It reads current metadata/files through GitHub API, never checks out or executes PR content.
Only it receives issues:write and pull-requests:write. Missing managed labels are created;
managed area/type labels are synchronized while unrelated labels remain. Areas: backend,
frontend, tests, docs, ci, infrastructure, dependencies. Types use conventional PR titles.
Renames consider old/new paths. Labels can run during merge conflicts; pull_request CI cannot.

## Merge enforcement limitation
The private repository's current plan returns HTTP403 for both branch protection and rulesets.
CI required is a reporting/publishing gate, not an enforceable merge restriction on this plan.
After upgrading, require CI required with an up-to-date branch and pull-request-only changes,
apply restrictions to administrators, prohibit force pushes/deletion, and configure appropriate
review requirements. Preserve existing rules when applying protection. Do not claim labels,
CODEOWNERS or an Actions workflow can substitute for server-enforced branch protection.

## Verification
CI hardening is verified on GitHub in the organization runtime PR. No local model calls,
application startup, Docker execution or local test/build/lint/typecheck is performed.

## Master Actions synchronization
Master now owns the hardened workflow baseline and runs 11 backend files available there.
This branch preserves all 16 contracts because its five feature-specific files are present.
Syncing master does not merge this PR or include frontend tests from the separate PR #24.
