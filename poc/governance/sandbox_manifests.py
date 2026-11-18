"""Render an inert offline sandbox bundle. No Kubernetes client or apply path.

Never use this builder as an admission controller. Admission, node attestation,
current permissions and durable attempt fencing are separate mandatory gates.
"""
import hashlib

from .sandbox_profile import SandboxAttempt, SandboxProfile


def build_sandbox_bundle(profile: SandboxProfile, attempt: SandboxAttempt) -> list[dict]:
    """Closed, tool-free baseline: no caller PodSpec, commands, mounts or egress.

    The approved image owns its entrypoint. There is no repository staging or
    inference connection in this slice. New IO requires a new reviewed profile.
    Revalidate at the boundary, including objects made with model_construct/copy.
    """
    profile = SandboxProfile.model_validate(profile.model_dump())
    attempt = SandboxAttempt.model_validate(attempt.model_dump())
    if attempt.profile_sha256 != profile.fingerprint():
        raise ValueError('Sandbox attempt profile fingerprint mismatch.')
    tenant = hashlib.sha256(attempt.organization_id.encode()).hexdigest()[:24]
    namespace = f'sbx-{tenant}-{attempt.attempt_id}'
    labels = {'platform.ai/sandbox': 'true', 'platform.ai/tenant': tenant,
              'platform.ai/attempt': attempt.attempt_id}
    annotations = {'platform.ai/profile-sha256': attempt.profile_sha256}
    resources = {'cpu': f'{profile.cpu_millis}m', 'memory': f'{profile.memory_mib}Mi',
                 'ephemeral-storage': f'{profile.scratch_mib * 2}Mi'}
    security = {'runAsNonRoot': True, 'runAsUser': profile.uid,
                'runAsGroup': profile.gid, 'seccompProfile': {'type': 'RuntimeDefault'}}
    container_security = {'allowPrivilegeEscalation': False, 'privileged': False,
                          'readOnlyRootFilesystem': True,
                          'capabilities': {'drop': ['ALL']}, **security}
    pod = {
        'os': {'name': 'linux'}, 'runtimeClassName': profile.runtime_class,
        'serviceAccountName': 'sandbox', 'automountServiceAccountToken': False,
        'enableServiceLinks': False, 'hostNetwork': False, 'hostPID': False,
        'hostIPC': False, 'shareProcessNamespace': False, 'restartPolicy': 'Never',
        'terminationGracePeriodSeconds': 10, 'securityContext': security,
        'containers': [{
            'name': 'agent', 'image': profile.image, 'imagePullPolicy': 'Always',
            'securityContext': container_security,
            'resources': {'requests': dict(resources), 'limits': dict(resources)},
            'volumeMounts': [{'name': 'scratch', 'mountPath': '/tmp'}],
            'env': [{'name': 'HOME', 'value': '/tmp'}],
        }],
        'volumes': [{'name': 'scratch', 'emptyDir': {
            'medium': 'Memory', 'sizeLimit': f'{profile.scratch_mib}Mi'}}],
    }
    def metadata(name):
        return {'name': name, 'namespace': namespace, 'labels': dict(labels)}

    return [
        {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {
            'name': namespace, 'labels': {**labels,
                'pod-security.kubernetes.io/enforce': 'restricted',
                'pod-security.kubernetes.io/enforce-version': profile.kubernetes_minor,
                'pod-security.kubernetes.io/audit': 'restricted',
                'pod-security.kubernetes.io/audit-version': profile.kubernetes_minor,
                'pod-security.kubernetes.io/warn': 'restricted',
                'pod-security.kubernetes.io/warn-version': profile.kubernetes_minor}}},
        {'apiVersion': 'v1', 'kind': 'ServiceAccount',
         'metadata': metadata('sandbox'), 'automountServiceAccountToken': False},
        {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
         'metadata': metadata('deny-all'), 'spec': {
             'podSelector': {}, 'policyTypes': ['Ingress', 'Egress'],
             'ingress': [], 'egress': []}},
        {'apiVersion': 'v1', 'kind': 'ResourceQuota',
         'metadata': metadata('attempt'), 'spec': {'hard': {
             'pods': '1', 'count/jobs.batch': '1',
             **{f'requests.{key}': value for key, value in resources.items()},
             **{f'limits.{key}': value for key, value in resources.items()}}}},
        {'apiVersion': 'batch/v1', 'kind': 'Job',
         'metadata': {**metadata('agent'), 'annotations': dict(annotations)},
         'spec': {'backoffLimit': 0, 'completions': 1, 'parallelism': 1,
                  'activeDeadlineSeconds': profile.deadline_seconds,
                  'template': {'metadata': {'labels': dict(labels),
                                            'annotations': dict(annotations)}, 'spec': pod}}},
    ]
