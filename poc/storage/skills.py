"""Skills persistence operations."""
from config import Skill
from datetime import datetime


def migrate_skill_ownership(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(skills)")}
    if "organization_id" not in columns:
        conn.execute("ALTER TABLE skills ADD COLUMN organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE")
        conn.execute("""
            UPDATE skills SET organization_id = CASE WHEN project_id IS NOT NULL
                THEN (SELECT o.id FROM projects p JOIN organizations o ON o.id = p.organization_id
                      WHERE p.id = skills.project_id
                        AND NOT EXISTS (SELECT 1 FROM access_resource_owners a
                            WHERE a.resource_type='skill' AND a.resource_id=skills.id
                                AND a.organization_id<>o.id))
                ELSE (SELECT o.id FROM access_resource_owners a JOIN organizations o ON o.id = a.organization_id
                      WHERE a.resource_type = 'skill' AND a.resource_id = skills.id)
            END
        """)
    if "is_system" not in columns:
        conn.execute("ALTER TABLE skills ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_skills_org ON skills(organization_id)")


class SkillsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def save_skill(self, skill: Skill, *, create_only=False):
        """Insert a skill or update it within the owning scope."""
        conflict = "" if create_only else """
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, description=excluded.description,
                content=excluded.content, project_id=excluded.project_id, updated_at=excluded.updated_at
            WHERE skills.organization_id IS excluded.organization_id AND skills.is_system = excluded.is_system
        """
        with self._get_connection() as conn:
            return conn.execute("""
                INSERT INTO skills
                (id, name, description, content, project_id, organization_id, is_system, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """ + conflict, (
                skill.id, skill.name, skill.description, skill.content, skill.project_id,
                skill.organization_id, skill.is_system, datetime.now(),
            )).rowcount == 1

    def update_skill(self, skill: Skill):
        with self._get_connection() as conn:
            return conn.execute("""
                UPDATE skills SET name=?, description=?, content=?, project_id=?, updated_at=?
                WHERE id=? AND organization_id=? AND is_system=0
            """, (skill.name, skill.description, skill.content, skill.project_id, datetime.now(),
                  skill.id, skill.organization_id)).rowcount == 1

    @staticmethod
    def _row_to_skill(row) -> Skill:
        return Skill(
            id=row['id'], name=row['name'], description=row['description'], content=row['content'],
            project_id=row['project_id'], organization_id=row['organization_id'], is_system=bool(row['is_system']),
        )

    def get_skill(self, skill_id: str, *, organization_id=None):
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM skills WHERE id=? AND
                (organization_id IS ? OR (organization_id IS NULL AND is_system=1 AND project_id IS NULL))
            """, (skill_id, organization_id)).fetchone()
            return self._row_to_skill(row) if row else None

    def list_skills(self, project_id=None, *, organization_id=None):
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM skills WHERE
                (organization_id IS ? OR (organization_id IS NULL AND is_system=1 AND project_id IS NULL))
                AND (? IS NULL OR project_id IS NULL OR project_id=?) ORDER BY name
            """, (organization_id, project_id, project_id))
            return [self._row_to_skill(row) for row in rows]

    def delete_skill(self, skill_id: str, *, organization_id=None):
        with self._get_connection() as conn:
            return conn.execute(
                "DELETE FROM skills WHERE id=? AND organization_id IS ? AND is_system=0",
                (skill_id, organization_id),
            ).rowcount == 1
