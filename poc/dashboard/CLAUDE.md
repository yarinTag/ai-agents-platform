# CLAUDE.md - Frontend Guidelines (Dashboard)

This document provides developer instructions and architectural invariants for Claude Code working on the `poc/dashboard` React application.

---

## 🚀 Quick Commands

* **Install Dependencies**: `npm install`
* **Development Server**: `npm run dev` (starts on `http://localhost:5173`)
* **Production Build**: `npm run build` (runs `vite build`, verifies TypeScript types & bundles)
* **Preview Production**: `npm run preview`

---

## 🏗️ Architecture & Technology Stack

* **Framework**: React 18 with TypeScript (`strict: true`)
* **Bundler & Tooling**: Vite + Rolldown
* **UI Component Library**: Ant Design (`antd` v5)
* **Icons**: `@ant-design/icons`
* **Styling**: Inline style objects with strict Tailwind-inspired palette (Slate, Amber, Emerald, Indigo)
* **Routing**: `react-router-dom` v6 (`AppLayout` wrapper, routes in `src/App.tsx`)
* **State Management**:
  * Local component state via React hooks (`useState`, `useEffect`, `useCallback`, `useRef`).
  * Real-time events hook: `useOfficeEvents` (`src/hooks/useOfficeEvents.ts`) subscribing to Server-Sent Events (SSE) `/api/v1/events/stream`.
* **Graphics & Simulation Engine**: Pure HTML5 Canvas Pixel Renderer (`src/engine/PixelRenderer.ts`) rendering an isometric/top-down pixel art office with sprite animations and real-time state bubbles.

---

## 📁 Directory Structure

```
poc/dashboard/src/
├── components/
│   ├── approval/        # ApprovalModal.tsx (HITL & Question resolution)
│   ├── chat/            # AgentMiniChatDrawer.tsx (Interactive live mini-chat)
│   ├── layout/          # AppLayout.tsx, OfficeTopBar.tsx (Navigation & headers)
│   ├── memory/          # ProjectSharedMemoryModal.tsx (Knowledge base & ADRs)
│   ├── office/          # PixelOfficeCanvas.tsx, OfficeRightSidebar.tsx, AgentDeskDrawer.tsx
│   ├── scheduler/       # CronBuilderModal.tsx (Cron generator & validator)
│   └── warroom/         # WarRoomModal.tsx (Multi-agent council deliberation)
├── engine/              # PixelRenderer.ts (Canvas tile/sprite engine)
├── hooks/               # useOfficeEvents.ts (SSE connection & state sync)
├── pages/               # OfficeView.tsx, CalendarView.tsx, Agents.tsx, Projects.tsx, Tasks.tsx
├── services/            # api.ts (Central Axios instance and typed API calls)
└── types/               # agent.ts, chat.ts, collab.ts, scheduler.ts, task.ts
```

---

## 📐 Coding Conventions & Guidelines

1. **TypeScript Strictness**:
   * Always define typed DTOs and interfaces in `src/types/`. Do NOT use `any` unless absolutely necessary for third-party interop.
   * Verify every change compiles cleanly using `npm run build`.
2. **Component Structure**:
   * Functional components with explicit `React.FC<Props>` typing.
   * Destructure props and provide sensible defaults.
   * Clean up event listeners, timers, and SSE streams in `useEffect` cleanup return functions.
3. **API Integration**:
   * All API calls MUST go through `src/services/api.ts`.
   * Standard Axios response pattern: `const res = await apiMethod(); setThing(res.data)`.
   * Handle errors gracefully with Ant Design's `message.error(...)`.
4. **Ant Design Conventions**:
   * Use theme tokens and Ant Design primitives (`Button`, `Modal`, `Drawer`, `Card`, `Tag`, `Typography`).
   * When wrapping multiple adjacent elements in table column `render` functions, always wrap them in a `<div style={{ display: 'flex', gap: '8px' }}>` container to prevent JSX syntax errors.
5. **Real-Time Responsiveness**:
   * Avoid polling loops where possible. Rely on `useOfficeEvents` SSE push for live updates.
