# Workflow settings: model, machine size, network and secrets

Open **Workflows → Settings** on a saved workflow. Viewing is allowed for anyone who
can see the workflow. Changing settings or secrets requires a current-database
**ORG_ADMIN**, or a **MANAGER** of the workflow's department. The JWT role alone is
not enough. Every change is written to `audit_logs`: `workflow.settings.update`,
`workflow.secret.set` and `workflow.secret.delete`. Secret values are never logged.

## Settings (`definition.settings`, versioned with the workflow)

| Field | Values | Applies to |
|---|---|---|
| `model` | `null`/`"default"`, a tier ID (`tier:developer`), or a catalog model ID from `/api/v1/models` | Every workflow step task (`wf_task_*`). It overrides the agent's model, and the runtime resolves it for the active provider. Invalid stored settings fail the step. |
| `machine_size` | `small` (1 CPU / 1 GB / 128 pids), `medium` (2 / 4 GB / 256, default), `large` (4 / 8 GB / 512) | Repository-sandbox (code) steps. |
| `network_allowlist` | Up to 20 exact hostnames (no IPs, ports, schemes or wildcards) | Repository-sandbox steps. Empty means no network at all. |

API: `GET /api/v1/workflows/{id}/settings` and
`PUT /api/v1/workflows/{id}/settings {settings, expected_revision, change_summary?}`.
A PUT creates a normal workflow revision and returns 409 on a stale `expected_revision`.

## Network allowlist (egress proxy)

When the allowlist is non-empty, the sandbox joins a per-step **internal** Docker
network. Its only route out is a proxy container (`workflows/egress_proxy.py`,
stdlib Python) with `HTTPS_PROXY`/`HTTP_PROXY` preset in the sandbox. The proxy:
- accepts only `CONNECT host:443`, so plain HTTP is refused and secrets can't go out in cleartext;
- requires an exact hostname match against the allowlist;
- dials only globally routable IPs (no private, loopback, link-local or cloud-metadata addresses), connecting to the resolved IP so DNS can't rebind;
- runs with cap-drop ALL, a read-only root, user 65534, 256 MB and 0.5 CPU.

Programs that ignore proxy variables simply cannot connect. The proxy needs
`PLATFORM_SANDBOX_PROXY_IMAGE`, a digest-pinned image containing `python3`. The
proxy and network are removed with the sandbox.

## Secrets

`PUT /api/v1/workflows/{id}/secrets/{NAME}` with exactly one of `{"value": "..."}` or
`{"external_ref": "arn:aws:secretsmanager:..."}`. Use `DELETE` with the same path to remove one.
`GET .../settings` lists names, kinds and ARNs only; values are write-only.

- **Encrypted:** AES-256-GCM via `cryptography`, keyed by `PLATFORM_SECRETS_KEY` (base64 of 32 random bytes, e.g. `openssl rand -base64 32`). The ciphertext is bound to its workflow and name (AAD). A missing key makes the API return 503.
- **External:** AWS Secrets Manager ARNs restricted to `PLATFORM_EXTERNAL_SECRET_ARN_PREFIXES` (comma-separated, required). They are fetched at step start with the server's own IAM credentials and need `pip install .[aws]` (boto3).
- **Names:** `UPPER_SNAKE_CASE` (max 64). Reserved names (`PATH`, `HOME`, proxy and loader variables), `PLATFORM_*` and `DOCKER_*` are rejected. Limits: 50 secrets per workflow and 32 KB per value.

**Delivery:** only to repository-sandbox containers, as environment variables passed
through the docker CLI's process environment (`--env NAME`). Values never appear in
command-line arguments, the database workspace record or prompts. The model only
gets the variable *names*. The worker loads the values from a host-only 0600 file
(deleted with the workspace) and redacts them from every tool result
(`[REDACTED:NAME]`). Write mode refuses to publish if any changed file contains a
secret value. Resolution failures fail the step; a run never starts with only some
of its secrets.

## Residual risks

- Anyone with Docker access on the host can see container env (`docker inspect`), as with any Docker secret-by-env.
- Allowlisted hosts are trusted destinations: sandboxed code can send secrets **to them**.
- Redaction matches exact values only. Encoded forms (base64, hex) are not masked.
- Encrypted values in the 0600 redaction file live on host disk for the step's duration.
- The proxy also listens on Docker's default bridge (no published port).

No tests, builds, Docker runs, AWS calls or live inference were performed.
