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

1. The backend checks policy, then clones on the host: shallow, single branch, no
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
- Each workspace step gets its own clone. Steps do not share a checkout yet.
- Step runtime is still capped at 300 seconds by the workflow step runner.
- The clone happens on the host. Keep host git current, because checkout-time git
  CVEs affect any clone of untrusted repositories.
- Processes a command leaves behind inside the container survive until the
  container is removed at step end.
- The workflow editor UI has no workspace form yet. Edit the YAML/JSON directly.

No tests, builds, application startup, Docker runs or live GitHub calls were
performed for this change.
