"""Invitations persistence operations; dependencies are injected callbacks."""
from .records import DepartmentMember, OrgInvitation, User
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import secrets
import uuid


class InvitationsRepository:
    def __init__(self, connection_factory, add_user_to_department, create_user, get_user_by_email, update_user):
        self._get_connection = connection_factory
        self.add_user_to_department = add_user_to_department
        self.create_user = create_user
        self.get_user_by_email = get_user_by_email
        self.update_user = update_user

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
        clean_email = email.strip().lower()

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

    @staticmethod
    def _row_to_invitation(row) -> OrgInvitation:
        """Single persisted record mapping for get/list queries."""
        return OrgInvitation(
            id=row['id'],
            organization_id=row['organization_id'],
            department_id=row['department_id'],
            email=row['email'],
            role=row['role'],
            invite_token=row['invite_token'],
            expires_at=row['expires_at'],
            status=row['status'],
            created_at=row['created_at'],
        )

    def get_invitation_by_token(self, token: str) -> Optional[OrgInvitation]:
        """Fetch an invitation by token."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM org_invitations WHERE invite_token = ?", (token,)).fetchone()
            if not row:
                return None
            return self._row_to_invitation(row)

    def list_pending_invitations_for_email(self, email: str) -> List[OrgInvitation]:
        """Fetch active pending invitations for a specific email."""
        clean_email = email.strip().lower()
        now_iso = datetime.now().isoformat()
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM org_invitations
                WHERE LOWER(email) = LOWER(?) AND status = 'PENDING' AND expires_at > ?
            """, (clean_email, now_iso)).fetchall()
            return [
                self._row_to_invitation(r)
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
            clean = em.strip().lower()
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
        Just-In-Time (JIT) automated robotic user onboarding:
        1. Creates user if not existing, or loads existing user.
        2. Detects any pending invitations for this email.
        3. Auto-links user to target departments and consumes invitations.
        4. Updates last_login_at.
        """
        clean_email = email.strip().lower()
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
