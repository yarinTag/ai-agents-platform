"""
Comprehensive Test Suite for Enterprise Organization Authentication, Department User Membership & JIT Onboarding:
Verifies:
1. Enterprise User and Department Membership persistence in SQLite.
2. Signed HS256 JWT access tokens and PBKDF2 password hashing.
3. Bulk email invitations with corporate domain validation.
4. Just-In-Time (JIT) robotic user onboarding upon invitation acceptance.
5. End-to-end REST API flows: Org registration, Login, /auth/me profile, and user listing.
6. Tenant & Department Isolation: Users blocked from executing workflows outside their assigned department (403 Forbidden).
7. Org Admin universal execution authority across all departments.
"""

import pytest
import uuid
import json
from fastapi.testclient import TestClient

from persistence import db_manager, Organization, Department, User, DepartmentMember, OrgInvitation
from backend.main import app
from backend.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password
)
from workflows.engine import WorkflowEngine, UnauthorizedUserDepartmentError


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_jwt_tokens_and_password_hashing():
    """Verify HS256 JWT token generation, claims decoding, expiration, and password hashing."""
    # 1. Password hashing
    password = "SuperSecretPassword123!"
    pw_hash = hash_password(password)
    assert pw_hash.startswith("pbkdf2_sha256$")
    assert verify_password(password, pw_hash) is True
    assert verify_password("WrongPassword!", pw_hash) is False

    # 2. JWT signing and claims verification
    payload = {
        "sub": "usr_test_001",
        "email": "dev@enterprise.internal",
        "org_id": "org_test_001",
        "role": "ORG_ADMIN",
        "departments": [{"id": "dept_core", "role": "MANAGER"}]
    }
    token = create_access_token(payload, expires_in_seconds=3600)
    assert token is not None
    assert len(token.split(".")) == 3

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "usr_test_001"
    assert decoded["email"] == "dev@enterprise.internal"
    assert decoded["role"] == "ORG_ADMIN"
    assert len(decoded["departments"]) == 1

    # 3. Tampered token rejected
    tampered_token = token[:-5] + "XXXXX"
    assert decode_access_token(tampered_token) is None


def test_enterprise_user_and_department_members_crud():
    """Verify User creation, Department assignment, listing, and removal in SQLite."""
    org_id = f"org_{uuid.uuid4().hex[:8]}"
    db_manager.create_organization(id=org_id, name="FinTech Corp", slug=f"fintech-{uuid.uuid4().hex[:6]}")

    dept_id = f"dept_core_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_id, name="Core Banking", organization_id=org_id)

    # 1. Create User
    user_id = f"usr_{uuid.uuid4().hex[:8]}"
    user = db_manager.create_user(
        id=user_id,
        organization_id=org_id,
        email=f"alice_{uuid.uuid4().hex[:4]}@fintech.corp",
        full_name="Alice Smith",
        role="MEMBER"
    )
    assert user.id == user_id
    assert user.organization_id == org_id
    assert "alice" in user.email

    # Lookup
    fetched = db_manager.get_user_by_email(user.email)
    assert fetched is not None
    assert fetched.id == user_id

    # 2. Add to Department
    dm = db_manager.add_user_to_department(dept_id, user_id, role="MANAGER")
    assert dm.department_id == dept_id
    assert dm.user_id == user_id
    assert dm.role == "MANAGER"

    # List department members
    members = db_manager.list_department_members(dept_id)
    assert len(members) == 1
    assert members[0]["user_id"] == user_id
    assert members[0]["email"] == user.email
    assert members[0]["full_name"] == "Alice Smith"

    # Check user departments
    user_depts = db_manager.get_user_departments(user_id)
    assert len(user_depts) == 1
    assert user_depts[0]["department_id"] == dept_id
    assert user_depts[0]["name"] == "Core Banking"

    # 3. Remove from department
    removed = db_manager.remove_user_from_department(dept_id, user_id)
    assert removed is True
    assert len(db_manager.list_department_members(dept_id)) == 0


def test_bulk_email_invitation_and_domain_validation():
    """Verify bulk invitations by email and rejection of foreign email domains."""
    org_id = f"org_corp_{uuid.uuid4().hex[:6]}"
    db_manager.create_organization(
        id=org_id,
        name="Global Logistics",
        slug=f"logistics-{uuid.uuid4().hex[:6]}",
        domain="logistics.corp"
    )

    dept_id = f"dept_ops_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_id, name="Operations", organization_id=org_id)

    # Bulk invite valid domain emails
    email1 = f"driver1_{uuid.uuid4().hex[:6]}@logistics.corp"
    email2 = f"driver2_{uuid.uuid4().hex[:6]}@logistics.corp"
    emails = [email1, email2]
    invites = db_manager.bulk_invite_to_department(
        organization_id=org_id,
        department_id=dept_id,
        emails=emails,
        role="OPERATOR"
    )
    assert len(invites) == 2
    assert invites[0].status == "PENDING"
    assert invites[0].invite_token.startswith("tok_")

    # Check pending invites lookup by email
    pending = db_manager.list_pending_invitations_for_email(email1)
    assert len(pending) == 1
    assert pending[0].department_id == dept_id


