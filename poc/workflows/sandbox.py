"""
Sandbox Isolation Manager:
Manages isolated execution environments for workflow steps.
Supports:
1. Docker Container Sandbox (when docker is installed and running on host).
2. Ephemeral Worktree / Isolated Directory Sandbox (fallback when Docker daemon is unavailable).
Ensures zero artifact leakage and clean lifecycle cleanup.
"""

import os
import shutil
import tempfile
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


@dataclass
class SandboxSession:
    """Represents an active or completed sandbox environment."""
    session_id: str
    sandbox_type: str  # 'DOCKER' or 'EPHEMERAL_DIR'
    path: str
    container_id: Optional[str] = None
    is_active: bool = True

    def cleanup(self):
        """Clean up the sandbox files and/or containers."""
        if not self.is_active:
            return

        if self.sandbox_type == "DOCKER" and self.container_id:
            try:
                subprocess.run(["docker", "rm", "-f", self.container_id], capture_output=True, check=False)
            except Exception as e:
                logger.warning(f"Failed to remove docker container {self.container_id}: {e}")

        # Clean up local temporary directory if created
        if self.path and os.path.exists(self.path):
            try:
                shutil.rmtree(self.path, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to clean up sandbox dir {self.path}: {e}")

        self.is_active = False


class SandboxManager:
    """Manages the creation, isolation, and teardown of execution sandboxes."""

    def __init__(self, base_sandboxes_dir: Optional[str] = None):
        self.base_dir = Path(base_sandboxes_dir) if base_sandboxes_dir else Path(tempfile.gettempdir()) / "ai_agents_sandboxes"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._docker_available: Optional[bool] = None

    def is_docker_available(self) -> bool:
        """Check if Docker CLI and daemon are responsive on host."""
        if self._docker_available is not None:
            return self._docker_available
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=3, check=False)
            self._docker_available = (res.returncode == 0)
        except Exception:
            self._docker_available = False
        return self._docker_available

    def create_sandbox(
        self,
        execution_id: str,
        source_workspace: Optional[str] = None,
        force_type: Optional[str] = None
    ) -> SandboxSession:
        """
        Create a secure ephemeral sandbox for a workflow execution.
        If Docker is available or forced, spins up a Docker-backed sandbox.
        Otherwise falls back to an isolated ephemeral workspace directory.
        """
        sandbox_dir = self.base_dir / f"run_{execution_id}"
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Clone or copy source workspace files if provided
        if source_workspace and os.path.exists(source_workspace):
            try:
                # Copy files ignoring git metadata or temp directories
                for item in os.listdir(source_workspace):
                    if item in (".git", "node_modules", "__pycache__", ".venv", ".pytest_cache"):
                        continue
                    s = os.path.join(source_workspace, item)
                    d = os.path.join(str(sandbox_dir), item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
            except Exception as e:
                logger.warning(f"Failed to copy source workspace into sandbox: {e}")

        use_docker = (force_type == "DOCKER") or (force_type is None and self.is_docker_available())

        if use_docker:
            container_id = None
            try:
                # Start an isolated container mounting the sandbox directory
                c_name = f"sandbox_{execution_id}"
                cmd = [
                    "docker", "run", "-d",
                    "--name", c_name,
                    "-v", f"{str(sandbox_dir.resolve())}:/workspace",
                    "-w", "/workspace",
                    "alpine:latest",
                    "tail", "-f", "/dev/null"
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if proc.returncode == 0:
                    container_id = proc.stdout.strip()
                    return SandboxSession(
                        session_id=execution_id,
                        sandbox_type="DOCKER",
                        path=str(sandbox_dir),
                        container_id=container_id,
                        is_active=True
                    )
            except Exception as e:
                logger.warning(f"Docker sandbox startup failed, falling back to ephemeral directory: {e}")

        # Fallback to ephemeral directory sandbox
        return SandboxSession(
            session_id=execution_id,
            sandbox_type="EPHEMERAL_DIR",
            path=str(sandbox_dir),
            container_id=None,
            is_active=True
        )
