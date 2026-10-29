"""Projects persistence operations; dependencies are injected callbacks."""
from config import ProjectConfig
from datetime import datetime
from typing import List, Optional
import json


class ProjectsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def save_project(self, project: ProjectConfig):
        """Save or update a project."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO projects
                (id, name, description, working_directory, instructions, skills, allowed_tools, updated_at, organization_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    working_directory=excluded.working_directory,
                    instructions=excluded.instructions,
                    skills=excluded.skills,
                    allowed_tools=excluded.allowed_tools,
                    updated_at=excluded.updated_at,
                    organization_id=COALESCE(excluded.organization_id, projects.organization_id)
            """, (
                project.id,
                project.name,
                project.description,
                project.working_directory,
                project.instructions,
                json.dumps(project.skills),
                json.dumps(project.allowed_tools),
                datetime.now(),
                getattr(project, "organization_id", None)
            ))
            conn.commit()

    @staticmethod
    def _row_to_project(row) -> ProjectConfig:
        """Canonical record conversion; malformed stored JSON retains its original error behavior."""
        return ProjectConfig(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            working_directory=row['working_directory'],
            instructions=row['instructions'],
            skills=json.loads(row['skills']) if row['skills'] else [],
            allowed_tools=json.loads(row['allowed_tools']) if row['allowed_tools'] else [],
            organization_id=row['organization_id'] if 'organization_id' in row.keys() else None,
        )

    def get_project(self, project_id: str) -> Optional[ProjectConfig]:
        """Get a project by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_project(row)
        return None

    def list_projects(self, organization_id: Optional[str] = None) -> List[ProjectConfig]:
        """List all projects, optionally scoped by organization."""
        with self._get_connection() as conn:
            if organization_id:
                cursor = conn.execute(
                    "SELECT * FROM projects WHERE organization_id = ? ORDER BY name",
                    (organization_id,)
                )
            else:
                cursor = conn.execute("SELECT * FROM projects ORDER BY name")
            return [
                self._row_to_project(row)
                for row in cursor.fetchall()
            ]

    def delete_project(self, project_id: str):
        """Delete a project."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
