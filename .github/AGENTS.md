# GitHub automation

## Required checks and execution boundaries
`workflows/ci.yml` runs on pull requests, main/master pushes, v-prefixed tag pushes and manual dispatch. Read-only GitHub permissions, disabled checkout credential persistence, job deadlines
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
Container build validates API/worker/dashboard images without login or publishing on PRs
and non-publishing manual runs. CI required aggregates Image plan, all backend suites,
dashboard and the applicable build checks; failures/cancellations/unexpected skips fail it.
Publish runs skip build-only checks because the gated publishing job builds each image once.
The image matrix is defined once in Image plan and shared by build/publish jobs.

## Immutable Actions and updates
All external uses references are pinned to full commit hashes with readable version comments.
Dependabot checks github-actions weekly and opens reviewable update PRs; no automatic merge.
Pinned commits were resolved from the upstream GitHub API. No untrusted PR text is interpolated
into shell or script source. The matrix test list is passed as environment data.

## Unified image publishing
ci.yml owns checking, building and publishing; images.yml is removed. A main/master or
v* tag push runs tests once and publishes only after CI required succeeds. Manual dispatch
builds without publishing by default; publish=true opts in only on main/master or v* refs.
Other refs cannot publish, even with that flag. PR code never runs in a packages:write job.
Only Publish image receives packages:write and GHCR login; read-only Container build
uses push:false and pr-* cache scopes. Publishing uses separate component cache scopes.
Images retain lowercase ghcr.io/<owner>/<repository>-<component> names, sha-<fullcommit>,
branch/tag tags and no implicit latest. Tests do not run twice on master anymore.
New PR runs cancel older runs for the same PR; publishing runs are not cancelled mid-push.
No deployment or automatic merge is configured.

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
The November5 master synchronization includes the merged frontend tests from PR #24
and the unified ci.yml publishing path. This PR retains its 16 backend contract files;
images.yml stays deleted. Feature-specific Anthropic Message Threads documentation is
preserved alongside master frontend-test guidance. Syncing master does not merge this PR.


The security matrix now additionally selects test_access_policy.py, test_access_lab_setup.py and
test_skill_connections.py (19 backend files total on this branch). They use actual temporary SQLite,
FastAPI/JWT, Markdown/JSON inputs and private filesystem fixtures, without application lifespan,
provider calls or live messages. Existing current-identity fixtures are aligned with DB-backed scope.
No CI dispatch or local test/build/typecheck/lint was performed in this task.
