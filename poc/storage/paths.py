"""Canonical locations, independent of storage package depth."""
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = POC_ROOT / "data" / "agents_platform.db"
