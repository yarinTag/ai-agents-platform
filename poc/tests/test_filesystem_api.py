"""
Tests for filesystem browsing and project folder picker API.
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

from poc.backend.main import app

client = TestClient(app)


def test_browse_directory_default():
    """Verify that browse endpoint returns current directory and quick access."""
    response = client.get("/api/v1/fs/browse")
    assert response.status_code == 200
    data = response.json()

    assert "current_path" in data
    assert "folders" in data
    assert "quick_access" in data
    assert len(data["quick_access"]) > 0
    assert any(q["name"] == "Home" for q in data["quick_access"])


def test_browse_directory_detects_project(tmp_path):
    """Verify that browse endpoint correctly flags directories with project markers."""
    # Create sample subdirectories
    proj_dir = tmp_path / "my_python_project"
    proj_dir.mkdir()
    (proj_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")

    regular_dir = tmp_path / "plain_folder"
    regular_dir.mkdir()

    response = client.get(f"/api/v1/fs/browse?path={str(tmp_path)}")
    assert response.status_code == 200
    data = response.json()

    assert data["current_path"] == str(tmp_path.resolve())
    folders = {f["name"]: f for f in data["folders"]}

    assert "my_python_project" in folders
    assert folders["my_python_project"]["is_project"] is True
    assert folders["my_python_project"]["project_type"] == "Python"

    assert "plain_folder" in folders
    assert folders["plain_folder"]["is_project"] is False


def test_pick_folder_structure():
    """Verify pick-folder endpoint schema and response structure without hanging."""
    # When initial_path is provided, test request
    # If platform dialog is not interactive or cancelled, response must be structured
    response = client.post("/api/v1/fs/pick-folder", json={"initial_path": "/tmp"})
    assert response.status_code == 200
    data = response.json()
    assert "cancelled" in data
    assert "path" in data
    assert "is_project" in data
