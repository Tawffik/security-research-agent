"""
agent_core — the control-plane library for the AI security-research agent.

This package implements the "boring but load-bearing" infrastructure that
every autonomous security-research agent needs before it is allowed to
touch a real target:

    scope/              -> ScopeGuard: hard authorization boundary
    content_isolation/  -> Sanitizer: treats all target-origin data as untrusted
    ledger/             -> Execution Ledger: durable, resumable state tree
    evidence/           -> Evidence Store: append-only, hash-chained findings support
    skills/             -> Skill Registry: progressive-disclosure skill loading
    verification/       -> Researcher -> Skeptic -> Referee loop

Nothing in this package performs any offensive action by itself. It has no
knowledge of specific vulnerability classes or payloads — that logic lives
in individual Skills (see /skills), which this library loads, sequences,
and holds accountable for evidence.
"""

__version__ = "0.1.0"
