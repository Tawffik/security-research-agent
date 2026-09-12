## What this changes


## Which Phase (per docs/ROADMAP.md) does this belong to?


## Checklist
- [ ] Tests added/updated (`pytest` passes locally)
- [ ] `python examples/run_demo.py` still runs end-to-end
- [ ] If this touches `ScopeGuard`: I did not add a way to bypass or widen
      scope silently (see `SECURITY.md`)
- [ ] If this touches `VerificationLoop`: a finding still cannot reach
      `CONFIRMED` without a Skeptic actually attempting disproof
- [ ] If this adds a Skill: `SKILL.md` states an invariant, cites evidence
      requirements, and does not self-approve findings
- [ ] Docs updated (`README.md` / `docs/ARCHITECTURE.md` / `docs/ROADMAP.md`)
      if this changes the shape of the system
