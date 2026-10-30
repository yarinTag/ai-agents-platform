# AGENTS.md - Spatial Office Simulation & Visualization Engines

## 1. Service Identity & Mission
The **Spatial Office Simulation & Visualization Engines** (`poc/dashboard/src/engine/PixelRenderer.ts` and `poc/dashboard/src/components/office/AgentsOfficeV3Canvas.tsx`) form the physical representation layer of the platform. They render live, animated visual office environments where every AI agent occupies a physical workstation, reflecting real-time execution states, active tasks, delegation flows, and interactive collaboration.

---

## 2. Rendering Engines Architecture

### 2.1 Pure HTML5 Canvas Engine (`PixelRenderer.ts` & `PixelOfficeCanvas.tsx`)
* **Pure HTML5 Canvas Tile Engine**:
  * High-performance 60 FPS rendering without heavy WebGL overhead.
  * Tile-based grid architecture: 56 columns × 46 rows with structured departments (Engineering, Marketing, Exec HQ, Operations, Conference, Lounge, Kitchen).
* **Multi-State Agent Sprite Rendering**:
  * Agent directionality (`up`, `down`, `left`, `right`).
  * Sitting, working, typing, and walking animations procedurally rendered with 0 external sprite assets.
* **Reactive Status Bubbles & Alerts**:
  * `❓ Floating Speech Bubble`: Animated bouncing bubble rendered above an agent's head when an active task enters `WAITING_INPUT`.
  * `⚠️ Alert Bubble`: Rendered when a task enters `PENDING_APPROVAL`.
  * `⚡ Active Glow`: Dynamic lighting effect around agents actively running tasks.
* **Interactive Spatial Hit-Testing**:
  * Translates screen mouse clicks into canvas tile coordinates.
  * Clicking an agent's desk immediately opens the `AgentMiniChatDrawer` or `AgentDeskDrawer`.

### 2.2 High-Fidelity 2.5D Isometric Engine (`AgentsOfficeV3Canvas.tsx`)
* **Department Hub Topology**:
  * Renders a central AI brain node surrounded by dedicated departmental clusters:
    * Engineering Hub (`#3b82f6`)
    * Operations & Security (`#10b981`)
    * Marketing & Growth (`#ec4899`)
    * Executive HQ (`#f59e0b`)
* **Interactive Viewport Controls**:
  * Smooth zoom (`0.5x` to `2.0x`) and fluid click-and-drag panning.
  * Reset view button returning viewport to platform center coordinates.
* **Live Agent Status & Glow Indicators**:
  * Multi-colored status rings (idle in green, executing in blue pulse, awaiting input in amber).
  * Direct desk click triggers agent selection and drawer presentation.
  * Department hover highlighting and quick task dispatching.

---

## 3. Interfaces & State Flow

### Key Functions & Integration
* `PixelRenderer.render(ctx, state)`: Master render loop consuming live platform state:
  * `agents: Agent[]`
  * `tasks: Task[]`
  * `selectedAgentId: string | null`
  * `animTick: number`
* **Department & Room Layouts**: Defined in `ROOMS` array with pre-configured workstation desks (`desks: RoomDef['desks']`).
* **AgentsOfficeV3Canvas Props**:
  * `agents: Agent[]`
  * `tasks: Task[]`
  * `onSelectAgent: (agent: Agent) => void`
  * `onSelectDepartment?: (dept: string) => void`
  * `onTaskCreated?: () => void`

---

## 4. Invariant Rules & Guardrails
1. **Zero External Asset Dependencies**: All sprites (desks, computers, walls, characters, speech bubbles) are drawn procedurally via canvas primitives and pixel matrices. No missing image 404s.
2. **DPI & Retina Scaling**: Canvas dimensions must always scale by `window.devicePixelRatio` to prevent blurriness on high-density displays.
3. **Smooth Fallbacks**: If an agent has no designated room or department, it is gracefully placed at available desks or in the reception/lounge zones without throwing rendering errors.
4. **Workflow Agent Exclusion**: Workflow automation agents (`role_type === 'WORKFLOW_AUTOMATION'`) are detached from physical desks and filtered out to preserve spatial realism.

---

## 5. 🔄 Mandatory UI `AGENTS.md` Synchronization Rule

### Renderer composition (2026-10-29 refactor)

`PixelRenderer.ts` is the public lifecycle/input facade. It retains constructor, `panX`/`panY`/`zoom` access, `updateData`, connection/selection setters, resize, start/stop, click/mouse-move handling and render. It privately owns `PixelSceneState`; consumers do not receive mutable scene state.

* `pixelSceneLayout.ts`: palette, room/grid constants, character colors and visual/walk contracts. Grid dimensions and desk coordinates are unchanged.
* `pixelSceneState.ts`: canvas/context, viewport, agents/tasks, selection, stable colors and animation maps.
* `pixelSceneLifecycle.ts`: data updates, connection derivation, animation-frame ownership and input hit testing. Frame rendering is supplied as a callback by the facade, so lifecycle does not import the painting coordinator.
* `pixelCoordinates.ts`: coordinate/pixel scaling helpers. `pixelAgentActivity.ts`: working/manager predicates and completion/walk transitions. `pixelDeskLayout.ts`: room assignment, desk allocation and stable colors.
* `pixelScenePainter.ts`: explicit render order and room/entrance/corridor orchestration. It preserves shell → floors → walls → doors → furniture → entrance → corridors → chairs → seated agents → desks → walking agents → connections → HUD → room labels.
* Drawing implementations are grouped in `pixelBuildingPainter.ts`, `pixelCharacterPainter.ts`, `pixelConnectionPainter.ts`, `pixelDeskPainter.ts`, `pixelLeisurePainter.ts` and `pixelRoomFurniturePainter.ts`. They receive scene context explicitly and do not own animation-frame lifecycle.

No inheritance or runtime method injection is used. Painters depend on low-level coordinates/state/layout; state does not import painters. The existing `VisualConnection` type remains re-exported from `PixelRenderer.ts`. This is a source-only structural extraction; no rendering or execution verification was run.

> [!IMPORTANT]
> **Every time `PixelRenderer.ts`, `PixelOfficeCanvas.tsx`, `AgentsOfficeV3Canvas.tsx`, or any visual rendering logic in `src/engine/` is added, modified, or refactored, the developer/agent MUST update this file (`src/engine/AGENTS.md`) as part of the same task.**
>
> Checklist on engine changes:
> 1. Document changes to grid dimensions, room definitions, or coordinate matrices.
> 2. Detail any new sprite rendering states, animation cycles, or hit-test bounding boxes.
> 3. Document zoom/pan interactions, department clusters, or layout algorithms.
> 4. Ensure master index in [`poc/dashboard/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/AGENTS.md) is kept in sync.
