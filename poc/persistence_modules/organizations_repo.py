"""
Organizations & Departments Repository Mixin.
Handles multi-tenant organizations, departments, and monthly budget enforcement.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import Organization, Department


class OrganizationsRepositoryMixin:
    """Mixin providing organization and department persistence operations."""

    def create_department(
        self,
        id: str,
        name: str,
        description: Optional[str] = None,
        monthly_budget_usd: float = 100.0,
        budget_action: str = "HARD_STOP",
        alert_threshold_pct: float = 80.0,
        organization_id: Optional[str] = None
    ) -> Department:
        """Create a new department."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO departments (id, name, description, monthly_budget_usd, budget_action, alert_threshold_pct, organization_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (id, name, description, monthly_budget_usd, budget_action, alert_threshold_pct, organization_id, now, now))
            conn.commit()
        return self.get_department(id)

    def get_department(self, id: str) -> Optional[Department]:
        """Fetch a department by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM departments WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            return Department(
                id=d['id'],
                name=d['name'],
                description=d.get('description'),
                monthly_budget_usd=float(d.get('monthly_budget_usd') or 100.0),
                current_spend_usd=self.get_department_monthly_spend(id),
                budget_action=d.get('budget_action') or 'HARD_STOP',
                alert_threshold_pct=float(d.get('alert_threshold_pct') or 80.0),
                organization_id=d.get('organization_id'),
                created_at=d.get('created_at'),
                updated_at=d.get('updated_at')
            )

    def list_departments(self) -> List[Department]:
        """List all departments."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id FROM departments ORDER BY name ASC").fetchall()
            return [self.get_department(r['id']) for r in rows if r['id']]

    def update_department(self, id: str, **kwargs) -> Optional[Department]:
        """Update department configuration."""
        fields = []
        params = []
        now = datetime.now().isoformat()
        for k in ("name", "description", "monthly_budget_usd", "budget_action", "alert_threshold_pct"):
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?")
                params.append(kwargs[k])
        if fields:
            fields.append("updated_at = ?")
            params.append(now)
            params.append(id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE departments SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_department(id)

    def get_department_monthly_spend(self, department_id: str, year: Optional[int] = None, month: Optional[int] = None) -> float:
        """Calculate actual monthly spend for a department."""
        now = datetime.now()
        y = year or now.year
        m = month or now.month
        month_prefix = f"{y:04d}-{m:02d}%"

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT COALESCE(SUM(total_cost_usd), 0.0) as total
                FROM workflow_executions
                WHERE department_id = ?
                  AND created_at LIKE ?
            """, (department_id, month_prefix))
            row = cursor.fetchone()
            return float(row['total']) if row else 0.0

    def check_department_budget(self, department_id: str, requested_cost: float = 0.0) -> Dict[str, Any]:
        """Check department budget limits against monthly spend."""
        dept = self.get_department(department_id)
        if not dept:
            return {"allowed": True, "reason": "No department limit"}

        current_spend = dept.current_spend_usd
        budget = dept.monthly_budget_usd

        if (current_spend + requested_cost) >= budget:
            return {
                "allowed": False,
                "action": dept.budget_action,
                "department_id": department_id,
                "current_spend_usd": current_spend,
                "monthly_budget_usd": budget,
                "message": f"Department '{dept.name}' exceeded monthly budget (${current_spend:.2f}/${budget:.2f}). Additional budget required."
            }

        is_alert = (current_spend / budget) * 100.0 >= dept.alert_threshold_pct if budget > 0 else False
        return {
            "allowed": True,
            "department_id": department_id,
            "current_spend_usd": current_spend,
            "monthly_budget_usd": budget,
            "is_alert": is_alert
        }

    def create_organization(
        self,
        id: str,
        name: str,
        slug: str,
        domain: Optional[str] = None,
        settings_json: str = "{}"
    ) -> Organization:
        """Create an organization tenant."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO organizations (id, name, slug, domain, settings_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (id, name, slug, domain, settings_json, now, now))
            conn.commit()
        return self.get_organization(id)

    def get_organization(self, id: str) -> Optional[Organization]:
        """Get an organization by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            return Organization(
                id=row['id'],
                name=row['name'],
                slug=row['slug'],
                domain=row['domain'],
                settings_json=row['settings_json'] or "{}",
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

    def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Get an organization by slug."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE slug = ?", (slug,)).fetchone()
            if not row:
                return None
            return Organization(
                id=row['id'],
                name=row['name'],
                slug=row['slug'],
                domain=row['domain'],
                settings_json=row['settings_json'] or "{}",
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

    def list_organizations(self) -> List[Organization]:
        """List all organizations."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM organizations ORDER BY name ASC").fetchall()
            return [
                Organization(
                    id=r['id'],
                    name=r['name'],
                    slug=r['slug'],
                    domain=r['domain'],
                    settings_json=r['settings_json'] or "{}",
                    created_at=r['created_at'],
                    updated_at=r['updated_at']
                )
                for r in rows
            ]

    def update_organization(self, id: str, **kwargs) -> Optional[Organization]:
        """Update organization attributes."""
        fields = []
        params = []
        now = datetime.now().isoformat()
        for k in ("name", "slug", "domain", "settings_json"):
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?")
                params.append(kwargs[k])
        if fields:
            fields.append("updated_at = ?")
            params.append(now)
            params.append(id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE organizations SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_organization(id)
