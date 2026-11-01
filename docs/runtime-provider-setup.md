# Choose CLI or direct API

On first use, select **CLI** or **Direct API** in the runtime setup dialog.
You can reopen it using **Runtime settings** in the top bar. Existing installations
keep their saved CLI selection until an administrator changes it.

This is a shared server default for agent tasks, workflows, the playground and
Workflow Assistant. Explicit agent provider overrides take precedence. An
organization administrator can change the default; server environment overrides
must be changed on the server first. Start a new conversation after switching
between API and CLI: their session histories use different formats.

## CLI

Choose an existing CLI backend and configure its login or gateway as before.
The existing **Anthropic API key** option in this group still runs Claude Code
with an API key. Choose **Direct API → Anthropic** to avoid Claude Code.

## Direct API

Configure credentials and model token prices in the environment of the backend
process, then restart that process if its environment changed. Re-scan in the
dialog, choose a provider and enter an exact tool-capable model ID available to
your account. Keys are read by the server, never stored in browser storage or
saved in the settings database.

| Provider | Credential | Input price per million tokens | Output price per million tokens |
| --- | --- | --- | --- |
| Anthropic | `ANTHROPIC_API_KEY` | `DIRECT_ANTHROPIC_INPUT_USD_PER_MILLION` | `DIRECT_ANTHROPIC_OUTPUT_USD_PER_MILLION` |
| OpenAI | `OPENAI_API_KEY` | `DIRECT_OPENAI_INPUT_USD_PER_MILLION` | `DIRECT_OPENAI_OUTPUT_USD_PER_MILLION` |
| NVIDIA NIM | `NVIDIA_API_KEY` | `DIRECT_NVIDIA_INPUT_USD_PER_MILLION` | `DIRECT_NVIDIA_OUTPUT_USD_PER_MILLION` |

Use the actual prices for your chosen model/account. Prices must be finite and
non-negative; zero must mean an actual zero price. Missing prices prevent direct
inference instead of recording unknown API usage as free. These configured rates
produce an estimate for platform accounting; upstream invoices, cache discounts,
service tiers and concurrent spend can differ. Authoring checks its remaining
budget before each request; this is not a cross-process spending reservation.

Provider model IDs are saved as `runtime_model_direct_anthropic`,
`runtime_model_direct_openai`, or `runtime_model_direct_nvidia`. Default and logical
tier assignments use the configured model. Explicit agent model IDs remain
explicit, so ensure their provider access and price configuration match. The
legacy `nvidia_nim/` prefix is removed before calling NVIDIA.

The model picker reflects the configured API model, not live discovery of your
provider account. Setup detection checks keys/prices only and makes no paid
requests. The first inference can still report an invalid key, unavailable model,
unsupported tool calling, quota limit or provider outage.

Direct inference uses [Anthropic Messages tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls),
[OpenAI Chat Completions function tools](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
or [NVIDIA NIM's compatible chat endpoint](https://docs.api.nvidia.com/nim/reference/create_chat_completion_v1_chat_completions_post).
No Claude Code installation is required for these paths.

## Tool and session behavior

Ordinary direct runs offer the authorized subset of Read, Write, Edit, Glob,
Grep, Bash and AskUserQuestion. File tools stay within the assigned workspace;
Bash runs only when it is explicitly listed in the agent's tools (managers and
orchestrators always receive it for delegation) or the permission bypass is
enabled. It is not an OS sandbox.

## Execution safety settings

| Variable | Default | Effect |
| --- | --- | --- |
| `PLATFORM_DANGEROUSLY_SKIP_PERMISSIONS` | `false` | `true` restores unattended approval of every tool for all CLI runs. Prefer per-agent `allowed_tools` or the per-agent flag. |
| `PLATFORM_WORKSPACE_ROOTS` | unset | Approved parent folders for project/agent working directories, separated by `:`. Paths outside them fail the run. `poc/workspaces` is always allowed and hosts the default workspace. `/` and your home folder itself are rejected as roots. |
| `PLATFORM_AGENT_ENV_PASSTHROUGH` | unset | Comma-separated variable names that may reach agent processes despite looking like credentials. |
| `JWT_SECRET_KEY` | unset (random per process) | Session signing key, 32+ characters. Set it for any real deployment. |
| `SLACK_SIGNING_SECRET` / `TELEGRAM_WEBHOOK_SECRET` | unset (callbacks refused) | Required to accept Slack/Telegram approval button callbacks. |

With the default, an agent with an empty tool list is effectively read-only in
CLI runs (tools needing approval are denied). Workflow runners are created with
Read, Grep, Glob, Write, Edit and AskUserQuestion; legacy runners saved with
`["*"]` receive that same set, never every tool.
CLI-installed extensions and inherited MCP servers are not imported into API runs.
An unsupported requested tool fails explicitly. Tool/result events are delivered
after each model response; token-by-token streaming is not implemented here.

Workflow Assistant connects only to its internal catalog/schema/YAML-validation
MCP server, retains current permission checks and saves inactive drafts explicitly.
Playground runs remain tool-free. API conversations persist privately beside the
database under `runtime_sessions`; resumption checks the tenant/agent scope,
provider and model. Authoring/playground do not create these transcripts.

## Verification status

Source and whitespace were reviewed. Tests, type checking, build, application
startup and live provider calls were not run because repository instructions
prohibit runtime verification for this task. The new source cases are in
`poc/tests/test_direct_runtime.py`; when authorized, run them with `--noconftest`.
