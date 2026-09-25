# CASE-0006 — Profile IDOR → email change → zero-click ATO

**Type:** CASE  
**Status:** EXTRACTED (Tier A — primary writeup)  
**Notion:** Real Bounty — Profile IDOR to ATO / Top Writeups  
**Primary URL:** https://blog.abdulaziz-d.com/from-profile-idor-to-zero-click-account-takeover-changing-one-userid-parameter-was-enough  
**Reported severity:** Critical · Bounty noted in source: $1,805 · Platform: Bugbounty.sa (private program)

## Security properties violated
1. Only the account owner may **read** full profile management fields.  
2. Only the account owner may **modify** primary email / profile state.  
3. Password reset must not become an ATO oracle after unauthorized email change.

## Target model
- **Actor:** low-privileged authenticated user A  
- **Action:** POST profile update / load  
- **Resource:** registration/profile update endpoint  
- **Object key:** client-supplied `userid`  
- **Expected condition:** target user == authenticated session user (or explicit admin grant)

## What the researcher initially believed
Possible horizontal IDOR on profile read.

## What changed the belief
Server returned **editable** profile form for User B while session was User A — trust of `userid` for both load **and** update.

## Decisive experiments
1. Two controlled accounts; as A set `userid=B` → B’s full profile fields in response (PII).  
2. As A, keep `userid=B`, change primary email to attacker-controlled → accepted.  
3. Legitimate password-reset to new email → ATO without victim interaction.

## Alternatives considered
- Password-reset feature itself is **not** the root bug; it behaved as designed.  
- Root failure: missing object-level authorization on `userid` for read+write.

## Root cause
Client-supplied object key used as authorization context instead of session-bound identity.

```text
Authentication answered: "who are you?"
Authorization failed: "may you access this account object?"
```

## Evidence requirements (for agent)
- Session A identity  
- Object key B  
- Response showing B’s sensitive fields and/or successful state change  
- Chain steps only after write IDOR proven (do not claim ATO from read-only 200)

## Stop / impact discipline
- Report read IDOR if write fails  
- Escalate to ATO only with reproducible email change + reset proof  
- No mass userid spray required once pattern confirmed on controlled pair

## Linked abstractions
- PAT-0001, PAT-0002  
- PROC-0001 (cross-identity object)  
- PROC-0002 (object-key substitution)  
- Future: procedure for “read IDOR inside state-changing form → test write”

## Skill?
**No** — primary case for knowledge graph only.
