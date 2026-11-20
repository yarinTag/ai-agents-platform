"""Operator-owned deployment declarations, not authorization or residency proof."""
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DeploymentContract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class ServicePlacement(DeploymentContract):
    service: Literal[
        'execution', 'policy', 'inference', 'mcp', 'secrets',
        'artifacts', 'execution_logs', 'security_audit', 'backups',
    ]
    boundary: Literal['customer', 'vendor', 'external']
    # Registry identity, never a URL, credential, or caller-defined connection.
    resource_id: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$')


class DeploymentProfile(DeploymentContract):
    schema_version: Literal[1] = 1
    installation_id: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$')
    organization_id: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$')
    revision: int = Field(ge=1)
    mode: Literal['customer_hosted', 'vendor_hosted_dedicated']
    connectivity: Literal['connected', 'air_gapped']
    database: Literal['postgresql']
    continuity: Literal['approved_artifacts']
    services: tuple[ServicePlacement, ...] = Field(min_length=9, max_length=64)
    # Explicit declaration of every customer-data service leaving its boundary.
    approved_data_egress: tuple[str, ...] = Field(max_length=9)
    management_enabled: bool
    management_metadata: tuple[
        Literal['installation_version', 'update_available', 'health_code'], ...
    ] = Field(max_length=3)

    @field_validator('schema_version', mode='before')
    @classmethod
    def exact_schema_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('Unsupported deployment schema version.')
        return value

    @model_validator(mode='after')
    def consistent_boundary(self):
        required = {
            'execution', 'policy', 'inference', 'mcp', 'secrets',
            'artifacts', 'execution_logs', 'security_audit', 'backups',
        }
        if {item.service for item in self.services} != required:
            raise ValueError('Every customer-data service must have a placement.')
        identities = [(item.service, item.resource_id) for item in self.services]
        if len(identities) != len(set(identities)):
            raise ValueError('Duplicate service resource placement.')
        approved = set(self.approved_data_egress)
        if len(approved) != len(self.approved_data_egress) or not approved <= required:
            raise ValueError('Egress declarations must be unique known services.')
        local = 'customer' if self.mode == 'customer_hosted' else 'vendor'
        remote = {item.service for item in self.services if item.boundary != local}
        if remote != approved:
            raise ValueError('Data egress must match the declared service placements.')
        if any(item.boundary != local for item in self.services
               if item.service in {'execution', 'policy', 'secrets'}):
            raise ValueError('Execution, policy and secrets must remain in the data plane.')
        if self.mode == 'customer_hosted' and remote:
            raise ValueError('Customer-hosted content must remain inside its boundary.')
        if len(set(self.management_metadata)) != len(self.management_metadata):
            raise ValueError('Duplicate management metadata field.')
        if not self.management_enabled and self.management_metadata:
            raise ValueError('Disabled management cannot export metadata.')
        if self.connectivity == 'air_gapped' and (
                self.mode != 'customer_hosted' or self.management_enabled or remote):
            raise ValueError('Air-gap requires a local independent data plane.')
        return self


def validate_deployment_profile(profile: DeploymentProfile) -> DeploymentProfile:
    """Revalidate even instances built using model_construct/model_copy."""
    return DeploymentProfile.model_validate(profile.model_dump())


def deployment_fingerprint(profile: DeploymentProfile) -> str:
    """Canonical declaration identity, never an approval or attestation."""
    document = validate_deployment_profile(profile).model_dump(mode='json')
    document['services'].sort(key=lambda item: (item['service'], item['resource_id']))
    document['approved_data_egress'].sort()
    document['management_metadata'].sort()
    encoded = json.dumps(document, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()
