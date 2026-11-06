"""
Filesystem exploration and directory picker API endpoints.
Provides local directory browsing, project detection, and OS dialog triggers.
"""

import os
import sys
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

router = APIRouter()


class FolderItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    path: str
    is_project: bool = False
    project_type: Optional[str] = None
    has_children: bool = False


class QuickAccessItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    path: str
    icon: Optional[str] = None


class BrowseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    current_path: str
    parent_path: Optional[str] = None
    name: str
    is_root: bool
    quick_access: List[QuickAccessItem]
    folders: List[FolderItem]


class PickFolderRequest(BaseModel):
    initial_path: Optional[str] = None


class PickFolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    path: Optional[str] = None
    name: Optional[str] = None
    is_project: bool = False
    project_type: Optional[str] = None
    cancelled: bool = False
    error: Optional[str] = None


def detect_project(directory: Path) -> Tuple[bool, Optional[str]]:
    """Detect if a directory is a software project and its primary type."""
    try:
        if not directory.is_dir():
            return False, None

        indicators = [
            (".git", "Git Repository"),
            ("package.json", "Node.js / Web"),
            ("pyproject.toml", "Python"),
            ("requirements.txt", "Python"),
            ("setup.py", "Python"),
            ("Cargo.toml", "Rust"),
            ("go.mod", "Go"),
            ("pom.xml", "Java / Maven"),
            ("build.gradle", "Java / Gradle"),
            ("Gemfile", "Ruby"),
            ("composer.json", "PHP"),
            ("Makefile", "C / Make"),
            ("CMakeLists.txt", "CMake"),
            ("docker-compose.yml", "Docker"),
            ("CLAUDE.md", "Agent Project"),
            ("GEMINI.md", "Agent Project"),
        ]

        for marker, p_type in indicators:
            target = directory / marker
            if target.exists():
                return True, p_type

        return False, None
    except (PermissionError, OSError):
        return False, None


def get_quick_access() -> List[QuickAccessItem]:
    """Retrieve verified quick-access directories on the user machine."""
    items: List[QuickAccessItem] = []
    seen_paths = set()

    def add_if_exists(name: str, p: Path, icon: str):
        try:
            resolved = p.resolve()
            p_str = str(resolved)
            if resolved.exists() and resolved.is_dir() and p_str not in seen_paths:
                items.append(QuickAccessItem(name=name, path=p_str, icon=icon))
                seen_paths.add(p_str)
        except (PermissionError, OSError):
            pass

    home = Path.home()
    add_if_exists("Home", home, "home")
    add_if_exists("Desktop", home / "Desktop", "desktop")
    add_if_exists("Documents", home / "Documents", "document")
    add_if_exists("Downloads", home / "Downloads", "download")

    # Common development / project directories
    dev_candidates = [
        home / "Projects",
        home / "Desktop" / "Projects",
        home / "Development",
        home / "workspace",
        home / "code",
        home / "repos",
    ]
    for cand in dev_candidates:
        if cand.exists():
            add_if_exists(cand.name, cand, "code")

    # Current working directory / workspace
    add_if_exists("Current Workspace", Path.cwd(), "folder")

    return items


@router.get("/browse", response_model=BrowseResponse)
async def browse_directory(request: Request, path: Optional[str] = Query(None, description="Directory path to inspect")):
    """
    Browse directories on the local machine and detect project structures.
    """
    from runtime.tenant_workspace import tenant_root
    root = (tenant_root(request.state.access_actor.organization_id) / "shared").resolve()
    target_path = Path(path.strip()).expanduser().resolve() if path and path.strip() else root
    if not target_path.is_relative_to(root):
        raise HTTPException(403, "Directory is outside authorized tenant storage.")
    if not target_path.exists() or not target_path.is_dir():
        raise HTTPException(404, "Tenant directory not found.")
    parent = target_path.parent
    is_root = target_path == root
    parent_path_str = None if is_root else str(parent)

    folders: List[FolderItem] = []
    try:
        for entry in target_path.iterdir():
            # Skip hidden files and common system noise
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_dir() and entry.resolve().is_relative_to(root):
                    is_proj, p_type = detect_project(entry)
                    has_children = False
                    try:
                        # Quick check if it has any subdirectories
                        has_children = any(c.is_dir() for c in entry.iterdir() if not c.name.startswith("."))
                    except (PermissionError, OSError):
                        pass

                    folders.append(FolderItem(
                        name=entry.name,
                        path=str(entry.resolve()),
                        is_project=is_proj,
                        project_type=p_type,
                        has_children=has_children
                    ))
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError) as e:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to directory: {str(e)}"
        )

    # Sort folders alphabetically case-insensitive, with projects listed first
    folders.sort(key=lambda f: (not f.is_project, f.name.lower()))

    return BrowseResponse(
        current_path=str(target_path),
        parent_path=parent_path_str,
        name=target_path.name or str(target_path),
        is_root=is_root,
        quick_access=[QuickAccessItem(name="Organization files", path=str(root), icon="folder")],
        folders=folders
    )


