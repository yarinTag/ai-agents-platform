"""Settings persistence operations; dependencies are injected callbacks."""
from datetime import datetime
from typing import Optional


class SettingsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Read a platform setting, returning `default` when unset."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM platform_settings WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            return row['value'] if row else default

    def set_setting(self, key: str, value: Optional[str]):
        """Upsert a platform setting."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO platform_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (key, value, datetime.now()))
            conn.commit()

    def delete_setting(self, key: str):
        """Remove a platform setting."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM platform_settings WHERE key = ?", (key,))
            conn.commit()
