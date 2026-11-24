# AI-55 PostgreSQL operation intents

`PostgresRunnerOperations` composes the existing PostgreSQL journal and its
installation→attempt lock order. It is inactive and receives no Kubernetes client.

`begin(org, attempt, owner_token, owner_epoch, revision, operation)` supports
Provision from Requested and Start from Ready. It repeats live ownership, lease,
recovery epoch and deadline checks and requires the exact revision/IDLE state.
It records STARTED and a distinct operation_token atomically before transport.
Provision moves to Preparing. No caller boolean establishes cluster success.

`record_resource` accepts an OwnedResource whose kind/name matches the immutable
plan and operation. It stores the acknowledged UID immediately. Exact retries
do not add revisions; a replaced UID fails. STARTED and UNKNOWN claims can retain
late evidence after revoke, lease expiry or recovery without restoring authority.

`finish(..., outcome=NOT_DISPATCHED)` resets the operation only if no resource from
that operation was acknowledged; it never clears revocation. UNKNOWN retains the
operation token, revokes execution and blocks automatic retry/owner takeover.
Ready/Running/Released success and Stop/Delete cleanup claims remain unimplemented.

Explicit journal initialization adds nullable operation_token transactionally;
it is not called by startup. Existing ambiguous rows without an operation token
cannot adopt a new one: they remain fenced for explicit reconciliation. Tokens
and private plans must not be exposed in HTTP or diagnostic projections.

Real PostgreSQL CI tests cover ownership races, crash fencing, late/duplicate UID,
tenant scope and refusal of fabricated success. This extends the source contract;
it does not activate a Runner or prove cluster termination, staging, isolation,
full migration/cutover, environment-head promotion or artifact durability.
