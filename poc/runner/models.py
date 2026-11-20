"""Immutable server-owned runner plan and resource identities for AI-56."""
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, model_validator

from governance.sandbox_profile import FrozenContract, SandboxAttempt, SandboxProfile

Identifier = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$')]
State = Literal['Requested', 'Preparing', 'Ready', 'Running', 'Stopping',
                'Released', 'CleanupFailed']
Operation = Literal['Provision', 'Start', 'Stop', 'Delete']


class RunnerPlan(FrozenContract):
    schema_version: Literal[1] = 1
    attempt: SandboxAttempt
    profile: SandboxProfile
    initiator_id: Identifier
    agent_id: Identifier
    environment_id: Identifier
    domain_id: Identifier
    base_version: int = Field(ge=0)
    config_revision: int = Field(ge=1)
    input_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    requested_at: int = Field(ge=0)
    deadline_at: int = Field(ge=1)

    @model_validator(mode='after')
    def bound_lifetime(self):
        if self.attempt.profile_sha256 != self.profile.fingerprint():
            raise ValueError('Runner plan profile binding mismatch.')
        if not 0 < self.deadline_at - self.requested_at <= self.profile.deadline_seconds:
            raise ValueError('Deadline includes preparation and must fit the approved profile.')
        return self

    def fingerprint(self):
        body = json.dumps(self.model_dump(), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(body.encode()).hexdigest()


class OwnedResource(FrozenContract):
    """Cluster-returned UID recorded after an acknowledged create, never name adoption."""
    kind: Literal['Namespace', 'ServiceAccount', 'NetworkPolicy', 'ResourceQuota', 'Job']
    name: str = Field(pattern=r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')
    uid: Identifier


def validate_plan(plan: RunnerPlan) -> RunnerPlan:
    return RunnerPlan.model_validate(plan.model_dump())
