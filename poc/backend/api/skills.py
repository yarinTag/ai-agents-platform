"""Compatibility exports and router composition for skills."""

from fastapi import APIRouter
# Bootstrap the single legacy import bridge before domain compatibility exports.
from ..dependencies import get_db_manager
from .skills_models import (PluginsConfigRequest, SkillBase, SkillCreate, SkillUpdate, SkillResponse)
from .skills_metadata import (extract_skill_meta_from_text, extract_skill_meta, skill_to_response)
from .skills_credentials import (_get_or_create_effective_org, _find_git_token, _format_authenticated_git_url)
from .skills_git_scanner import (_GIT_TREE_SCAN_CACHE, _parse_github_owner_repo, _scan_git_repo_via_api)
from .skills_plugin_settings import (get_plugins_config, update_plugins_config, get_plugin_git_repos)
from .skills_plugin_scan import (scan_plugins, get_plugin_skill_content)
from .skills_crud import (list_skills, create_skill, get_skill, update_skill, delete_skill)

router = APIRouter()
from .skills_plugin_settings import router as plugin_settings_router
router.include_router(plugin_settings_router)
from .skills_plugin_scan import router as plugin_scan_router
router.include_router(plugin_scan_router)
from .skills_crud import router as crud_router
router.include_router(crud_router)
