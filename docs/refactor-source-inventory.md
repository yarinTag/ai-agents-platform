# Refactor source inventory

Source text read on 2026-10-30 after merging master 523913e. Project modules were not imported or executed; this is source-size evidence, not test/build/runtime verification.

Owned source/config files inventoried: 473. Largest file: 482 physical lines. Files above 500: 0.

Dependency folders, caches, generated build outputs and generated package-lock.json are excluded. Markdown documentation is outside the code limit. The unrelated existing :memory:.ses artifact was not edited.

| Area | Files | Maximum physical lines |
|---|---:|---:|
| . | 4 | 112 |
| poc | 25 | 473 |
| poc/backend | 9 | 326 |
| poc/backend/api | 55 | 378 |
| poc/backend/approvals | 3 | 450 |
| poc/backend/chat | 2 | 447 |
| poc/backend/config | 1 | 349 |
| poc/backend/db | 3 | 214 |
| poc/backend/events | 2 | 309 |
| poc/backend/memory | 2 | 112 |
| poc/backend/messages | 2 | 265 |
| poc/backend/queue | 7 | 270 |
| poc/backend/scheduler | 5 | 223 |
| poc/backend/security | 7 | 247 |
| poc/backend/teams | 2 | 165 |
| poc/backend/war_room | 2 | 163 |
| poc/backend/workflow_assistant | 8 | 446 |
| poc/config | 2 | 30 |
| poc/dashboard | 6 | 28 |
| poc/dashboard/src | 186 | 470 |
| poc/dashboard/tests | 1 | 37 |
| poc/events | 4 | 109 |
| poc/integrations | 2 | 61 |
| poc/orchestration | 16 | 482 |
| poc/plugins | 5 | 195 |
| poc/runtime | 18 | 298 |
| poc/storage | 41 | 378 |
| poc/tests | 40 | 435 |
| poc/workflows | 13 | 336 |

## Largest source files

| File | Physical lines |
|---|---:|
| poc/orchestration/supervisor_resolver.py | 482 |
| poc/runtime_adapter.py | 473 |
| poc/dashboard/src/components/workflows/useWorkflowBuilder.ts | 470 |
| poc/dashboard/src/pages/useMcpConnectorActions.tsx | 456 |
| poc/dashboard/src/components/workflows/WorkflowCanvasGraph.tsx | 454 |
| poc/backend/approvals/router.py | 450 |
| poc/backend/chat/router.py | 447 |
| poc/dashboard/src/components/office/OfficeCanvas.tsx | 447 |
| poc/backend/workflow_assistant/service.py | 446 |
| poc/dashboard/src/components/workflows/WorkflowStepsPanel.tsx | 435 |
| poc/tests/test_workflow_assistant.py | 435 |
| poc/dashboard/src/components/chat/AgentChatContent.tsx | 430 |
| poc/dashboard/src/pages/OrganizationPage.tsx | 428 |
| poc/orchestration/code_indexer.py | 428 |
| poc/dashboard/src/components/memory/ProjectSharedMemoryModal.tsx | 408 |
| poc/dashboard/src/components/layout/AppSidebar.tsx | 404 |
| poc/tests/test_org_auth_and_department_users.py | 404 |
| poc/dashboard/src/components/office/OfficeRightSidebar.tsx | 403 |
| poc/dashboard/src/components/common/FolderPickerModal.tsx | 398 |
| poc/dashboard/src/pages/useSkillsPage.tsx | 397 |
| poc/tests/test_department_mcp_governance.py | 396 |
| poc/verify_full_e2e_flow.py | 396 |
| poc/dashboard/src/pages/useTasksPage.tsx | 392 |
| poc/dashboard/src/pages/Tasks.tsx | 390 |
| poc/dashboard/src/index.css | 385 |
| poc/dashboard/src/components/office/AgentDeskDrawer.tsx | 382 |
| poc/backend/workflow_assistant/generation.py | 380 |
| poc/dashboard/src/components/warroom/WarRoomModal.tsx | 380 |
| poc/backend/api/workflows_generation.py | 378 |
| poc/dashboard/src/pages/Workflows.tsx | 378 |

## Interpretation

All reported owned source files are below the limit. Source parsing/conflict-marker review does not establish successful compilation, preserved runtime behavior or failure isolation. See refactor-implementation.md for source-review evidence and remaining limits.
