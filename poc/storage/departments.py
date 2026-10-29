"""Departments persistence operations; dependencies are injected callbacks."""
from .records import Department
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


class DepartmentsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def create_department(
        self,
        id: Optional[str] = None,
        name: str = "",
        description: Optional[str] = None,
        monthly_budget_usd: float = 100.0,
        budget_action: str = "HARD_STOP",
        alert_threshold_pct: float = 80.0,
        organization_id: Optional[str] = None
    ) -> Department:
        """Create a new department."""
        if not id:
            id = f"dept_{uuid.uuid4().hex[:10]}"
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

    def list_departments(self, organization_id: Optional[str] = None) -> List[Department]:
        """List all departments, optionally filtered by organization_id."""
        with self._get_connection() as conn:
            if organization_id:
                rows = conn.execute(
                    "SELECT id FROM departments WHERE organization_id = ? ORDER BY name ASC",
                    (organization_id,)
                ).fetchall()
            else:
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
        """
        Calculate actual monthly spend for a department.
        Per user decision: ONLY enforces and counts runs using API keys (cost_source='API_KEY').
        Subscription CLI runs are zero-billed against the budget.
        """
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
        """
        Check department budget limits against monthly spend.
        Action: HARD_STOP (per user decision) when spend >= monthly_budget_usd.
        """
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
