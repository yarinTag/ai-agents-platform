"""SQLite connection ownership, transaction boundaries and self-healing lifecycle."""
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import sqlite3


class ConnectionStore:
    def __init__(self, db_path, initialize_tables):
        self.db_path = Path(db_path)
        self._initialize_tables = initialize_tables
        self._initializing_db = False
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self):
        self._initializing_db = True
        try:
            self._initialize_tables()
        finally:
            self._initializing_db = False

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """
        Yield a database connection, then always close it.
        Automatically recreates parent directory and schema if the DB file was removed at runtime.
        """
        db_missing = not self.db_path.exists()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_missing and not getattr(self, "_initializing_db", False):
            self.initialize()

        conn = sqlite3.connect(self.db_path)
        try:
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            # Enable WAL mode for better concurrent access
            conn.execute("PRAGMA journal_mode = WAL")
            # Enable busy timeout (5000ms) to prevent immediate locking errors
            conn.execute("PRAGMA busy_timeout = 5000")
            # Return rows as dictionaries
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            except BaseException:
                conn.rollback()
                raise
            else:
                conn.commit()
        finally:
            conn.close()
