# Refactor source inventory

Source text read on 2026-10-29; project modules were not imported or executed. This is file-size evidence only, not test/build/runtime verification.

Owned source/config files inventoried: 413. Largest file: 482 physical lines. Files above 500: 0.

Dependency folders, caches, generated build outputs and generated package-lock.json are excluded. Markdown documentation is outside the code limit. The unrelated existing :memory:.ses artifact was not edited.

| Area | Files | Maximum physical lines |
|---|---:|---:|
| poc | 25 | 445 |
| poc/backend | 7 | 295 |
| poc/backend/api | 52 | 371 |
| poc/backend/approvals | 2 | 250 |
| poc/backend/chat | 2 | 447 |
| poc/backend/config | 1 | 349 |
| poc/backend/events | 2 | 296 |
| poc/backend/memory | 2 | 112 |
| poc/backend/messages | 2 | 265 |
| poc/backend/scheduler | 5 | 223 |
| poc/backend/security | 6 | 207 |
| poc/backend/teams | 2 | 165 |
| poc/backend/war_room | 2 | 163 |
| poc/config | 2 | 30 |
| poc/dashboard | 5 | 28 |
| poc/dashboard/src | 170 | 456 |
| poc/data/qdrant_storage | 1 | 1 |
| poc/events | 4 | 109 |
| poc/integrations | 2 | 61 |
| poc/orchestration | 16 | 482 |
| poc/plugins | 5 | 195 |
| poc/runtime | 16 | 272 |
| poc/storage | 41 | 334 |
| poc/tests | 31 | 404 |
| poc/workflows | 10 | 279 |

## Largest source files

| File | Physical lines |
|---|---:|
| poc/orchestration/supervisor_resolver.py | 482 |
| poc/dashboard/src/pages/useMcpConnectorActions.tsx | 456 |
| poc/dashboard/src/components/office/OfficeCanvas.tsx | 447 |
| poc/backend/chat/router.py | 447 |
| poc/runtime_adapter.py | 445 |
| poc/dashboard/src/components/workflows/WorkflowCanvasGraph.tsx | 439 |
| poc/dashboard/src/components/workflows/WorkflowStepsPanel.tsx | 435 |
| poc/dashboard/src/components/chat/AgentChatContent.tsx | 430 |
| poc/orchestration/code_indexer.py | 428 |
| poc/dashboard/src/pages/OrganizationPage.tsx | 428 |
| poc/dashboard/src/components/memory/ProjectSharedMemoryModal.tsx | 408 |
| poc/tests/test_org_auth_and_department_users.py | 404 |
| poc/dashboard/src/components/office/OfficeRightSidebar.tsx | 403 |
| poc/dashboard/src/components/common/FolderPickerModal.tsx | 398 |
| poc/dashboard/src/pages/useSkillsPage.tsx | 397 |
| poc/verify_full_e2e_flow.py | 396 |
| poc/tests/test_department_mcp_governance.py | 396 |
| poc/dashboard/src/pages/useTasksPage.tsx | 389 |
| poc/dashboard/src/components/layout/AppSidebar.tsx | 386 |
| poc/dashboard/src/index.css | 385 |
| poc/dashboard/src/components/office/AgentDeskDrawer.tsx | 382 |
| poc/dashboard/src/components/warroom/WarRoomModal.tsx | 380 |
| poc/dashboard/src/pages/Tasks.tsx | 378 |
| poc/dashboard/src/components/workflows/useWorkflowBuilder.ts | 375 |
| poc/dashboard/src/engine/pixelCharacterPainter.ts | 372 |
| poc/backend/api/workflows_generation.py | 371 |
| poc/dashboard/src/components/office/OfficeDepartmentPlatforms.tsx | 368 |
| poc/dashboard/src/pages/McpWorkflowChannels.tsx | 363 |
| poc/config.py | 361 |
| poc/backend/api/filesystem.py | 361 |
| poc/dashboard/src/pages/CalendarView.tsx | 351 |
| poc/backend/config/agents.json | 349 |
| poc/dashboard/src/pages/useCalendarViewPage.tsx | 344 |
| poc/dashboard/src/components/office/IsometricOffice.tsx | 344 |
| poc/tests/test_provider_agnostic_runtime.py | 342 |

## Interpretation

Existing public compatibility facades remain in use. All reported source files are under the limit; this does not establish absence of semantic duplication, successful compilation or runtime resilience. See refactor-implementation.md for ownership/review and limitations.
