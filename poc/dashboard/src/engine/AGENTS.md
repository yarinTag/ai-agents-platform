# AGENTS.md - Pixel Office Simulation & Visualization Engine

## 1. Service Identity & Mission
The **Pixel Office Simulation & Visualization Engine** (`poc/dashboard/src/engine/PixelRenderer.ts`) is the spatial representation layer of the platform. It renders an animated, isometric/top-down pixel art office environment where every AI agent has a physical workstation, visually reflecting live execution states, delegation flows, and collaboration events.

---

## 2. Core Capabilities & Specializations
* **Pure HTML5 Canvas Tile Engine**:
  * High-performance 60 FPS rendering without heavy WebGL overhead.
  * Tile-based grid architecture: 56 columns × 46 rows with structured departments (Engineering, Marketing, Exec HQ, Operations, Conference, Lounge, Kitchen).
* **Multi-State Agent Sprite Rendering**:
  * Agent directionality (`up`, `down`, `left`, `right`).
  * Sitting, working, typing, and walking animations.
* **Reactive Status Bubbles & Alerts**:
  * `❓ Floating Speech Bubble`: Animated bouncing bubble rendered above an agent's head when an active task enters `WAITING_INPUT`.
  * `⚠️ Alert Bubble`: Rendered when a task enters `PENDING_APPROVAL`.
  * `⚡ Active Glow`: Dynamic lighting effect around agents actively running tasks.
* **Interactive Spatial Hit-Testing**:
  * Translates screen mouse clicks into canvas tile coordinates.
  * Clicking an agent's desk immediately opens the `AgentMiniChatDrawer` or `AgentDeskDrawer`.

---

## 3. Interfaces & State Flow

### Key Functions & Integration
* `PixelRenderer.render(ctx, state)`: Master render loop consuming live platform state:
  * `agents: Agent[]`
  * `tasks: AgentRun[]`
  * `selectedAgentId: string | null`
  * `animTick: number`
* **Department & Room Layouts**: Defined in `ROOMS` array with pre-configured workstation desks (`desks: RoomDef['desks']`).

---

## 4. Invariant Rules & Guardrails
1. **Zero External Asset Dependencies**: All sprites (desks, computers, walls, characters, speech bubbles) are drawn procedurally via canvas primitives and pixel matrices. No missing image 404s.
2. **DPI & Retina Scaling**: Canvas dimensions must always scale by `window.devicePixelRatio` to prevent blurriness on high-density displays.
3. **Smooth Fallbacks**: If an agent has no designated room, it is gracefully placed at available desks or in the reception/lounge zones without throwing rendering errors.
