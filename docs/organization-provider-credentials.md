# Organization-owned provider credentials

Source implementation; no tests, build, imports, application startup or provider calls were executed.

## Configuration and transition

Each organization must configure its own Direct API credentials in Runtime settings. Configure PLATFORM_SECRETS_KEY on the server first: base64 of 32 random bytes, matching the existing workflow-secret encryption requirement. Retain it in deployment secret storage and back it up separately from SQLite. Losing or changing this encryption key makes existing encrypted credentials unreadable; provider-key replacement does not rotate the encryption master key.

Existing platform_settings runtime keys, provider environment variables, ~/.fcc/.env and PLATFORM_RUNTIME_PROVIDER are not inherited by organization execution. They are neither automatically copied into a tenant nor deleted. An administrator must re-enter each organization's credentials and default provider/model. Legacy global plaintext settings should be removed by an explicitly owned deployment migration after confirming that they are no longer needed. This source change does not modify any live database or environment.

The existing shared CLI/gateway selection is not a fallback for organization model execution. Legacy agent provider values must be updated to a supported direct_* provider or cleared to inherit the organization's saved default. Supported providers: direct_anthropic, direct_openai, direct_nvidia, direct_openrouter. This does not introduce department model grants or atomic budget reservations.

## API

GET /api/v1/runtimes and POST /api/v1/runtimes/detect return only the authenticated organization's provider configuration. available/has_api_key mean a stored credential exists, not a verified vendor connection or usable encryption key. Effective/default and model settings are organization-owned. GET /api/v1/models reads the same scope; unconfigured organizations receive an empty list.

PUT /api/v1/runtimes/selection retains provider_id, model_id, api_key, provider_keys, provider_models and enabled_providers. Values are write-only SecretStr fields; missing/blank keys preserve existing credentials. All models/providers/required credentials are validated before one atomic write. Malformed requests return a generic 422 without rejected input; invalid models/providers/missing required credentials return 400; missing encryption configuration or storage failure returns a sanitized 503. Authentication requires a current ACTIVE database user in the signed organization, and management requires its current ORG_ADMIN role. Explicit org-bound service authentication remains supported. No client-supplied organization ID selects credential ownership.

DELETE /api/v1/runtimes/credentials/{provider_id} revokes only the caller organization's key and returns updated setup metadata. Revocation is repeat-safe. Replacing a key gives it a fresh random positive 62-bit version, including after revoke/recreate. Configuration responses never contain key values, ciphertext or nonce.

## Storage and execution

storage.runtime_settings.OrganizationRuntimeSettings is a scoped settings/credential port. organization_schema initializes additive tables:

- organization_runtime_settings: organization_id, key, value, updated_at; primary key (organization_id,key).
- organization_provider_credentials: organization_id, provider, ciphertext, nonce, version, updated_by, updated_at; primary key (organization_id,provider).
- organization_provider_credential_events: id, organization_id, provider, action (REPLACE/REVOKE), actor_id, created_at. Credential changes and their metadata-only events commit together.

All tables reference organizations with ON DELETE CASCADE. AES-256-GCM authenticates ciphertext against the exact organization and provider identity, preventing copying a key row into another scope. Keys never go through get_setting or settings_json.

Task execution binds organization to the current stored agent, rejects a conflicting task/config/project organization and records the bound task organization. Command construction resolves agent provider/model owner, then organization default; absent organization/provider/key fails closed. Workflow chat captures the verified user's organization and carries the stored job organization to its temporary tool-free profile. Playground uses the stored agent as well.

The parent decrypts only the selected key, pins its version, and passes that key plus database/organization/version context to the Direct HTTP worker. The encryption master key and other providers' keys are removed. Before every HTTP request, the worker checks current organization existence and credential version in SQLite. Revocation/rotation blocks the next request; it cannot recall an already sent request. Resumption starts a new worker with current credentials. This is not a transaction spanning SQLite and the external provider.

Model-directed shell/container environments remove provider credentials and PLATFORM_PROVIDER_* context, even when an operator configured credential passthrough. The worker remains a trusted server process; this is not a new OS security boundary for host-local agents. Production repository tools continue using the existing Docker boundary.

## Workflow visibility

Existing /workflows/:workflowId/logs?execution=<executionId> polls every five seconds and displays per-step runtime events, expandable JSON and export. reasoning_summary is provider-visible content per completed response, with an explicit missing-summary state, not complete hidden reasoning or token streaming. Tool-use events include the command/input. The current direct worker emits local tool_use after execution and tool_result only for connector calls; local shell/file output is not consistently logged as a separate event. No additional log-view behavior was implemented by this credentials change.

## Deferred verification

poc/tests/test_organization_provider_credentials.py contains real SQLite/FastAPI source contracts for organization separation, encryption/AAD tampering, global fallback refusal, stale roles, disabled users, input redaction, atomic validation/encryption failure, worker rotation/revoke and command/tool environment hygiene. They were not executed. Existing tests that assumed global credentials/provider selection require migration to organization-scoped setup before becoming the regression acceptance gate.

## Explicit local migration (2026-11-03)
At the user request, the sole local organization received its existing NVIDIA key encrypted under a newly generated ignored root .env PLATFORM_SECRETS_KEY. Existing tenant entries were preserved; legacy globals were retained. Enabled providers without stored credentials were disabled in imported configuration. No API calls, application startup or tests were performed. Restart the server to load the encryption key. This was an explicit local migration, not an automatic cross-tenant fallback.

The explicit local migration also copied the existing OPENROUTER_API_KEY from the previously supported ~/.fcc/.env source into the sole organization encrypted credential store and re-enabled direct_openrouter, preserving any already stored organization credential. The source file was retained; no automatic FCC fallback was restored and no provider calls were made.
