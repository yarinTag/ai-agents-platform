"""Strict versioned policy and decision contracts, independent of HTTP/providers."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


def timestamp(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Validity timestamps must include a timezone.')
    return parsed.astimezone(timezone.utc)


class PolicyRule(StrictModel):
    id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,79}$')
    capability_id: str = Field(pattern=r'^[a-z][a-z0-9_-]*\.[a-z][a-z0-9_]*$', max_length=150)
    capability_version: int = Field(default=1, ge=1, le=1)
    connector_id: str = Field(min_length=1, max_length=200)
    resource_type: str = Field(pattern=r'^[a-z][a-z0-9_]{0,49}$')
    resource_ids: list[str] = Field(min_length=1, max_length=100)
    effect: Literal['allow', 'deny', 'require_approval']
    user_ids: list[str] = Field(default_factory=list, max_length=100)
    agent_ids: list[str] = Field(default_factory=list, max_length=100)
    workflow_ids: list[str] = Field(default_factory=list, max_length=100)
    branches: list[str] = Field(default_factory=list, max_length=30)
    not_before: str | None = Field(default=None, max_length=40)
    expires_at: str | None = Field(default=None, max_length=40)

    @field_validator('resource_ids', 'user_ids', 'agent_ids', 'workflow_ids', 'branches')
    @classmethod
    def exact_ids(cls, values):
        if len(values) != len(set(values)) or any(not value.strip() or value != value.strip()
                or len(value) > 300 or '*' in value or '\x00' in value for value in values):
            raise ValueError('Use unique, bounded, exact identifiers; wildcard resources/subjects are forbidden.')
        return values

    @model_validator(mode='after')
    def valid_window(self):
        start, end = timestamp(self.not_before), timestamp(self.expires_at)
        if start and end and start >= end:
            raise ValueError('expires_at must be later than not_before.')
        return self


class PolicyDocument(StrictModel):
    schema_version: Literal[1] = 1
    default: Literal['inherit', 'deny'] = 'inherit'
    rules: list[PolicyRule] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def unique_rules(self):
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError('Policy rule IDs must be unique.')
        return self


class PolicyUpdate(PolicyDocument):
    expected_revision: int = Field(ge=0)


class DecisionRequest(StrictModel):
    capability_id: str = Field(min_length=1, max_length=150)
    capability_version: int = Field(default=1, ge=1, le=1)
    connector_id: str = Field(min_length=1, max_length=200)
    resource_id: str = Field(min_length=1, max_length=300)
    purpose: Literal['authoring', 'execution'] = 'execution'
    agent_id: str | None = Field(default=None, min_length=1, max_length=200)
    workflow_id: str | None = Field(default=None, min_length=1, max_length=200)
    execution_id: str | None = Field(default=None, min_length=1, max_length=200)
    branch: str | None = Field(default=None, min_length=1, max_length=200)
