---
name: Bug report
about: Something in agent_core (scope, ledger, evidence, skills, verification) is broken
labels: bug
---

**Which module?**
`src/agent_core/<scope|ledger|evidence|skills|content_isolation|verification>/...`

**What happened**


**What you expected**


**Minimal reproduction**
```python
# smallest possible script that reproduces it
```

**Does this touch ScopeGuard or the Verification Loop?**
If yes, please be extra explicit — bugs there affect authorization
correctness and false-positive rates, not just convenience.
