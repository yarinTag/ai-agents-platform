"""
PostgreSQL Enterprise Multi-Tenant Adapter with Row-Level Security (RLS) enforcement.
"""

import os
import logging
from typing import Optional, Dict, Any, Iterator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PostgresRLSManager:
    """
    Manages PostgreSQL connections with dynamic RLS tenant context injection:
    `SET LOCAL app.current_org_id = '<org_id>'`.
    """

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/agents_platform"
        )
        self._pool = None

    def is_available(self) -> bool:
        """Checks if PostgreSQL driver is available and URL is configured."""
        try:
            import psycopg2
            return bool(self.database_url and (
                self.database_url.startswith("postgresql://") or
                self.database_url.startswith("postgres://")
            ))
        except ImportError:
            return False

    @contextmanager
    def get_scoped_connection(self, organization_id: Optional[str] = None):
        """
        Yields a PostgreSQL connection with Row-Level Security context set.
        """
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
        try:
            if organization_id:
                with conn.cursor() as cur:
                    # Parameterized set_config to prevent SQL injection
                    cur.execute("SELECT set_config('app.current_org_id', %s, false);", (organization_id,))
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def run_migrations(self, sql_path: Optional[str] = None):
        """Executes the DDL & RLS schema script."""
        if not self.is_available():
            logger.warning("PostgreSQL driver not available; skipping RLS DDL execution.")
            return

        import psycopg2
        path = sql_path or os.path.join(os.path.dirname(__file__), "init_postgres_rls.sql")
        if not os.path.exists(path):
            logger.warning(f"SQL file not found at {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        try:
            with psycopg2.connect(self.database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_script)
                conn.commit()
            logger.info("Successfully executed PostgreSQL RLS enterprise schema migrations.")
        except Exception as e:
            logger.error(f"PostgreSQL migration error: {e}")
