"""AI-53 offline contracts; not execution authorization or cluster attestation."""
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class SandboxProfile(FrozenContract):
    """Trusted operator configuration, never populated from workflow parameters.

    No built-in approved profile exists. Cluster evidence and admission enforcement
    remain release gates, even when a structurally valid profile can be constructed.
    """

    schema_version: Literal[1] = 1
    profile_id: str = Field(pattern=r'^[a-z][a-z0-9-]{0,39}$')
    revision: int = Field(ge=1)
    isolation: Literal['vm-isolated']
    # Deliberately accept a DNS-label subset of Kubernetes DNS-subdomain names.
    runtime_class: str = Field(pattern=r'^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$')
    kubernetes_minor: str = Field(pattern=r'^v1\.[0-9]{2}$')
    image: str = Field(min_length=75, max_length=350)
    uid: int = Field(ge=1000, le=65534)
    gid: int = Field(ge=1000, le=65534)
    cpu_millis: int = Field(ge=100, le=4000)
    memory_mib: int = Field(ge=128, le=8192)
    runtime_cpu_overhead_millis: int = Field(ge=0, le=4000)
    runtime_memory_overhead_mib: int = Field(ge=0, le=8192)
    scratch_mib: int = Field(ge=16, le=512)
    deadline_seconds: int = Field(ge=1, le=3600)

    @field_validator('image')
    @classmethod
    def pinned_image(cls, value):
        import re
        label = r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?'
        registry = rf'{label}(?:\.{label})*(?::[1-9][0-9]{{0,4}})?'
        component = r'[a-z0-9]+(?:[._-][a-z0-9]+)*'
        if not re.fullmatch(rf'{registry}/(?:{component}/)*{component}@sha256:[0-9a-f]{{64}}', value):
            raise ValueError('Use an explicit registry/repository and exact sha256 digest.')
        return value

    def fingerprint(self) -> str:
        document = json.dumps(self.model_dump(), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(document.encode()).hexdigest()


class SandboxAttempt(FrozenContract):
    """Server-derived identity and immutable policy binding; contains no secrets."""

    organization_id: str = Field(min_length=1, max_length=200)
    attempt_id: str = Field(pattern=r'^[0-9a-f]{32}$')
    profile_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')

    @field_validator('organization_id')
    @classmethod
    def exact_organization(cls, value):
        if value != value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError('Organization ID must be exact and free of control characters.')
        return value
