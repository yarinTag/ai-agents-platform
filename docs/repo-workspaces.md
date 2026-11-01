# Sandboxed repository workspaces

Workflow steps that must **run or change code** get a fresh clone of one approved
GitHub repository inside a Docker sandbox. Steps that only summarize activity keep
using the API-only connector tools (`docs/connector-execution.md`) and never clone.

## Declaring a workspace step

```yaml
steps:
  - key: fix-lint
    name: Fix lint errors
    agent_id: backend-dev
    prompt: Run the linter and fix every reported error.
    params:
      workspace:
        connector_id: github-main      # a CONNECTED GitHub connector in this org
        repository: acme/payments      # must be on the connector's allowed_repos
        ref: main                      # optional branch or tag; default branch if omitted
        mode: write                    # read (default) or write
        pr_title: Fix lint errors      # optional; write mode only
```

A workspace step cannot also declare `mcp_servers` or a `channel_action`. Validation
happens when the workflow is saved and again before execution.

## Requirements (all fail closed)

| Requirement | Why |
|---|---|
| Direct API runtime provider (Anthropic/OpenAI/NVIDIA HTTP) | The Claude Code CLI runs its own shell on the host; it is refused for workspace steps. |
| Docker on a POSIX host | No temp-directory fallback exists. |
| `PLATFORM_SANDBOX_IMAGE=name@sha256:<digest>` | Only digest-pinned images run. The image must contain the toolchain and dependencies, because the container has no network. |
| Department grant `clone_repository` on the connector | Read access. A `*` grant covers it. |
| Department grant `open_pull_request` (write mode) | Must be listed **explicitly**; a `*` grant never covers repository writes. |
| Agent MCP restrictions, active initiator, budget | Same live checks as connector tools, rechecked before clone, push and PR creation. |

## Lifecycle

1. The backend checks policy, refreshes a private object cache, then creates an isolated shallow checkout on the host: no
   tags or submodules, `core.symlinks=false`, hooks disabled, system/global git
   config ignored. The token goes only in that git process's environment
   (`GIT_CONFIG_*` extra header), never in a URL, `.git/config`, the model prompt or
   the container.
2. Git metadata uses `--separate-git-dir` outside the mount, and the worktree's `.git`
   pointer is deleted. Sandboxed code cannot change the config, hooks or remotes that
   the backend's git later uses.
3. A container starts with only the worktree mounted at `/workspace/repo`:
   `--network none`, `--cap-drop ALL`, `no-new-privileges`, read-only root, 512 MB
   `/tmp` tmpfs, 256 processes, 2 GB memory, 2 CPUs, non-root user, 1-hour lifetime.
4. The Direct API worker routes **every** local tool (Bash, Read, Write, Edit, Glob,
   Grep) through `docker exec`. The host filesystem is never read or written for the
   model. The worker's own cwd is an empty directory, not the checkout. Grep uses
   POSIX ERE syntax.
5. **Read mode:** changes are discarded.
   **Write mode:** after the step completes, the backend runs `git add --all`, rejects
   changes to `.github/workflows/`, `.github/actions/` or `.gitmodules`, caps the
   change at 200 files / 50,000 lines, commits as "AI Agents Platform", and pushes to a
   new `agent/<workflow>/<execution>-<step>` branch. The push uses
   `--force-with-lease=<branch>:` (an empty lease means the branch must not exist).
   It then opens a **draft** PR. No change means no PR.
6. The container and every workspace directory are removed when the step ends
   (success, failure, timeout or cancellation). The record is marked `RELEASED`, and a
   resumed task cannot reuse it.

## Workflow settings

Machine size, the network allowlist (via an egress proxy) and secrets come from the workflow's settings. See [workflow-settings.md](workflow-settings.md). That replaces the fixed 2 CPU / 2 GB and always-no-network defaults described above; with no allowlist, the container still has no network.

## Never done

- Push to the base branch, any existing branch, or force-push.
- Merge, approve or mark a PR ready. A human reviews and merges on GitHub. Enforce
  this with branch protection on the base branch.
- Clone for summary or reporting steps, the Playground, or the CLI runtime.

## Audit

`mcp_tool_calls` rows `call_repo_<sha256(task:operation)>` record `clone_repository`
(repository, ref, resolved commit) and `open_pull_request` (branch, base, commit,
changed files, PR URL). An operation already attempted for a task is not repeated
automatically. Git output is never surfaced because it can echo remote URLs.

## Known limits and residual risk

- Pushing a branch can trigger the repository's CI on that branch, with its secrets,
  before a human looks. Agent edits to workflow files are blocked, but existing CI
  still runs agent-modified code (tests, build scripts). Use CI that does not expose
  secrets to `agent/*` branches, or require approval for those runs.
