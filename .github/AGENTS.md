# GitHub automation

## CI contracts
`workflows/ci.yml` runs on PRs, main/master pushes, manual dispatch and reusable calls.
Python 3.11 uses frozen uv dependencies with the dev extra and no project installation.
Backend syntax compilation and an explicit initial ten-file contract suite run without shared
conftest cleanup. These contracts use local files/Git, real SQLite and FastAPI; no provider
keys, live model calls, Docker services or channel sends are supplied. This is not the full suite.
JUnit reports are retained for 14 days even after failure. Dashboard uses Node22, npm ci,
oxlint, explicit TypeScript checking, cache tests and production build. Jobs are read-only
and time-bounded. No local tests/build/lint/typecheck/startup were performed for this task.

## Images
`workflows/images.yml` runs on main/master pushes, v-prefixed tags or manual dispatch.
It first calls the same CI workflow; publishing requires both CI jobs to pass. It builds
API, worker and dashboard separately and pushes to lowercase
`ghcr.io/<owner>/<repository>-<component>` with full sha-<commit>, branch/tag tags;
no implicit latest. Only image jobs receive packages:write. No deployment is configured.
Root and dashboard Docker ignore files exclude credentials, databases and local outputs.
Dashboard Docker build uses Node22 to match CI and Vite's runtime requirements.

## PR labels
`workflows/pr-labels.yml` reads current PR metadata/files through GitHub's API on
pull_request_target opened/reopened/synchronize/edited/ready_for_review, without checkout.
It creates missing labels, applies/removes only its managed area/type labels, and preserves
other labels. Areas: backend, frontend, tests, docs, ci, infrastructure, dependencies.
Types follow conventional PR-title prefixes: feat/fix/docs/refactor/test/ci/build/chore/perf/revert.
Multiple area labels are allowed; a title without a supported prefix gets no managed type.
Renamed files consider old and new paths. The workflow needs issues:write for label creation
and pull-requests:write for PR labels. It supports fork PRs without executing their content.
It becomes active once merged into the default branch. No external tokens are required.

## Administration
After first successful CI, configure a branch ruleset requiring Backend contracts and
Dashboard checks (use the actual reported names, including reusable prefixes if present).
Workflow files alone do not enable branch protection. GHCR package creation must be allowed
by repository/organization policy. CI may expose pre-existing source/lock incompatibilities;
never suppress failing checks or silently broaden the contract suite to live operations.
Use pinned immutable action SHAs when upgrading supply-chain policy; current major refs
should be reviewed and updated through normal PRs.
