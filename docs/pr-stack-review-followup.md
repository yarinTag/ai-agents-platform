# Follow-up to the supplied review of PR49/50/51/57/58

## Subsequent publication and validation

Production dashboard build and tsc --noEmit passed on 2026-11-20, including the
isolated prepared publication checkout. Only the existing large-chunk build warning
remains. Review fixes were committed/pushed to PR49/50/51/57 and propagated into
PR58 without force-push. New AI-51/52/55 work is a separate draft PR59:
https://github.com/yarinTag/ai-agents-platform/pull/59 . No merge or deployment;
backend tests/database/cluster/provider checks were not run locally. Earlier
unpublished/unverified statements below describe the preceding review task.

2026-11-20. Source inspection and local fixes only. The five non-Dependabot PRs
remain open in the reported stack according to a read-only GitHub query. No CI
run, browser, tests, typecheck, worker, model or provider action was executed.
Local uncommitted source is not identical to all PR heads; these fixes are not
published to those branches and do not establish their merge readiness.

| Review item | Assessment and action |
| --- | --- |
| Stale channel loading failure | Confirmed: reset failed/bindings on department changes, including no department; abort still fences late responses. Reset linked/checks on preview connector/admin changes. |
| Index React keys | Confirmed: mapping rows get a stable per-component numeric rowId that survives edits/removal. rowId is UI-only; save/preview still serialize name/source only. |
| tmpfs capacity >= worker memory | Confirmed configuration risk: strict SandboxProfile validation requires scratch_mib < memory_mib. No arbitrary half-memory policy introduced. This is not an OOM guarantee; workload headroom remains an acceptance concern. |
| Local failure retains paid reservation | Partially confirmed: command/profile/environment setup failures now return cost_usd=0 before spawning. OS failure with no child also reports zero; after a child exists it reports unknown cost. |
| Timeout/cancel/no-result budget hold | Intentional conservative behavior: a launched child may have sent a paid HTTP request. No result is not evidence of no charge. UNKNOWN remains reserved; no TTL/automatic zero settlement introduced. A worker crash before HTTP cannot be distinguished safely without trusted dispatch evidence. |
| Trigger UTC/local mixture | Not an observed cooldown bug: the query joins channel_trigger_dispatches, whose execution rows are written by reserve_dispatches in UTC. Added an explicit invariant comment; global timestamp normalization is separate work. |
| Provider inferred from message_id | Valid technical debt. Current binding/connector metadata alone cannot reconstruct the historical provider after deletion or mutation. A future change should persist provider on delivery and define an unknown legacy fallback. Not changed in this patch. |
| Local Socket Mode flock | Valid deployment limitation, not new evidence of duplicate live consumers. Multi-host transport ownership needs distributed lease/fencing before multi-replica activation. Not changed. |
| Runner create idempotency | Review heading is inaccurate: existing identical plan is returned before lifetime checks. Future requested_at clock skew is a distinct admission/time-authority design issue. No deadline reset or permissive skew allowance added. |
| Runner NOT_DISPATCHED guard | Known conservative limitation in inactive PR58. The proposed kind-only one-liner does not establish per-operation dispatch/receipt provenance across Stop/Delete and future resources. Keep the guard until per-operation effect evidence is integrated. |

## Source changes and evidence

- Dashboard ChannelApprovalFields and ChannelTriggerPanel implement the state/key
  fixes without new strings, API payload fields or permission changes.
- governance/sandbox_profile.py adds the tmpfs relation check, also enforced by
  existing revalidation at manifest/plan boundaries. Two denial source cases added.
- runtime/workflow_chat.py contains bounded sanitized setup/OS errors. Setup paths
  return definite zero only before a child exists; post-launch uncertainty remains
  untouched. Existing hosted_budget.settle semantics are unchanged.
- Channel relevance test source covers invalid selection before launch and real
  SQLite UNKNOWN reservation retention even after a later zero-settlement attempt.

Only git diff --check and physical source line counts were checked. Tests remain
unexecuted under repository instructions. No PR head/status/check result was
modified and no blanket endorsement of the supplied review's CI claims is made.

## Publication validation
Production dashboard build and tsc --noEmit passed on 2026-11-20. Build reports an
existing large-chunk warning. Review fixes were prepared on the corresponding
PR49/50/51/57 branches and propagated to PR58; new PostgreSQL work is a separate
stacked branch. No backend test, database, cluster or provider verification run.
