"""Skills persistence operations; dependencies are injected callbacks."""
from config import Skill
from datetime import datetime
from typing import List, Optional


class SkillsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def save_skill(self, skill: Skill):
        """Save or update a skill."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO skills
                (id, name, description, content, project_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                skill.id,
                skill.name,
                skill.description,
                skill.content,
                skill.project_id,
                datetime.now()
            ))
            conn.commit()

    @staticmethod
    def _row_to_skill(row) -> Skill:
        """Canonical record conversion; malformed stored JSON retains its original error behavior."""
        return Skill(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            content=row['content'],
            project_id=row['project_id'],
        )

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM skills WHERE id = ?", (skill_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_skill(row)
        return None

    def list_skills(self, project_id: Optional[str] = None) -> List[Skill]:
        """List skills, optionally filtered by project."""
        with self._get_connection() as conn:
            if project_id is not None:
                cursor = conn.execute(
                    "SELECT * FROM skills WHERE project_id = ? OR project_id IS NULL ORDER BY name",
                    (project_id,)
                )
            else:
                cursor = conn.execute("SELECT * FROM skills ORDER BY name")
            return [
                self._row_to_skill(row)
                for row in cursor.fetchall()
            ]

    def delete_skill(self, skill_id: str):
        """Delete a skill."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
            conn.commit()
