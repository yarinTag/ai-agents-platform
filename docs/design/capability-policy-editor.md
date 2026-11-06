# AI-17: capability/resource editor

The existing `/organization` route now includes Capabilities & resources. Own-org
administrators use the new tab in OrganizationPage. Other roles retain the scoped
DepartmentAccessPage and its authorized descriptions; they never mount administrative
OrganizationPage or request org users, credentials or runtime settings for this view.
There is no new sidebar item or duplicate settings route.

## Roles and explicit scope

The existing header chooses one department. All Departments shows assignment/selection
guidance and never becomes a wildcard edit target. Organization name, department and
effective current account/membership role are displayed. `usePermissions` intersects
account and membership ranks; current backend identity remains authoritative.

All department readers get Available access: implemented actions, exact resources,
separate authoring/execution decisions and approval conditions. Unsupported descriptors
are a separate non-editable inventory. Configuration/policy readiness is explicitly
not provider verification. A member can author but cannot execute by base role.

Effective managers get department policy and revision history. They may only append
deny/require_approval rules; saved rules/default are immutable in their editor. They
can amend/remove a new unsaved restriction in their draft. Administrators can edit,
remove or add rules/default within the existing grant ceiling and can choose the
Organization policy tab. No organization policy request is made for non-admins.
This follows the AI-16 restrictive-manager contract, superseding the original ticket
wording that suggested managers could independently grant wider access.

## Editing and recovery

The editor selects a trusted implemented capability and connector, then exact repository
or channel IDs, with explicit effect. No free-form tool, secret, command or wildcard
resource field is provided. Existing subject, workflow, branch and validity constraints
are displayed and retained; this basic editor does not author new advanced selectors.
Policy options do not authorize an operation that lacks an existing legacy grant.

Review changes displays the complete before/after rules/default and captured revision.
New/changed write/destructive allow rules show a warning. Only Confirm and save issues
a policy PUT with expected_revision; no automatic grants, activation, message, workflow
dispatch, provider test or model request occurs. Repeat submission is disabled in flight.
The policy refreshes after success. No-op documents remain server-defined no-ops.

409 preserves the visible unsaved draft and disables saving. The stale policy cannot be
reopened for edit; close and explicitly refresh to fetch the current revision. Validation
errors preserve the draft without exposing raw server exception bodies. Authority loss
clears old records/editor and shows scope-unavailable guidance. Failed reads disable
editing; independent read sections remain recoverable through tabs/refresh.

Organization/user/department/effective-role keys remount the scoped component, clearing
drafts, drawers, rows and errors synchronously. Fetches and writes use AbortSignal and
generation guards to discard late results. Tab changes clear the previous policy before
loading the new target. Data is in component memory only, never browser storage or URL.

## API projection

The shared authenticated `httpClient` carries bearer and selected department headers;
`governanceApi.ts` uses encoded path segments, cancellation and typed contracts from
`types/governance.ts`. Existing AI-16 endpoints are reused.

GET organization/department policy adds `resource_options` only on the protected read
response. Each entry contains capability_id, connector_id, connector_name, resource_type,
resource_ids. It includes implemented actions on exact configured resources even when
current typed policy denies them, allowing an administrator to repair restrictions.
Department options require an active own-org department connector grant; organization
options are own-org administrator-only. Provider configuration, credentials, unsupported
actions and foreign organization resources never appear in this projection. PUT and
history responses retain the original policy record shape. Options are not grants.

## Localization and verification

`i18n/governance.ts` owns matching typed English/Hebrew copy. ConfigProvider direction
follows the active locale, Ant Design forms/drawers inherit RTL, and immutable IDs remain
LTR in bdi elements. Inputs have accessible labels; success/error states use live roles;
scrollable tables and a viewport-bounded drawer support narrow layouts.

The isolated API audit covers safe option projections, denied-resource editing choices,
role/department isolation, CAS/revocation and existing action policy. It uses real
FastAPI/SQLite without agent execution or provider I/O. Frontend type/lint/build and
existing logic tests run in GitHub CI. No local UI/browser/render/accessibility or live
provider execution is claimed. AI-18 broader P01 documentation and subsequent generic
action/event/approval capabilities remain separate tickets.

The review drawer title identifies the organization/department policy and exact scope ID. Refresh controls are disabled while the draft editor is open; explicit close/reload is required for conflict recovery. A rule edit remains cancellable when its original resource option is no longer configured.
