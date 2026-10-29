"""Users persistence operations; dependencies are injected callbacks."""
from .records import DepartmentMember, User
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


class UsersRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

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
        clean_email = email.strip().lower()
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

    @staticmethod
    def _row_to_user(row) -> User:
        """Single persisted record mapping for get/list queries."""
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
            last_login_at=row['last_login_at'],
        )

    def get_user(self, id: str) -> Optional[User]:
        """Get an enterprise user by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get an enterprise user by normalized email."""
        clean_email = email.strip().lower()
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (clean_email,)).fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def list_users_by_organization(self, organization_id: str) -> List[User]:
        """List all users belonging to an enterprise organization."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM users WHERE organization_id = ? ORDER BY created_at ASC
            """, (organization_id,)).fetchall()
            return [
                self._row_to_user(r)
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
