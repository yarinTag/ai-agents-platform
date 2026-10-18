"""
Enterprise Users, Department Members & Email Onboarding Repository Mixin.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import uuid
import secrets
from .models import User, DepartmentMember, OrgInvitation
from shared.validators import normalize_email


class UsersRepositoryMixin:
    """Mixin providing enterprise user identity, department membership, and JIT onboarding."""

    def create_user(
        self,
        id: str,
        organization_id: str,
        email: str,
        full_name: str,
        role: str = "MEMBER",
        status: str = "ACTIVE",
        password_hash: Optional[str] = None
    ) -> User:
        """Create an enterprise user under an organization."""
        now = datetime.now().isoformat()
        clean_email = normalize_email(email)
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO users (
                    id, organization_id, email, full_name, role, status, password_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (id, organization_id, clean_email, full_name.strip(), role, status, password_hash, now, now))
            conn.commit()
        user = self.get_user(id)
        if not user:
            raise RuntimeError(f"Failed to create user {id}")
        return user

    def get_user(self, id: str) -> Optional[User]:
        """Get an enterprise user by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            return User(
                id=row['id'],
                organization_id=row['organization_id'],
                email=row['email'],
                full_name=row['full_name'],
                role=row['role'],
                status=row['status'],
                password_hash=row['password_hash'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                last_login_at=row['last_login_at']
            )

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get an enterprise user by normalized email."""
        clean_email = normalize_email(email)
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (clean_email,)).fetchone()
            if not row:
                return None
            return User(
                id=row['id'],
                organization_id=row['organization_id'],
                email=row['email'],
                full_name=row['full_name'],
                role=row['role'],
                status=row['status'],
                password_hash=row['password_hash'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                last_login_at=row['last_login_at']
            )

    def list_users_by_organization(self, organization_id: str) -> List[User]:
        """List all users belonging to an enterprise organization."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM users WHERE organization_id = ? ORDER BY created_at ASC
            """, (organization_id,)).fetchall()
            return [
                User(
                    id=r['id'],
                    organization_id=r['organization_id'],
                    email=r['email'],
                    full_name=r['full_name'],
                    role=r['role'],
                    status=r['status'],
                    password_hash=r['password_hash'],
                    created_at=r['created_at'],
                    updated_at=r['updated_at'],
                    last_login_at=r['last_login_at']
                )
                for r in rows
            ]

    def update_user(self, id: str, **kwargs) -> Optional[User]:
        """Update user profile or status."""
        fields = []
        params = []
        now = datetime.now().isoformat()
        for k in ("full_name", "role", "status", "password_hash", "last_login_at"):
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?")
                params.append(kwargs[k])
        if fields:
            fields.append("updated_at = ?")
            params.append(now)
            params.append(id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_user(id)

    def add_user_to_department(
        self,
        department_id: str,
        user_id: str,
        role: str = "OPERATOR"
    ) -> DepartmentMember:
        """Assign a user to a department with a specified department role."""
        member_id = f"dmem_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO department_members (id, department_id, user_id, role, joined_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(department_id, user_id) DO UPDATE SET
                    role = excluded.role
            """, (member_id, department_id, user_id, role, now))
            conn.commit()

            row = conn.execute("""
                SELECT * FROM department_members WHERE department_id = ? AND user_id = ?
            """, (department_id, user_id)).fetchone()
            if not row:
                raise RuntimeError(f"Failed to add user {user_id} to department {department_id}")
            return DepartmentMember(
                id=row['id'],
                department_id=row['department_id'],
                user_id=row['user_id'],
                role=row['role'],
                joined_at=row['joined_at']
            )

    def remove_user_from_department(self, department_id: str, user_id: str) -> bool:
        """Remove a user from a department."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM department_members WHERE department_id = ? AND user_id = ?
            """, (department_id, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def list_department_members(self, department_id: str) -> List[Dict[str, Any]]:
        """List all members of a department with user details."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT dm.id, dm.department_id, dm.user_id, dm.role, dm.joined_at,
                       u.email, u.full_name, u.role as org_role, u.status as user_status
                FROM department_members dm
                JOIN users u ON dm.user_id = u.id
                WHERE dm.department_id = ?
                ORDER BY dm.joined_at ASC
            """, (department_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_user_departments(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all departments a user is a member of."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT d.id as department_id, d.name, d.description, d.monthly_budget_usd,
                       d.organization_id, dm.role as department_role, dm.joined_at
                FROM department_members dm
                JOIN departments d ON dm.department_id = d.id
                WHERE dm.user_id = ?
                ORDER BY d.name ASC
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def create_org_invitation(
        self,
        organization_id: str,
        email: str,
        department_id: Optional[str] = None,
        role: str = "MEMBER",
        expires_in_days: int = 7
    ) -> OrgInvitation:
        """Issue an email-based invitation to join an organization/department."""
        inv_id = f"inv_{uuid.uuid4().hex[:12]}"
        invite_token = f"tok_{secrets.token_urlsafe(24)}"
        now_dt = datetime.now()
        expires_at = (now_dt + timedelta(days=expires_in_days)).isoformat()
        clean_email = normalize_email(email)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO org_invitations (
                    id, organization_id, department_id, email, role, invite_token, expires_at, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """, (inv_id, organization_id, department_id, clean_email, role, invite_token, expires_at, now_dt.isoformat()))
            conn.commit()

        inv = self.get_invitation_by_token(invite_token)
        if not inv:
            raise RuntimeError(f"Failed to create invitation for {email}")
        return inv

    def get_invitation_by_token(self, token: str) -> Optional[OrgInvitation]:
        """Fetch an invitation by token."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM org_invitations WHERE invite_token = ?", (token,)).fetchone()
            if not row:
                return None
            return OrgInvitation(
                id=row['id'],
                organization_id=row['organization_id'],
                department_id=row['department_id'],
                email=row['email'],
                role=row['role'],
                invite_token=row['invite_token'],
                expires_at=row['expires_at'],
                status=row['status'],
                created_at=row['created_at']
            )

    def list_pending_invitations_for_email(self, email: str) -> List[OrgInvitation]:
        """Fetch active pending invitations for a specific email."""
        clean_email = normalize_email(email)
        now_iso = datetime.now().isoformat()
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM org_invitations
                WHERE LOWER(email) = LOWER(?) AND status = 'PENDING' AND expires_at > ?
            """, (clean_email, now_iso)).fetchall()
            return [
                OrgInvitation(
                    id=r['id'],
                    organization_id=r['organization_id'],
                    department_id=r['department_id'],
                    email=r['email'],
                    role=r['role'],
                    invite_token=r['invite_token'],
                    expires_at=r['expires_at'],
                    status=r['status'],
                    created_at=r['created_at']
                )
                for r in rows
            ]

    def accept_invitation(self, token: str, user_id: str) -> bool:
        """Accept an invitation token and link user to target organization and department."""
        inv = self.get_invitation_by_token(token)
        if not inv or inv.status != "PENDING":
            return False

        now_iso = datetime.now().isoformat()
        if inv.expires_at and inv.expires_at < now_iso:
            with self._get_connection() as conn:
                conn.execute("UPDATE org_invitations SET status = 'EXPIRED' WHERE id = ?", (inv.id,))
                conn.commit()
            return False

        if inv.department_id:
            self.add_user_to_department(inv.department_id, user_id, role=inv.role or "OPERATOR")

        with self._get_connection() as conn:
            conn.execute("UPDATE org_invitations SET status = 'ACCEPTED' WHERE id = ?", (inv.id,))
            conn.commit()
        return True

    def bulk_invite_to_department(
        self,
        organization_id: str,
        department_id: str,
        emails: List[str],
        role: str = "OPERATOR",
        expires_in_days: int = 7
    ) -> List[OrgInvitation]:
        """Bulk issue department invitations to a list of email addresses."""
        invitations: List[OrgInvitation] = []
        for em in emails:
            clean = normalize_email(em)
            if clean:
                inv = self.create_org_invitation(
                    organization_id=organization_id,
                    email=clean,
                    department_id=department_id,
                    role=role,
                    expires_in_days=expires_in_days
                )
                invitations.append(inv)
        return invitations

    def onboard_user_by_email(
        self,
        organization_id: str,
        email: str,
        full_name: str,
        password_hash: Optional[str] = None,
        role: str = "MEMBER"
    ) -> Tuple[User, List[DepartmentMember]]:
        """
        Just-In-Time (JIT) automated robotic user onboarding.
        """
        clean_email = normalize_email(email)
        now_iso = datetime.now().isoformat()

        user = self.get_user_by_email(clean_email)
        if not user:
            user_id = f"usr_{uuid.uuid4().hex[:12]}"
            user = self.create_user(
                id=user_id,
                organization_id=organization_id,
                email=clean_email,
                full_name=full_name,
                role=role,
                status="ACTIVE",
                password_hash=password_hash
            )
        else:
            self.update_user(user.id, last_login_at=now_iso)

        pending_invites = self.list_pending_invitations_for_email(clean_email)
        joined_depts: List[DepartmentMember] = []
        for inv in pending_invites:
            if inv.department_id:
                dm = self.add_user_to_department(
                    department_id=inv.department_id,
                    user_id=user.id,
                    role=inv.role or "OPERATOR"
                )
                joined_depts.append(dm)
            with self._get_connection() as conn:
                conn.execute("UPDATE org_invitations SET status = 'ACCEPTED' WHERE id = ?", (inv.id,))
                conn.commit()

        return user, joined_depts
