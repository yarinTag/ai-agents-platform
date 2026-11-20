"""Offline policy denial cases; no cluster mocks or runtime execution.

Source only under the current repository verification restriction.
"""
import copy

import pytest
from pydantic import ValidationError

from governance.sandbox_manifests import build_sandbox_bundle
from governance.sandbox_profile import SandboxAttempt, SandboxProfile


def profile(**overrides):
    return SandboxProfile.model_validate({
        'profile_id': 'test-only', 'revision': 1, 'isolation': 'vm-isolated',
        'runtime_class': 'test-vm', 'kubernetes_minor': 'v1.35',
        'image': 'registry.invalid/agent@sha256:' + 'a' * 64,
        'uid': 1000, 'gid': 1000, 'cpu_millis': 500, 'memory_mib': 512,
        'runtime_cpu_overhead_millis': 100, 'runtime_memory_overhead_mib': 64,
        'scratch_mib': 32, 'deadline_seconds': 60, **overrides})


def attempt(policy, organization='org-a'):
    return SandboxAttempt(organization_id=organization, attempt_id='b' * 32,
                          profile_sha256=policy.fingerprint())


@pytest.mark.parametrize('override', [
    {'image': 'registry.invalid/agent:latest'}, {'uid': 0}, {'gid': 0},
    {'cpu_millis': True}, {'memory_mib': '512'}, {'deadline_seconds': 0},
    {'scratch_mib': 513}, {'isolation': 'shared-kernel'},
    {'runtime_class': ''}, {'hostNetwork': True}, {'volumes': []},
    {'image': 'registry.invalid//agent@sha256:' + 'a' * 64},
    {'command': ['sh']}, {'env': {'TOKEN': 'secret'}},
    {'memory_mib': 128, 'scratch_mib': 128},
    {'memory_mib': 128, 'scratch_mib': 512},
])
def test_untrusted_profile_extensions_and_weaker_settings_rejected(override):
    with pytest.raises(ValidationError):
        profile(**override)


def test_revised_policy_cannot_reuse_old_attempt_binding():
    original = profile()
    changed = profile(revision=2)
    with pytest.raises(ValueError, match='fingerprint mismatch'):
        build_sandbox_bundle(changed, attempt(original))


def test_unvalidated_model_copy_cannot_bypass_boundary_validation():
    original = profile()
    forged = original.model_copy(update={'uid': 0})
    with pytest.raises(ValidationError):
        build_sandbox_bundle(forged, attempt(original))


def test_same_attempt_identifier_in_other_tenant_has_separate_namespace():
    policy = profile()
    first = build_sandbox_bundle(policy, attempt(policy))
    other = build_sandbox_bundle(policy, attempt(policy, 'org-b'))
    assert first[0]['metadata']['name'] != other[0]['metadata']['name']
    assert len(first[0]['metadata']['name']) <= 63


def test_mutating_returned_bundle_does_not_change_future_policy_output():
    policy = profile()
    identity = attempt(policy)
    bundle = build_sandbox_bundle(policy, identity)
    original = copy.deepcopy(bundle)
    bundle[-1]['spec']['template']['spec']['hostNetwork'] = True
    bundle[2]['spec']['egress'].append({})
    assert build_sandbox_bundle(policy, identity) == original


def test_closed_baseline_has_no_credential_or_network_delivery_path():
    policy = profile()
    bundle = build_sandbox_bundle(policy, attempt(policy))
    pod = bundle[-1]['spec']['template']['spec']
    assert not pod['automountServiceAccountToken']
    assert bundle[2]['spec']['egress'] == []
    assert bundle[2]['spec']['ingress'] == []
    assert {volume['name'] for volume in pod['volumes']} == {'scratch'}
    assert all('hostPath' not in volume and 'secret' not in volume
               and 'projected' not in volume for volume in pod['volumes'])
    assert not any(item['kind'] in {'Role', 'RoleBinding', 'Secret'} for item in bundle)


def test_vm_overhead_fits_quota_without_expanding_agent_limit():
    policy = profile()
    bundle = build_sandbox_bundle(policy, attempt(policy))
    quota = bundle[3]['spec']['hard']
    limits = bundle[-1]['spec']['template']['spec']['containers'][0]['resources']['limits']
    assert quota['requests.cpu'] == quota['limits.cpu'] == '600m'
    assert quota['requests.memory'] == quota['limits.memory'] == '576Mi'
    assert limits['cpu'] == '500m'
    assert limits['memory'] == '512Mi'