@router.post("/pick-folder", response_model=PickFolderResponse)
async def pick_folder_native(req: Optional[PickFolderRequest] = None):
    """
    Trigger native operating system folder selection dialog (macOS, Windows, Linux).
    Runs asynchronously in worker thread to prevent blocking the event loop.
    Returns chosen path, project metadata, or cancellation status.
    """
    if os.getenv("PYTEST_CURRENT_TEST"):
        return PickFolderResponse(cancelled=True, error="Test mode: GUI dialog skipped")

    initial = req.initial_path if req and req.initial_path else str(Path.home())

    def _sync_pick() -> PickFolderResponse:
        if sys.platform == "darwin":
            prompt_text = "Select Project Folder:"
            # First try with frontmost app context so dialog appears on top
            script_front = f'''
            tell application (path to frontmost application as text)
                activate
                set chosen to choose folder with prompt "{prompt_text}"
                return POSIX path of chosen
            end tell
            '''
            try:
                proc = subprocess.run(
                    ["osascript", "-e", script_front],
                    capture_output=True,
                    text=True,
                    timeout=180
                )
                if proc.returncode == 0:
                    selected = proc.stdout.strip()
                    if selected.endswith("/"):
                        selected = selected[:-1]
                    p = Path(selected).resolve()
                    is_proj, p_type = detect_project(p)
                    return PickFolderResponse(
                        path=str(p),
                        name=p.name,
                        is_project=is_proj,
                        project_type=p_type,
                        cancelled=False
                    )
                else:
                    stderr_lower = proc.stderr.lower()
                    if "user canceled" in stderr_lower or "cancelled" in stderr_lower:
                        return PickFolderResponse(cancelled=True)
                    # If frontmost app AppleEvent permission was denied, fallback to generic choose folder
                    fallback_script = f'POSIX path of (choose folder with prompt "{prompt_text}")'
                    proc_fb = subprocess.run(
                        ["osascript", "-e", fallback_script],
                        capture_output=True,
                        text=True,
                        timeout=180
                    )
                    if proc_fb.returncode == 0:
                        selected = proc_fb.stdout.strip()
                        if selected.endswith("/"):
                            selected = selected[:-1]
                        p = Path(selected).resolve()
                        is_proj, p_type = detect_project(p)
                        return PickFolderResponse(
                            path=str(p),
                            name=p.name,
                            is_project=is_proj,
                            project_type=p_type,
                            cancelled=False
                        )
                    if "user canceled" in proc_fb.stderr.lower() or "cancelled" in proc_fb.stderr.lower():
                        return PickFolderResponse(cancelled=True)
                    return PickFolderResponse(cancelled=False, error=proc_fb.stderr.strip() or proc.stderr.strip())
            except subprocess.TimeoutExpired:
                return PickFolderResponse(cancelled=True, error="Selection dialog timed out")
            except Exception as e:
                return PickFolderResponse(cancelled=False, error=str(e))

        elif sys.platform == "win32":
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$dialog.Description = 'Select Project Folder'; "
                "$dialog.ShowNewFolderButton = $true; "
                "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
                "  Write-Output $dialog.SelectedPath "
                "}"
            )
            try:
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=180
                )
                selected = proc.stdout.strip()
                if selected:
                    p = Path(selected).resolve()
                    is_proj, p_type = detect_project(p)
                    return PickFolderResponse(
                        path=str(p),
                        name=p.name,
                        is_project=is_proj,
                        project_type=p_type,
                        cancelled=False
                    )
                return PickFolderResponse(cancelled=True)
            except Exception as e:
                return PickFolderResponse(cancelled=False, error=str(e))

        else:
            zenity = shutil.which("zenity")
            kdialog = shutil.which("kdialog")

            if zenity:
                try:
                    proc = subprocess.run(
                        [zenity, "--file-selection", "--directory", "--title=Select Project Folder"],
                        capture_output=True,
                        text=True,
                        timeout=180
                    )
                    if proc.returncode == 0:
                        selected = proc.stdout.strip()
                        p = Path(selected).resolve()
                        is_proj, p_type = detect_project(p)
                        return PickFolderResponse(
                            path=str(p),
                            name=p.name,
                            is_project=is_proj,
                            project_type=p_type,
                            cancelled=False
                        )
                    return PickFolderResponse(cancelled=True)
                except Exception as e:
                    return PickFolderResponse(cancelled=False, error=str(e))
            elif kdialog:
                try:
                    proc = subprocess.run(
                        [kdialog, "--getexistingdirectory", initial, "--title", "Select Project Folder"],
                        capture_output=True,
                        text=True,
                        timeout=180
                    )
                    if proc.returncode == 0:
                        selected = proc.stdout.strip()
                        p = Path(selected).resolve()
                        is_proj, p_type = detect_project(p)
                        return PickFolderResponse(
                            path=str(p),
                            name=p.name,
                            is_project=is_proj,
                            project_type=p_type,
                            cancelled=False
                        )
                    return PickFolderResponse(cancelled=True)
                except Exception as e:
                    return PickFolderResponse(cancelled=False, error=str(e))
            else:
                return PickFolderResponse(
                    cancelled=False,
                    error="Native folder dialog is not supported in this environment. Please use the built-in browser."
                )

    return await asyncio.to_thread(_sync_pick)