- Each workspace step gets its own isolated checkout from a freshly refreshed object cache. Steps do not share a checkout yet.
- Step runtime is still capped at 300 seconds by the workflow step runner.
- The clone happens on the host. Keep host git current, because checkout-time git
  CVEs affect any clone of untrusted repositories.
- Processes a command leaves behind inside the container survive until the
  container is removed at step end.
- The visual step editor supports connector tools, read workspace, and code changes with a required draft PR. YAML/JSON editing remains available.

No tests, builds, application startup, Docker runs or live GitHub calls were
performed for this change.

## AI creation and required PR outcomes
Create with AI can now propose a typed repository workspace with required_outcome=pull_request. The chat lists workspace operations separately from GitHub activity tools. A PR request needs clone_repository and an explicit open_pull_request department grant; a wildcard grant does not authorize publishing. Existing workflow definitions and grants are not automatically migrated.

Native step example (replace IDs with authorized values):
```yaml
key: create_pr
agent_id: <workflow-runner-id>
prompt_template: Locate the version manifest and make the requested version bump.
mcp_servers: []
params:
  required_outcome: pull_request
  workspace:
    connector_id: <github-connector-id>
    repository: <owner/repository>
    mode: write
    pr_title: Bump core plugin version
```

The backend edits in an isolated workspace and publishes a draft PR only after existing policy checks. A required PR step fails if there are no changes/no PR receipt; dependent success messages do not run. Workspace mode and pinned sandbox image are checked before any steps. Configure Docker and PLATFORM_SANDBOX_IMAGE=name@sha256:<verified-digest> on the backend before execution; this change does not install/start Docker, choose an unverified image digest or grant permissions. Configure the proxy image only if using the optional network allowlist.

Governed connector-only model steps now return a final completed/blocked envelope. Invalid or blocked outcomes fail instead of treating explanatory prose as task completion. This is separate from actual connector receipt validation. No historical results or previously sent notifications are rewritten or resent.

## Visual editing
Open Workflows → Edit → Visual Step & Skill Builder. Under Step execution choose Read files or Code changes → draft PR, then select the authorized GitHub connector and repository, optional base branch/tag and optional draft PR title. Write mode sets params.required_outcome=pull_request and removes incompatible per-step connector/channel scopes. The MCP selector is disabled for workspace steps. Save Changes uses the existing optimistic workflow revision contract; no run is started by the editor.

The editor shares one department-authorized catalog fetch across all step controls. Missing explicit workspace permissions disable unavailable mode choices; failed permission reads do not invent repository options. Sandbox setup warnings are configuration-only (Docker binary and pinned image syntax); no daemon, container, provider or token permissions are tested by viewing this form. Actual run-time checks remain mandatory. AI preview shows the same setup warning. No existing workflow, grant or host environment was automatically modified during implementation.

## Shared repository object cache
Repository workspaces automatically reuse a persistent backend-only Git object cache. The first run initializes an entry; later workflows in the same organization using the same connector/repository reuse downloaded objects. Every run resolves and fetches the current requested remote branch/tag using current credentials. A cache hit never bypasses permissions or allows an unavailable/deleted ref to run from stale content.

The default location is `repo_cache` beside the SQLite database (normally `poc/data/repo_cache`). Optional backend environment settings:

| Setting | Default | Meaning |
| --- | --- | --- |
| PLATFORM_REPO_CACHE_DIR | Database-adjacent repo_cache | Persistent host cache directory |
| PLATFORM_REPO_CACHE_TTL_SECONDS | 604800 | Seven idle days before lazy expiry |
| PLATFORM_REPO_CACHE_MAX_ENTRIES | 8 | Retained entries per tenant; active entries can temporarily exceed this |
| PLATFORM_REPO_CACHE_MAX_ENTRY_BYTES | 536870912 | 512MiB retained-entry threshold; larger entries are discarded after checkout |

Retention runs on cache use, not a timer. Fetch-time disk usage is not capped by these retention settings. The cache may contain private source objects, so keep its directory private to the backend user and on persistent storage if it should survive container/server replacement. The normal database-adjacent location is already covered by the repository's data-directory ignore rule.

A per-entry cross-process lock serializes refresh/materialization. Each run receives independent object files and Git metadata, without hard links, alternates or shared working directories. The container only sees its worktree. Cache eviction does not invalidate active runs, and run edits/commits never enter the cache. Each step's clone_repository audit receipt and retained workspace JSON expose hit/refreshed/retained/commit/base_branch; hit reports an existing entry, not a measured download saving. Workspace cleanup removes run-owned files while cached objects remain. No live cache warming or workflow execution was performed during implementation.
