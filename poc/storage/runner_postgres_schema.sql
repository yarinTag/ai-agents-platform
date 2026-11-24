-- Explicit opt-in fresh-schema migration; never run from application startup.
CREATE TABLE IF NOT EXISTS sandbox_runner_installations (
    organization_id TEXT NOT NULL,
    installation_id TEXT NOT NULL,
    recovery_epoch BIGINT NOT NULL DEFAULT 1 CHECK (recovery_epoch > 0),
    PRIMARY KEY (organization_id, installation_id)
);
CREATE TABLE IF NOT EXISTS sandbox_runner_attempts (
    organization_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    installation_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    recovery_epoch BIGINT NOT NULL,
    plan_json TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'Requested' CHECK (state IN
      ('Requested','Preparing','Ready','Running','Stopping','Released','CleanupFailed')),
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    owner_epoch BIGINT NOT NULL DEFAULT 0 CHECK (owner_epoch >= 0),
    claim_token TEXT,
    lease_until BIGINT NOT NULL DEFAULT 0,
    deadline_at BIGINT NOT NULL,
    operation TEXT CHECK (operation IN ('Provision','Start','Stop','Delete')),
    operation_state TEXT NOT NULL DEFAULT 'IDLE' CHECK
      (operation_state IN ('IDLE','STARTED','UNKNOWN')),
    operation_token TEXT,
    resources_json TEXT NOT NULL DEFAULT '[]',
    reason TEXT NOT NULL DEFAULT 'CREATED',
    updated_at BIGINT NOT NULL,
    PRIMARY KEY (organization_id, attempt_id),
    FOREIGN KEY (organization_id, installation_id) REFERENCES
      sandbox_runner_installations (organization_id, installation_id)
);
CREATE TABLE IF NOT EXISTS sandbox_runner_effects (
    organization_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    effect_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    owner_epoch BIGINT NOT NULL,
    recovery_epoch BIGINT NOT NULL,
    state TEXT NOT NULL DEFAULT 'INTENT' CHECK
      (state IN ('INTENT','IN_FLIGHT','SUCCEEDED','FAILED','UNKNOWN')),
    receipt_json TEXT,
    revision BIGINT NOT NULL DEFAULT 1,
    updated_at BIGINT NOT NULL,
    PRIMARY KEY (organization_id, execution_id, effect_id),
    FOREIGN KEY (organization_id, attempt_id) REFERENCES
      sandbox_runner_attempts (organization_id, attempt_id)
);
CREATE TABLE IF NOT EXISTS sandbox_runner_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    event TEXT NOT NULL,
    effect_id TEXT,
    owner_epoch BIGINT NOT NULL,
    recorded_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS sandbox_runner_effect_attempt
    ON sandbox_runner_effects (organization_id, attempt_id, state);
-- Explicit initialization also upgrades an existing inactive journal additively.
ALTER TABLE sandbox_runner_attempts ADD COLUMN IF NOT EXISTS operation_token TEXT;

-- Application role must not be superuser/BYPASSRLS. Migration role owns DDL.
DO $$
DECLARE table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'sandbox_runner_installations', 'sandbox_runner_attempts',
    'sandbox_runner_effects', 'sandbox_runner_history'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
    IF NOT EXISTS (SELECT 1 FROM pg_policies
                   WHERE schemaname = current_schema() AND tablename = table_name
                     AND policyname = 'runner_tenant') THEN
      EXECUTE format(
        'CREATE POLICY runner_tenant ON %I USING '
        '(organization_id = NULLIF(current_setting(''app.current_org_id'', true), '''')) '
        'WITH CHECK '
        '(organization_id = NULLIF(current_setting(''app.current_org_id'', true), ''''))',
        table_name);
    END IF;
  END LOOP;
END $$;
