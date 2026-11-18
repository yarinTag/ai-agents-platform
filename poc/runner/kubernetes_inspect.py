"""Read-only Kubernetes ownership reconciliation. Never starts or deletes a Job."""
from dataclasses import dataclass
from typing import Protocol

from governance.sandbox_manifests import build_sandbox_bundle
from .models import OwnedResource, RunnerPlan, validate_plan


class ClusterReader(Protocol):
    def get(self, path: str) -> dict | None:
        """Return decoded object; None ONLY for an authenticated API HTTP 404.

        Implementations must enforce trusted TLS/cluster identity, no redirects,
        bounded response/timeouts and no environment credential fallback. Other
        errors must raise. No transport implementation is activated in this slice.
        """
        ...


@dataclass(frozen=True)
class Inspection:
    status: str
    reason: str


def inspect_job(reader: ClusterReader, plan: RunnerPlan,
                owned: tuple[OwnedResource, ...]) -> Inspection:
    """UIDs are required; labels and names alone never establish ownership.

    Absence is diagnostic, never proof of process termination or Released.
    """
    plan = validate_plan(plan)
    resources = tuple(OwnedResource.model_validate(item.model_dump()) for item in owned)
    manifests = build_sandbox_bundle(plan.profile, plan.attempt)
    namespace = manifests[0]['metadata']['name']
    namespaces = [item for item in resources if item.kind == 'Namespace' and item.name == namespace]
    jobs = [item for item in resources if item.kind == 'Job' and item.name == 'agent']
    if len(namespaces) != 1 or len(jobs) != 1:
        return Inspection('UNKNOWN', 'MISSING_UID_RECEIPTS')
    try:
        ns = reader.get(f'/api/v1/namespaces/{namespace}')
        if ns is None:
            return Inspection('ABSENT', 'NAMESPACE_ABSENT_NOT_TERMINATION_PROOF')
        if ns.get('metadata', {}).get('uid') != namespaces[0].uid:
            return Inspection('UNKNOWN', 'NAMESPACE_UID_MISMATCH')
        job = reader.get(f'/apis/batch/v1/namespaces/{namespace}/jobs/agent')
        if job is None:
            return Inspection('ABSENT', 'JOB_ABSENT_NOT_TERMINATION_PROOF')
        metadata = job.get('metadata', {})
        if metadata.get('uid') != jobs[0].uid or metadata.get('annotations', {}).get(
                'platform.ai/profile-sha256') != plan.attempt.profile_sha256:
            return Inspection('UNKNOWN', 'JOB_IDENTITY_MISMATCH')
        if job.get('spec', {}).get('template') != manifests[-1]['spec']['template']:
            # API defaulting/admission can add fields. Until a reviewed comparison
            # contract exists, defaulting produces UNKNOWN rather than approval.
            return Inspection('UNKNOWN', 'JOB_TEMPLATE_NOT_EXACT')
        conditions = job.get('status', {}).get('conditions', [])
        terminal = {item.get('type') for item in conditions if item.get('status') == 'True'}
        if 'Complete' in terminal and 'Failed' in terminal:
            return Inspection('UNKNOWN', 'CONTRADICTORY_JOB_CONDITIONS')
        if 'Failed' in terminal:
            return Inspection('TERMINAL', 'JOB_FAILED')
        if 'Complete' in terminal:
            return Inspection('TERMINAL', 'JOB_COMPLETE_NOT_CLEANUP_PROOF')
        return Inspection('PRESENT', 'JOB_PRESENT_NOT_AGENT_READINESS')
    except Exception:
        # Provider bodies/credentials are never persisted or emitted here.
        return Inspection('UNKNOWN', 'CLUSTER_READ_FAILED')
