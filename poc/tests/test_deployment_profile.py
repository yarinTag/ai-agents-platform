"""Deployment boundary contracts; no application, database or provider setup."""
import pytest
from pydantic import ValidationError

from governance.deployment_profile import (
    DeploymentProfile, ServicePlacement, deployment_fingerprint,
)


SERVICES = (
    'execution', 'policy', 'inference', 'mcp', 'secrets',
    'artifacts', 'execution_logs', 'security_audit', 'backups',
)


def profile(**changes):
    return DeploymentProfile(
        installation_id='installation-a', organization_id='org-a', revision=1,
        mode='customer_hosted', connectivity='connected', database='postgresql',
        continuity='approved_artifacts',
        services=tuple(ServicePlacement(service=name, boundary='customer',
                                        resource_id=name) for name in SERVICES),
        approved_data_egress=(), management_enabled=False,
        management_metadata=(), **changes,
    )


def test_incomplete_inventory_is_rejected():
    original = profile()
    with pytest.raises(ValidationError):
        DeploymentProfile.model_validate({**original.model_dump(),
                                          'services': original.services[:-1]})


@pytest.mark.parametrize('change', [
    {'database': 'sqlite'}, {'continuity': 'full_home'},
    {'schema_version': True}, {'revision': True},
    {'management_metadata': ('prompts',)},
    {'management_metadata': ('health_code',)},
    {'management_required': True},
    {'approved_data_egress': ('unknown',)},
])
def test_invalid_or_content_export_configuration_is_rejected(change):
    with pytest.raises(ValidationError):
        DeploymentProfile.model_validate({**profile().model_dump(), **change})


def test_private_mcp_connection_does_not_hide_external_inference():
    original = profile()
    placements = tuple(item.model_copy(update={'boundary': 'external'})
                       if item.service == 'inference' else item
                       for item in original.services)
    with pytest.raises(ValidationError, match='Customer-hosted'):
        DeploymentProfile.model_validate({**original.model_dump(),
            'services': placements, 'approved_data_egress': ('inference',)})


def test_hosted_remote_service_needs_explicit_egress_declaration():
    original = profile()
    document = {**original.model_dump(), 'mode': 'vendor_hosted_dedicated',
        'services': tuple(ServicePlacement(service=name,
            boundary='customer' if name == 'mcp' else 'vendor', resource_id=name)
            for name in SERVICES)}
    with pytest.raises(ValidationError, match='egress'):
        DeploymentProfile.model_validate(document)
    DeploymentProfile.model_validate({**document, 'approved_data_egress': ('mcp',)})


def test_airgap_rejects_management_connection():
    with pytest.raises(ValidationError, match='Air-gap'):
        DeploymentProfile.model_validate({**profile().model_dump(),
            'connectivity': 'air_gapped', 'management_enabled': True})


def test_duplicate_resource_cannot_declare_conflicting_boundaries():
    original = profile()
    with pytest.raises(ValidationError, match='Duplicate'):
        DeploymentProfile.model_validate({**original.model_dump(),
            'services': (*original.services, original.services[0].model_copy(
                update={'boundary': 'vendor'}))})


def test_nested_forged_placement_is_revalidated_at_fingerprint_boundary():
    original = profile()
    forged = original.model_copy(update={'services': (
        original.services[0].model_copy(update={'boundary': 'untrusted'}),
        *original.services[1:],
    )})
    with pytest.raises(ValidationError):
        deployment_fingerprint(forged)


def test_fingerprint_revalidates_forged_instance_and_ignores_inventory_order():
    original = profile()
    reordered = original.model_copy(update={'services': original.services[::-1]})
    assert deployment_fingerprint(original) == deployment_fingerprint(reordered)
    assert deployment_fingerprint(original) != deployment_fingerprint(
        original.model_copy(update={'revision': 2}))
    with pytest.raises(ValidationError):
        deployment_fingerprint(original.model_copy(update={'database': 'sqlite'}))
