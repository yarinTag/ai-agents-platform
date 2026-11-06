"""Run only reviewed HTTP contracts in a disposable source snapshot.

Module-level legacy persistence singletons resolve relative to their copied source,
so they cannot initialize or migrate the working application's database. The real
FastAPI routers and temporary SQLite repositories are exercised without app lifespan,
agent/model execution, service doubles, external HTTP or subprocesses inside pytest.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

API_CONTRACTS = [
    'poc/tests/test_github_pr_governance_api.py',
    'poc/tests/test_capability_policy_api.py',
    'poc/tests/test_generic_governance_api.py',
    'poc/tests/test_access_policy.py::test_lists_details_and_selected_department_are_scoped',
    'poc/tests/test_access_policy.py::test_stale_admin_claims_and_disabled_users_cannot_restore_rights',
    'poc/tests/test_access_policy.py::test_membership_role_limits_global_manager_and_revocation_takes_effect',
    'poc/tests/test_access_policy.py::test_member_write_and_foreign_nested_reference_fail_before_mutation',
    'poc/tests/test_access_policy.py::test_manager_can_update_own_workflow_but_cannot_change_tenant',
    'poc/tests/test_access_policy.py::test_org_admin_is_never_a_platform_admin',
    'poc/tests/test_access_policy.py::test_operator_can_operate_own_agent_but_not_manage_it',
    'poc/tests/test_access_policy.py::test_department_transfer_cannot_silently_transfer_history',
    'poc/tests/test_access_policy.py::test_all_department_members_can_author_workflows',
    'poc/tests/test_workflow_pr_approvals.py::test_approval_is_owned_requires_manager_and_records_real_actor',
    'poc/tests/test_workflow_pr_approvals.py::test_expiry_and_revision_change_cannot_approve',
]


def run_audit(report_dir):
    repository = Path(__file__).resolve().parents[2]
    if not (repository / '.git').exists():
        raise ValueError('Run from a checkout so only tracked/unignored source is copied.')
    report_dir = Path(report_dir).resolve()
    if report_dir.is_relative_to(repository):
        raise ValueError('Audit reports must be outside the checkout.')
    report_dir.mkdir(parents=True, exist_ok=True)
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '-z'],
                                    cwd=repository).decode().split('\0')
    paths += ['poc/tests/api_audit_guard.py', 'poc/tests/run_api_audit.py',
              'poc/tests/test_generic_governance_api.py']
    with tempfile.TemporaryDirectory(prefix='ai13_api_audit_') as directory:
        snapshot = Path(directory) / 'source'
        snapshot.mkdir()
        for relative in paths:
            source = repository / relative
            if (not relative or not source.is_file() or source.is_symlink()
                    or source.suffix not in {'.py', '.json', '.yaml', '.yml', '.toml'}
                    or not (relative.startswith('poc/') or relative == 'pyproject.toml')
                    or any(part in {'data', 'workspaces', 'runtime_sessions', '__pycache__', 'node_modules'}
                           for part in Path(relative).parts)):
                continue
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        # Keep OS plumbing only; do not forward organization/provider/bot keys or DB URLs.
        env = {name: value for name, value in os.environ.items()
               if name in {'PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT', 'WINDIR', 'TMPDIR'}}
        env.update(PLATFORM_DEV_MODE='1', PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH=str(snapshot) + os.pathsep + str(snapshot / 'poc'))
        command = [str(repository / '.venv' / 'bin' / 'python'), '-m', 'pytest', '--noconftest',
                   '-p', 'poc.tests.api_audit_guard', '-q', *API_CONTRACTS,
                   '--junitxml=' + str(report_dir / 'api-audit.xml')]
        completed = subprocess.run(command, cwd=snapshot, env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (report_dir / 'api-audit.log').write_text(completed.stdout)
        print(completed.stdout)
        summary = {'exit_code': completed.returncode, 'report': str(report_dir / 'api-audit.xml'),
                   'guard': 'No network or child processes; runtime disabled; disposable source/SQLite only.'}
        (report_dir / 'api-audit-summary.json').write_text(json.dumps(summary, indent=2))
        return completed.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-dir', required=True)
    raise SystemExit(run_audit(parser.parse_args().report_dir))
