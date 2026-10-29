"""Templates persistence operations; dependencies are injected callbacks."""
from config import AgentTemplate
from datetime import datetime
from typing import List, Optional
import json
import sqlite3


class TemplatesRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def _row_to_template(self, row: sqlite3.Row) -> AgentTemplate:
        """Convert a database row to an AgentTemplate instance."""
        return AgentTemplate(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            role=row['role'],
            system_prompt=row['system_prompt'],
            model=row['model'] or 'default',
            skills=json.loads(row['skills']) if row['skills'] else [],
            tools=json.loads(row['tools']) if row['tools'] else [],
            suggested_children=json.loads(row['suggested_children']) if row['suggested_children'] else [],
            category=row['category'] or 'Engineering',
            created_at=str(row['created_at']) if 'created_at' in row.keys() and row['created_at'] else None,
            updated_at=str(row['updated_at']) if 'updated_at' in row.keys() and row['updated_at'] else None
        )

    def save_template(self, template: AgentTemplate) -> AgentTemplate:
        """Save or update an agent template."""
        with self._get_connection() as conn:
            now = datetime.now().isoformat()
            existing = conn.execute("SELECT created_at FROM agent_templates WHERE id = ?", (template.id,)).fetchone()
            created_at = existing['created_at'] if existing else (template.created_at or now)
            updated_at = now

            conn.execute("""
                INSERT INTO agent_templates
                (id, name, description, role, system_prompt, model, skills, tools, suggested_children, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    role=excluded.role,
                    system_prompt=excluded.system_prompt,
                    model=excluded.model,
                    skills=excluded.skills,
                    tools=excluded.tools,
                    suggested_children=excluded.suggested_children,
                    category=excluded.category,
                    updated_at=excluded.updated_at
            """, (
                template.id,
                template.name,
                template.description,
                template.role,
                template.system_prompt,
                template.model,
                json.dumps(template.skills),
                json.dumps(template.tools),
                json.dumps(template.suggested_children),
                template.category,
                str(created_at),
                str(updated_at)
            ))
            conn.commit()
            return self.get_template(template.id) or template

    def get_template(self, template_id: str) -> Optional[AgentTemplate]:
        """Get an agent template by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agent_templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_template(row)
        return None

    def list_templates(self, category: Optional[str] = None) -> List[AgentTemplate]:
        """List agent templates, optionally filtered by category."""
        with self._get_connection() as conn:
            if category:
                cursor = conn.execute("SELECT * FROM agent_templates WHERE category = ? ORDER BY name", (category,))
            else:
                cursor = conn.execute("SELECT * FROM agent_templates ORDER BY name")
            return [self._row_to_template(row) for row in cursor.fetchall()]

    def delete_template(self, template_id: str) -> bool:
        """Delete an agent template."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM agent_templates WHERE id = ?", (template_id,))
            conn.commit()
            return cursor.rowcount > 0
