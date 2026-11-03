# AGENTS.md - Global Context & State Management

## 1. Overview & Directory Mission
The `src/context/` directory encapsulates global application state, session persistence, multi-tenant security isolation, and active departmental context. The core provider is [`AuthContext.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/context/AuthContext.tsx).

---

## 2. `AuthContext.tsx` Architectural Specification

### 2.1 State Model (`AuthContextType`)
The `AuthContext` provides the following reactive state variables and handler functions:

```typescript
export interface AuthContextType {
  token: string | null;                         // Active JWT Bearer token
  user: AuthUser | null;                        // Authenticated user profile
  organization: Organization | null;            // Current tenant organization
  departments: Department[];                   // List of departments in the organization
  activeDepartmentId: string | null;           // Currently selected department for filtering
  setActiveDepartmentId: (id: string | null) => void; // Department switcher handler
  isAuthenticated: boolean;                     // Derived boolean: Boolean(token && user)
  isLoading: boolean;                           // Initial session verification state
  login: (data: LoginDto) => Promise<void>;    // Sign in handler
  register: (data: RegisterOrgDto) => Promise<void>; // Register organization handler
  acceptInvitation: (data: AcceptInviteDto) => Promise<void>; // Accept invite handler
  logout: () => void;                           // Clear session and disconnect
  refreshUserProfile: () => Promise<void>;      // Refresh user, org, and departments from /api/v1/auth/me
}
```

### 2.2 Storage & Persistence Invariants
* **`AUTH_TOKEN_KEY`**: `'agents_platform_auth_token'`
  * Stores the raw JWT Bearer token string in browser `localStorage`.
* **`AUTH_SESSION_KEY`**: `'agents_platform_auth_session'`
  * Stores a JSON-serialized object containing `{ user, organization, departments }` for immediate hydrated rendering before network revalidation.
* **Auto-Default Department**:
  * On initial load or after authentication, `activeDepartmentId` automatically defaults to the first available department (`departments[0].id`) if not previously specified.

### 2.3 Network & Security Integrations
* **Axios Request Interceptor**:
  * All outgoing requests from `src/services/api.ts` read `localStorage.getItem(AUTH_TOKEN_KEY)` and attach `Authorization: Bearer <token>`.
* **401 Unauthorized Interceptor**:
  * When any protected API call returns an HTTP 401 status, the interceptor clears both localStorage keys and dispatches a global window event:
    `window.dispatchEvent(new CustomEvent('auth:unauthorized'))`.
  * `AuthContext` listens for `'auth:unauthorized'` and triggers `logout()`, transitioning the UI to the authentication shell.
* **SSE Stream Coordination**:
  * `eventStream.ts` relies on the same JWT token stored in `localStorage` to authorize the `/api/v1/events/stream?token=...` connection.

### 2.4 Multi-Tenant Data Isolation
* All agents, tasks, workflows, and plugins are strictly scoped to the authenticated user's `organization.id`.
* The `activeDepartmentId` is consumed by UI views (e.g., `OfficeRightSidebar`, `OfficeTopBar`, `AgentsPage`, `OrganizationPage`) to filter data or assign new entities to the correct departmental unit.

---

## 3. Usage Pattern

```tsx
import { useAuth } from '../context/AuthContext';

const MyComponent: React.FC = () => {
  const { user, organization, departments, activeDepartmentId, setActiveDepartmentId } = useAuth();
  
  return (
    <div>
      <h3>{organization?.name}</h3>
      <p>Logged in as: {user?.email} ({user?.role})</p>
    </div>
  );
};
```

---

## 4. 🔄 Mandatory UI `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> **Every time `AuthContext.tsx` or any file in `src/context/` is added, modified, or refactored, the developer/agent MUST update this file (`src/context/AGENTS.md`) as part of the same task.**
>
> Checklist on context changes:
> 1. Document any changes to `AuthContextType` (new state fields, getters, or actions).
> 2. Detail any alterations to localStorage keys or session hydration logic.
> 3. Document new custom events or interceptor coordination mechanisms.
> 4. Ensure [`poc/dashboard/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/AGENTS.md) is updated if tenant context boundaries change.

## Department ID normalization (2026-11-01)
`AuthContext.tsx` normalizes hydrated and refreshed `departments` entries via `normalizeDepartments` so every entry carries both `id` and `department_id` (`d.id || d.department_id`), and preserves the existing selected `activeDepartmentId` across `initAuth`/`refreshUserProfile` when still valid.
