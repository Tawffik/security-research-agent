# Skill: authz-idor-analysis

## Purpose
Generate and structure HYPOTHESES about object- and function-level
authorization boundaries. This skill reasons about *invariants*, per
MASTER SPEC §6 ("Business Logic" / "Authorization" family) — it does not
just try random object IDs.

## Precondition
You need at least two legitimately-owned, authorized test identities
(e.g. two accounts the researcher controls under the bounty program's own
rules) before this skill can produce anything beyond a hypothesis. Without
a second identity there is nothing to diff against, and the skill should
mark itself `BLOCKED` in the Ledger rather than guess.

## Procedure
1. From the Target Graph, enumerate every endpoint that accepts an
   object identifier (path param, query param, or body field) and is
   reachable by an authenticated identity.
2. For each such endpoint, state the INVARIANT that should hold, e.g.:
   "identity A can only retrieve/modify objects it owns or has been
   explicitly granted access to." Write this invariant explicitly into
   the Hypothesis node — the invariant, not the payload, is the unit of
   reasoning here.
3. Design the SMALLEST possible controlled experiment that could falsify
   the invariant: the same request, issued by identity A, but referencing
   an object legitimately owned by identity B (where B is also a
   researcher-controlled account under program rules). Never target a
   real third-party user's data to test a hypothesis — that crosses from
   "controlled experiment" into "unauthorized access," which ScopeGuard
   must refuse regardless of how promising the hypothesis looks.
4. Record BOTH the request and response as Evidence, tagged with the
   `related_hypothesis` id, whether or not the boundary held. A held
   boundary is valuable NEGATIVE evidence — it means this endpoint class
   does not need to be re-tested after a restart.
5. Hand the hypothesis + evidence to the VerificationLoop. This skill must
   never mark its own hypothesis CONFIRMED — that decision belongs to the
   Researcher -> Skeptic -> Referee loop, specifically so the same
   reasoning pass that found the issue is not the one that approves it.

## Skeptic prompts this skill should expect to be challenged with
- Could identity A have been legitimately granted access to B's object
  (e.g. a share, a team membership, a support role)?
- Is the differing response explained by caching rather than an
  authorization gap?
- Is this endpoint intentionally public read-only data?

## Evidence requirements
A CONFIRMED finding from this skill must include: the exact request for
both identities, the diffed response bodies, and an explicit statement of
which invariant was violated.
