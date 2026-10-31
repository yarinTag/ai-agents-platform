"""Pytest plugin (loaded via addopts, even with --noconftest): test-only security environment.

The application refuses to start without JWT_SECRET_KEY. Tests use dev mode, which signs
tokens with a random per-process key, so no shared secret is ever committed.
"""
import os

os.environ.setdefault("PLATFORM_DEV_MODE", "1")
