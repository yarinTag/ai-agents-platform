# Plugin discovery components

`metadata.py` owns markdown/front-matter metadata parsing and registration in the existing skill-content cache. `git_scanner.py` owns in-memory GitHub tree/blob discovery and the tree-SHA cache. `local_scanner.py` owns explicitly configured local directory/marketplace discovery. `packages.py` owns the shared package-summary projection. These modules do not import FastAPI, routers, the backend container or a concrete inference runtime.

The API's skills_metadata.py and skills_git_scanner.py retain compatibility exports. HTTP routes resolve the current organization, update explicit source settings, resolve tenant-scoped credentials, and call the source adapters. Local mode with an empty path and Git mode with an empty repository return zero packages; neither falls back to system paths or clones repositories. Existing manifest and non-manifest discovery rules are preserved. Files remain at most 500 physical lines.

GET `/api/v1/skills/plugins/content` revalidates remote content through GitHub under current credentials rather than returning a globally cached private document. Local content must resolve inside the current organization's configured plugins_local_path; an empty source or out-of-root file returns 404. Organization-scoped token discovery never falls back to another organization's credentials or host gh authentication. Legacy unscoped local use retains the prior token lookup behavior.

The shared runtime skill-content cache remains a compatibility integration in skills_service; this refactor does not claim a complete audit of every runtime skill-resolution policy.

Agent skill resolution (`skills_service.resolve_skill`) is contained: an absolute-path ID resolves only to an existing `.md` file inside a configured skill search root (checked after symlink resolution), and name IDs used in marketplace globs must be plain relative names (no `..`, absolute paths, `~` or glob characters). Relative file-path IDs are no longer read from the process working directory. Search roots still merge every organization's `plugins_local_path`; per-tenant root scoping is a separate open item. No source import, scanner execution, live provider request, test, build or lint was executed during this task.

Master refresh integration: _scan_git_repo_via_api(repo_url, token, force_refresh=False) bypasses cached Git tree results when requested by GET /api/v1/skills/plugins/scan?refresh=true; configured empty sources still return no plugins.

workflow_skills.py projects only the organization's explicit configured plugin
source into id/name/key/plugin/description metadata. Git mode uses the existing
in-memory scanner and exact-tenant GitHub connector credentials; local mode has
no fallback roots. Context resolution revalidates current catalog membership,
fetches remote full Markdown via bounded fixed-host GitHub API, or reads a local
file inside the configured root. Unique legacy keys/relative suffixes resolve
only within that catalog; unavailable/ambiguous references fail. No global skill
content cache supplies workflow instructions. Combined content is <=120000 chars,
local files <=100000 bytes; empty/missing content fails. No clone, tool grant or
script execution is implied. Runtime verification was not performed.

## Inter-skill flow connection extraction (2026-11-03)
`metadata.py:extract_skill_meta_from_text` extracts optional `role` from YAML frontmatter and retains `_raw_content` transiently during package assembly. `packages.py:_enrich_skill_connections` resolves cross-skill references across discovered skills (matching both full skill IDs such as `product-prd-writer` and category-prefix-stripped aliases such as `prd-writer`, `idea-to-blueprint`, `architecture-designer`, `google-docs-prd-publisher`), populates `connected_skills: List[str]` on each skill summary, and strips `_raw_content` before returning `PluginPackage` payloads.

## Evidence-backed skill relationships (2026-11-05; supersedes mention-as-flow)
`connections.py` owns `enrich_skill_connections(plugins_map, flow_documents=None)`;
`packages.py` retains `_enrich_skill_connections` as a compatibility alias and forwards
optional named DAG documents from local/Git adapters. Each summary adds `skill_connections`
objects with source/target, kind (`handoff`, `conditional_handoff`, `declared_transition`,
`reference`), optional conditional:boolean, and evidence {path,line?,node_id?,text,section?,
revision?}. `connected_skills` remains a deduplicated compatibility mention/transition list;
it must not be interpreted as execution order. `connection_warnings` reports duplicate
IDs, missing/incomplete full content and unresolved declarative targets. Full raw content
is removed before responding. Unique full IDs/short aliases resolve globally; ambiguous
aliases, self edges and unknown targets never establish a relationship.

Positive imperative handoffs (including coordinated targets) and explicit Routing table
rows establish instruction flow; if/when/once/etc. in the source line/heading retain
conditional semantics, including conditions before a sentence boundary. Negations,
frontmatter, fenced examples, non-goals and resource paths cannot establish execution
handoffs. Ordinary references remain a separate kind, never implicit prerequisites or
reversed flow. Prose recognition is conservative, not exhaustive semantic certification.

Only named `references/skill-dependency-dag.json` files inside discovered package roots
supply machine-declared {nodes:[{id,skill,nextNodes,optional?,skipFlag?,...}]} transitions.
Each edge retains from/to nodes (artifacts/flags included) in its evidence; optional nodes
remain conditional. Unknown group names produce a warning rather than guessed skills.
No referenced scripts execute. Git reads immutable blob SHAs from the selected tree,
adds source_revision (tree SHA), and versions the scan cache key with evidence-flow-v1.
Local reads are bounded at one million characters rather than 16 KiB; truncated/unreadable
content cannot establish prose flow. Local DAG reads are source-root/package-contained,
limited to one million bytes. Tree fetch/blob and existing organization credentials remain
in the adapters; no new API route, grant or model call. Sources may describe different
modes and are not combined into a claimed universal execution sequence. See
[the pinned-source audit](../../docs/plugin-skill-flow-audit.md). No local runtime checks.


## Agent and local-source access scope (2026-11-05)
workflow_skills.skill_catalog requires local sources to lie under the organization's shared
server-owned tenant root. agent_skill_context adds owned custom-catalog/project records to the
same organization plugin source; project skill use requires the actual selected project and
owner. Foreign/unowned custom IDs fail instead of falling back to a global cache. Context is
bounded to120000 chars. API plugin content additionally verifies configured Git owner/repo or
local tenant containment. No source execution, scan, provider calls or verification imports.

source.py resolves plugin Git overrides through the current department, its parent departments and the agent’s supervisor departments before using organization settings. Parent/agent traversal is tenant-bounded and cycle-safe. Workflow skills use the workflow department. Agent custom skills require organization ownership and, when applicable, the exact project.
