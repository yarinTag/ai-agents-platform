"""Organizations persistence operations; dependencies are injected callbacks."""
from .records import Organization
from datetime import datetime
from typing import List, Optional
import json


class OrganizationsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def _row_to_organization(self, row) -> Organization:
        settings_str = row['settings_json'] or "{}"
        source_mode = "local"
        git_repo = None
        local_path = None
        keys = row.keys() if hasattr(row, 'keys') else []
        try:
            if 'plugins_source_mode' in keys and row['plugins_source_mode']:
                source_mode = row['plugins_source_mode']
            if 'plugins_git_repo' in keys:
                git_repo = row['plugins_git_repo']
            if 'plugins_local_path' in keys:
                local_path = row['plugins_local_path']
        except Exception:
            pass

        # Backwards compatibility sync with settings_json only if column is None
        try:
            settings_dict = json.loads(settings_str)
            if git_repo is None and "plugins_git_repo" in settings_dict:
                git_repo = settings_dict.get("plugins_git_repo")
            if local_path is None and "plugins_local_path" in settings_dict:
                local_path = settings_dict.get("plugins_local_path")
            if source_mode == "local" and settings_dict.get("plugins_source_mode"):
                source_mode = settings_dict.get("plugins_source_mode")
        except Exception:
            pass

        return Organization(
            id=row['id'],
            name=row['name'],
            slug=row['slug'],
            domain=row['domain'],
            settings_json=settings_str,
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            plugins_source_mode=source_mode or "local",
            plugins_git_repo=git_repo or "",
            plugins_local_path=local_path or ""
        )

    def create_organization(
        self,
        id: str,
        name: str,
        slug: str,
        domain: Optional[str] = None,
        settings_json: str = "{}",
        plugins_source_mode: str = "local",
        plugins_git_repo: Optional[str] = None,
        plugins_local_path: Optional[str] = None
    ) -> Organization:
        """Create an organization tenant."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO organizations (id, name, slug, domain, settings_json, plugins_source_mode, plugins_git_repo, plugins_local_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (id, name, slug, domain, settings_json, plugins_source_mode, plugins_git_repo, plugins_local_path, now, now))
            conn.commit()
        return self.get_organization(id)

    def get_organization(self, id: str) -> Optional[Organization]:
        """Get an organization by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            return self._row_to_organization(row)

    def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Get an organization by slug."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE slug = ?", (slug,)).fetchone()
            if not row:
                return None
            return self._row_to_organization(row)

    def list_organizations(self) -> List[Organization]:
        """List all organizations."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM organizations ORDER BY name ASC").fetchall()
            return [self._row_to_organization(r) for r in rows]

    def update_organization(self, id: str, **kwargs) -> Optional[Organization]:
        """Update organization attributes."""
        fields = []
        params = []
        now = datetime.now().isoformat()

        # Sync settings_json if plugins attributes are updated
        current = self.get_organization(id)
        if current:
            try:
                s_dict = json.loads(current.settings_json or "{}")
            except Exception:
                s_dict = {}
            if "plugins_source_mode" in kwargs and kwargs["plugins_source_mode"] is not None:
                s_dict["plugins_source_mode"] = kwargs["plugins_source_mode"]
            if "plugins_git_repo" in kwargs:
                s_dict["plugins_git_repo"] = kwargs["plugins_git_repo"] or ""
            if "plugins_local_path" in kwargs:
                s_dict["plugins_local_path"] = kwargs["plugins_local_path"] or ""
            if "settings_json" not in kwargs:
                kwargs["settings_json"] = json.dumps(s_dict)

        for k in ("name", "slug", "domain", "settings_json", "plugins_source_mode"):
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?")
                params.append(kwargs[k])
        for k in ("plugins_git_repo", "plugins_local_path"):
            if k in kwargs:
                fields.append(f"{k} = ?")
                params.append(kwargs[k] or "")
        if fields:
            fields.append("updated_at = ?")
            params.append(now)
            params.append(id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE organizations SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_organization(id)