def test_jit_onboarding_via_invitation_token():
    """Verify Just-In-Time onboarding: when invited email accepts, auto-links to department."""
    org_id = f"org_jit_{uuid.uuid4().hex[:6]}"
    db_manager.create_organization(id=org_id, name="AI Research Hub", slug=f"airhub-{uuid.uuid4().hex[:6]}")

    dept_id = f"dept_ai_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_id, name="Deep Learning", organization_id=org_id)

    # Issue invitation for new employee
    invite_email = f"researcher_{uuid.uuid4().hex[:4]}@airhub.io"
    inv = db_manager.create_org_invitation(
        organization_id=org_id,
        email=invite_email,
        department_id=dept_id,
        role="OPERATOR"
    )
    assert inv.status == "PENDING"

    # User onboards by accepting invitation
    user, joined_depts = db_manager.onboard_user_by_email(
        organization_id=org_id,
        email=invite_email,
        full_name="Dr. Elena Vance"
    )
    assert user.email == invite_email
    assert user.full_name == "Dr. Elena Vance"
    assert len(joined_depts) == 1
    assert joined_depts[0].department_id == dept_id

    # Invitation marked ACCEPTED
    inv_after = db_manager.get_invitation_by_token(inv.invite_token)
    assert inv_after.status == "ACCEPTED"

    # Department now lists Elena
    members = db_manager.list_department_members(dept_id)
    assert any(m["email"] == invite_email for m in members)


