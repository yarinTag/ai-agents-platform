# Plugin discovery components

`metadata.py` owns markdown/front-matter metadata parsing and registration in the existing skill-content cache. `git_scanner.py` owns in-memory GitHub tree/blob discovery and the tree-SHA cache. `local_scanner.py` owns explicitly configured local directory/marketplace discovery. `packages.py` owns the shared package-summary projection. These modules do not import FastAPI, routers, the backend container or a concrete inference runtime.

The API's skills_metadata.py and skills_git_scanner.py retain compatibility exports. HTTP routes resolve the current organization, update explicit source settings, resolve tenant-scoped credentials, and call the source adapters. Local mode with an empty path and Git mode with an empty repository return zero packages; neither falls back to system paths or clones repositories. Existing manifest and non-manifest discovery rules are preserved. Files remain at most 500 physical lines.

GET `/api/v1/skills/plugins/content` revalidates remote content through GitHub under current credentials rather than returning a globally cached private document. Local content must resolve inside the current organization's configured plugins_local_path; an empty source or out-of-root file returns 404. Organization-scoped token discovery never falls back to another organization's credentials or host gh authentication. Legacy unscoped local use retains the prior token lookup behavior.

The shared runtime skill-content cache remains a compatibility integration in skills_service; this refactor does not claim a complete audit of every runtime skill-resolution policy. No source import, scanner execution, live provider request, test, build or lint was executed during this task.

Master refresh integration: _scan_git_repo_via_api(repo_url, token, force_refresh=False) bypasses cached Git tree results when requested by GET /api/v1/skills/plugins/scan?refresh=true; configured empty sources still return no plugins.
