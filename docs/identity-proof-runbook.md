# AI-27 · Identity proof and approver authentication

The [external identities API contract](external-identities.md) defines the request and response shapes. This guide covers how the proof establishes identity, how future approval handlers must use it, and how to respond to a compromise.

```mermaid
sequenceDiagram
    actor User as Signed-in platform user
    participant Platform as Platform API
    participant DB as SQLite
    participant Provider as Telegram or Slack
    User->>Platform: Request challenge for authorized connector
    Platform->>DB: Check active user and connector access, store digest and expiry
    Platform-->>User: Return one-time code with no-store
    User->>Provider: Send code via private bot chat or slash command
    Provider->>Platform: Send provider-authenticated request
    Platform->>Platform: Verify request, freshness, account and personal subject
    Platform->>DB: Check connector configuration version and record observed subject
    Platform-->>Provider: Acknowledge without revealing challenge state
    User->>Platform: Read own challenge and observed subject
    User->>Platform: Confirm the observed subject
    Platform->>DB: Recheck access, expiry and uniqueness; consume and audit atomically
    Platform-->>User: Return linked identity
```

The platform account is the active user in a specific organization. The provider subject is a stable personal ID inside a verified provider account. Channel membership describes access at the provider. It grants no platform role. Display names, typed subject IDs and forwarded messages never establish proof. A stored link remains tied to its connector and provider account.

Challenges expire after five minutes. A new challenge invalidates the previous one for that user and connector. At most five challenges can be issued per user in ten minutes. Provider proof records one observed subject and final confirmation consumes it. The platform confirms the subject with the same authenticated user who requested the challenge. Keep codes private and issue a new one after expiry or suspected disclosure.

## How an approval handler uses identity

Channel-native decisions are a future consumer of the link. Authenticate the provider request, identify the exact connector and provider account, and resolve a verified personal subject to a current platform user. Recheck organization, department, role and authority for the specific pending action. Match the decision to the exact binding, execution, approval, and reviewed action. Require a current one-use decision and reject ambiguity or expiry. The existing authenticated dashboard decision remains available independently of provider linking.

| Threat | Boundary |
| --- | --- |
| Hijacked channel or bot added to another group | A channel or group cannot identify a personal approver. Inbound routing must match the authorized connector and binding. |
| Spoofed user ID or workspace | Verify the provider request before extracting the subject. Check the configured account and app where applicable. Resolve the stable subject under the exact connector and organization. |
| Forwarded proof or approval message | Telegram proof accepts a direct private bot message from a personal sender. A forwarded approval link conveys no approval authority. |
| Leaked challenge | A third party can interfere with a pending challenge. The authenticated initiator must inspect and confirm the observed subject. Reject an unexpected subject and issue a new code. |
| Stolen provider secret | Treat provider proof for that installation as compromised. Rotate at both boundaries and review links established during the exposure window. |
| Revoked platform access | Current membership and action authorization govern every decision. An existing link does not preserve a user's prior privileges. |

## Respond to a compromised account or credential

1. Identify the organization, connector and affected provider account. Preserve correlation IDs and timestamps. Keep credentials and challenge codes out of incident records.
2. Revoke compromised provider credentials at the provider and stop using the affected proof route during recovery. Replace the connector's provider credentials where applicable. Rotate the proof secret through the platform's personal organization-admin endpoint and update the provider installation. Rotation invalidates outstanding challenges. Existing links require separate review.
3. Review affected links and revoke suspicious mappings. A user can unlink their own mapping. Managers can inspect links within the selected department. An organization administrator must revoke a shared link or one belonging to another organization administrator. For compromised platform sessions, follow the organization's account recovery process before issuing another challenge. Audit history remains available after unlinking.
4. Recheck connector and account scope, then repeat proof and confirmation from the restored account. A different provider account requires a new proof. Treat pre-rotation and post-rotation credentials as separate when diagnosing failed challenges.

Use the operation, outcome code and request correlation ID to diagnose proof rejection, expiration, replay, rotation, rate limiting and storage unavailability. The audit trail records verified actors and scoped link or connector IDs for link, unlink and secret rotation. Audit records do not contain raw requests, provider tokens or challenge codes.