def test_api_org_registration_login_and_me_endpoints(client):
    """Verify end-to-end REST API registration, login, and authenticated /auth/me session."""
    slug = f"skyline-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.corp"
    domain = f"{slug}.corp"

    # 1. Register organization + Org Admin
    reg_resp = client.post("/api/v1/auth/org-register", json={
        "name": "Skyline Global",
        "slug": slug,
        "domain": domain,
        "admin_email": admin_email,
        "admin_name": "Chief Architect",
        "admin_password": "AdminSecurePassword123!"
    })
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    token = reg_data["token"]
    assert token is not None
    assert reg_data["user"]["email"] == admin_email
    assert reg_data["user"]["role"] == "ORG_ADMIN"
    org_id = reg_data["organization"]["id"]

    # 2. Login with credentials
    login_resp = client.post("/api/v1/auth/login", json={
        "email": admin_email,
        "password": "AdminSecurePassword123!"
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    auth_token = login_data["token"]

    # Login with wrong password rejected
    bad_login = client.post("/api/v1/auth/login", json={
        "email": admin_email,
        "password": "WrongPassword!"
    })
    assert bad_login.status_code == 401

    # 3. Call /auth/me using Bearer JWT
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {auth_token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["user"]["email"] == admin_email
    assert me_data["organization"]["id"] == org_id

    # 4. Create department under organization
    dept_resp = client.post("/api/v1/departments", json={
        "name": "Infrastructure",
        "organization_id": org_id,
        "monthly_budget_usd": 500.0
    }, headers={"Authorization": f"Bearer {auth_token}"})
    assert dept_resp.status_code == 201
    dept_id = dept_resp.json()["id"]

    # 5. Bulk invite members to department via API
    invite_resp = client.post(f"/api/v1/departments/{dept_id}/members/bulk-invite", json={
        "emails": [f"eng1@{domain}", f"eng2@{domain}"],
        "role": "OPERATOR"
    }, headers={"Authorization": f"Bearer {auth_token}"})
    assert invite_resp.status_code == 201
    inv_data = invite_resp.json()
    assert inv_data["invited_count"] == 2
    tok1 = inv_data["invitations"][0]["invite_token"]

    # 6. Reject inviting unauthorized external domain
    bad_invite = client.post(f"/api/v1/departments/{dept_id}/members/bulk-invite", json={
        "emails": ["intruder@hacker.net"]
    }, headers={"Authorization": f"Bearer {auth_token}"})
    assert bad_invite.status_code == 400
    assert "does not belong to organization domain" in bad_invite.json()["detail"]

    # 7. Accept invitation via API (JIT onboarding for eng1)
    accept_resp = client.post("/api/v1/invitations/accept", json={
        "invite_token": tok1,
        "full_name": "Engineer One",
        "password": "EngPassword123!"
    })
    assert accept_resp.status_code == 200
    eng1_data = accept_resp.json()
    assert eng1_data["user"]["email"] == f"eng1@{domain}"
    assert len(eng1_data["departments"]) == 1
    assert eng1_data["departments"][0]["department_id"] == dept_id

    # 8. List department members
    members_resp = client.get(f"/api/v1/departments/{dept_id}/members", headers={"Authorization": f"Bearer {auth_token}"})
    assert members_resp.status_code == 200
    members_list = members_resp.json()
    assert len(members_list) == 1
    assert members_list[0]["email"] == f"eng1@{domain}"

    # 9. List organization users
    users_resp = client.get(f"/api/v1/organizations/{org_id}/users", headers={"Authorization": f"Bearer {auth_token}"})
    assert users_resp.status_code == 200
    assert len(users_resp.json()) == 2  # Admin + Engineer One


def test_department_workflow_execution_user_isolation(client):
    """
    Verify Tenant & Department Isolation:
    - User in Department A cannot execute Department B's workflow (403 Forbidden).
    - Org Admin can execute across all departments in the organization.
    - User in Department B can execute successfully.
    """
    org_id = f"org_iso_{uuid.uuid4().hex[:6]}"
    db_manager.create_organization(id=org_id, name="Security Bank", slug=f"secbank-{uuid.uuid4().hex[:6]}")

    dept_a = f"dept_a_{uuid.uuid4().hex[:6]}"
    dept_b = f"dept_b_{uuid.uuid4().hex[:6]}"
    db_manager.create_department(id=dept_a, name="Retail Banking", organization_id=org_id, monthly_budget_usd=500.0)
    db_manager.create_department(id=dept_b, name="Investment Banking", organization_id=org_id, monthly_budget_usd=500.0)

    # User A belongs to Dept A
    email_a = f"user_a_{uuid.uuid4().hex[:6]}@bank.corp"
    user_a = db_manager.create_user(
        id=f"usr_a_{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        email=email_a,
        full_name="User A",
        role="MEMBER"
    )
    db_manager.add_user_to_department(dept_a, user_a.id, role="OPERATOR")

    # User B belongs to Dept B
    email_b = f"user_b_{uuid.uuid4().hex[:6]}@bank.corp"
    user_b = db_manager.create_user(
        id=f"usr_b_{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        email=email_b,
        full_name="User B",
        role="MEMBER"
    )
    db_manager.add_user_to_department(dept_b, user_b.id, role="OPERATOR")

    # Org Admin belongs to Org
    email_adm = f"ciso_{uuid.uuid4().hex[:6]}@bank.corp"
    org_admin = db_manager.create_user(
        id=f"usr_adm_{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        email=email_adm,
        full_name="CISO Admin",
        role="ORG_ADMIN"
    )

    # Create workflow for Department B
    wf_b_id = f"wf_b_{uuid.uuid4().hex[:6]}"
    wf_b_def = {
        "id": wf_b_id,
        "name": "Investment Analysis",
        "steps": [
            {
                "key": "analyze",
                "name": "Analyze Portfolio",
                "agent_id": "test-analyst",
                "prompt_template": "Analyze market data"
            }
        ]
    }
    db_manager.create_workflow(
        id=wf_b_id,
        name="Investment Analysis",
        definition_json=json.dumps(wf_b_def),
        department_id=dept_b
    )

    # 1. User A tries to execute Department B's workflow via WorkflowEngine -> UnauthorizedUserDepartmentError
    engine = WorkflowEngine(db_manager=db_manager)
    user_a_ctx = {
        "sub": user_a.id,
        "email": user_a.email,
        "role": user_a.role,
        "departments": [{"id": dept_a, "role": "OPERATOR"}]
    }
    with pytest.raises(UnauthorizedUserDepartmentError) as exc_info:
        engine.execute_workflow(wf_b_id, user_context=user_a_ctx)
    assert "not an authorized member of department" in str(exc_info.value)

    # 2. User A tries via HTTP API with JWT Bearer -> 403 Forbidden
    token_user_a = create_access_token(user_a_ctx)
    resp_a = client.post(
        f"/api/v1/workflows/{wf_b_id}/execute",
        headers={"Authorization": f"Bearer {token_user_a}"}
    )
    assert resp_a.status_code == 403
    assert "Department Access Denied" in resp_a.json()["detail"]

    # 3. User B executes Department B's workflow via HTTP API -> 200 OK
    user_b_ctx = {
        "sub": user_b.id,
        "email": user_b.email,
        "role": user_b.role,
        "departments": [{"id": dept_b, "role": "OPERATOR"}]
    }
    token_user_b = create_access_token(user_b_ctx)
    resp_b = client.post(
        f"/api/v1/workflows/{wf_b_id}/execute",
        headers={"Authorization": f"Bearer {token_user_b}"}
    )
    assert resp_b.status_code == 200
    assert resp_b.json()["status"] == "COMPLETED"

    # 4. Org Admin executes Department B's workflow -> 200 OK (universal authority)
    admin_ctx = {
        "sub": org_admin.id,
        "email": org_admin.email,
        "role": "ORG_ADMIN",
        "departments": []
    }
    token_admin = create_access_token(admin_ctx)
    resp_adm = client.post(
        f"/api/v1/workflows/{wf_b_id}/execute",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert resp_adm.status_code == 200
    assert resp_adm.json()["status"] == "COMPLETED"
