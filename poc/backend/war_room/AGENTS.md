# AGENTS.md - Multi-Agent War Room & Deliberation Council Service

## 1. Service Identity & Mission
The **Multi-Agent War Room & Deliberation Council Service** (`poc/backend/war_room/router.py`) facilitates structured, multi-agent debates and alignment sessions before executing complex or risky engineering tasks. It brings together agents of diverse specializations (e.g., Architect, Backend Lead, QA Specialist, Security Officer) to debate trade-offs, critique proposals, and forge a consensus plan.

---

## 2. Core Capabilities & Specializations
* **Session Lifecycle State Machine**:
  * `GATHERING` -> `DEBATING` -> `CONSENSUS_REACHED` -> `EXECUTING` -> `COMPLETED`.
* **Structured Roundtable Debate Protocol**:
  * Agents speak in designated deliberation rounds (`round_number`).
  * Typed argument contributions:
    * `💡 PROPOSAL`: Introduction of an architectural or implementation approach.
    * `⚠️ CRITIQUE`: Identification of edge cases, security risks, or scalability flaws.
    * `👍 CONSENSUS_VOTE`: Formal agreement or ratification of a proposal.
    * `📋 SUMMARY`: Interim condensation of points of agreement.
* **Council Moderator Leadership**:
  * A designated lead agent (`moderator_agent_id`) presides over the session.
  * Formulates and locks the final synthesized execution plan (`synthesized_plan`).
* **Collaborative Plan Synthesis (`/synthesize`)**:
  * Locks consensus into a single authoritative roadmap ready for subtask dispatching.

---

## 3. Interfaces & REST Endpoints

### API Endpoints
* `GET /api/v1/war-room/` - List all active and historical deliberation sessions.
* `POST /api/v1/war-room/` - Convene a new war room council.
* `GET /api/v1/war-room/{session_id}` - Retrieve complete dialogue transcript and participant metadata.
* `POST /api/v1/war-room/{session_id}/messages` - Submit a deliberation argument, proposal, or critique.
* `POST /api/v1/war-room/{session_id}/synthesize` - Finalize consensus and lock the agreed execution plan.

---

## 4. Invariant Rules & Guardrails
1. **Minimum Quorum**: Every War Room session must have at least 1 moderator agent and at least 1 participant agent.
2. **Immutability of Transcripts**: Once submitted, debate messages cannot be edited or erased, guaranteeing an auditable trail of decision-making.
3. **Consensus Requirement**: No session can transition to `CONSENSUS_REACHED` without a non-empty `synthesized_plan`.
