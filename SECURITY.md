# Usage Policy

This project is infrastructure for **authorized** security research only:

- Bug-bounty programs, scoped to that program's published rules.
- Systems you own or have explicit written permission to test.
- CTFs and controlled lab environments built for that purpose.

`ScopeGuard` (see `src/agent_core/scope/guard.py`) is designed to make
unauthorized use structurally awkward — it fails closed, requires an
explicit scope file, and logs every decision — but it cannot verify that
the scope file you feed it was actually authorized by the target's owner.
**That verification is on you.** Do not point this at a target you do not
have explicit, current authorization to test.

Contributions that weaken this posture (e.g. "convenience" flags to bypass
`ScopeGuard`, defaults that widen scope silently, or skills that encourage
testing against unauthorized targets) will not be accepted.

If you find a security issue in this project itself, please open a private
security advisory on GitHub rather than a public issue.
