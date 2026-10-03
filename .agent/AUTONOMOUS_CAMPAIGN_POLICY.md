# Autonomous Campaign Policy

## LOCAL BLOCKER ≠ CAMPAIGN BLOCKER

A human dependency or missing live environment blocks **only the affected capability**.
It does **not** terminate the entire campaign while independent safe work remains.

## Terminal states (only)

| State | When |
|-------|------|
| `CAMPAIGN_COMPLETE` | All required roadmap dependencies verified; remaining items optional/deferred only |
| `CAMPAIGN_BLOCKED` | All safe independent work exhausted **and** remaining required work is external/human-blocked |

Non-terminal: task complete, sub-gate complete, tests green, commit created, report written, session ended, single capability blocked, deferred items present.

## Dependency states

`COMPLETE` · `IN_PROGRESS` · `READY` · `DEFERRED` · `BLOCKED` · `HUMAN_ACTION_REQUIRED`

- `DEFERRED ≠ BLOCKED ≠ COMPLETE`
- Deferred items must retain reason, priority, return condition

## Gate 6 special rule

Gate 6 (Real BugBountyCI E2E) requires authorized live environment + scope + credentials + target approval.

If unavailable:
```
Gate 6 = BLOCKED (local)
→ record resume condition
→ continue Gate 7 / Gate 8 / knowledge / offline / offline offline work
```

Never: fake live results, bypass ScopeGuard, infer authorization, mark Gate 6 complete.

## Mandatory precheck before CAMPAIGN_BLOCKED

```
RECONCILE REPO → CONTROL PLANE → ENUMERATE DEPENDENCIES → CLASSIFY
→ EXPAND BLOCKERS → CHECK SIBLINGS/DOWNSTREAM → SEARCH OFFLINE WORK
→ ANY READY WORK? YES → CONTINUE / NO → external blocker? → BLOCKED
```

Forbidden: `Gate 6 blocked → campaign blocked`

## Human action

Record exact action, affected dependency, resume condition; continue unrelated work.

## Session resume

Read STATE → CURRENT_TASK → actual HEAD → tests → reconcile → continue.
Never restart from Gate 0 solely because the session changed.
