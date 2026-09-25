# PAT-0003 — Action-Level Object BOLA (mutate, not only read)

**Type:** PATTERN  
**Status:** DRAFT  
**Primary source:** APIsec Research Labs — analysis of 100+ disclosed BOLA reports (HackerOne 2021–2026)  
**URL:** https://labs.apisec.ai/research/articles/bola-object-level-auth-analysis/  
**Supporting paper:** https://arxiv.org/abs/2605.25865 · dataset notes: https://github.com/hackwither/bola-in-the-wild  

## Why this matters for the agent
Most “IDOR test” mental models optimize for **GET / read**. Field data shows **~41.7%** of confirmed BOLA is **Action-Level Object** (delete/modify/approve/transfer/trigger on another user’s object) and **~46.4%** of cases involve state-changing operations. A research engine that only designs read differentials will systematically miss a large real-world family.

## Abstraction
Attacker is authenticated for the **function**, supplies another user’s **object key**, and performs a **mutating** operation the owner should exclusively control.

## Dominant families (from source classification)
| Family | Share (source) | Agent implication |
|--------|----------------|-------------------|
| Action-Level Object | ~41.7% | Prefer mutation differentials after read signal |
| Direct Object Reference | ~36.9% | Classic key substitution (PAT-0002) |
| Tenant / workflow / chain / rebind | ~21.4% | Later procedures |

## Signals
- DELETE/PATCH/POST-to-trigger endpoints with object id  
- “Destroy account”, token revoke, report delete, storage config delete  
- Same session can call endpoint; ownership not re-checked on mutate  

## Discriminating experiment (minimum)
1. Create object under identity A  
2. As identity B, attempt **one** mutating call on A’s object id  
3. Verify side effect (gone/changed) — status code alone insufficient  
4. Prefer controlled pair over ID spray  

## False-positive traps
- Platform tags “IDOR” that are not object-level (~39% noise in source prefilter)  
- Business logic on **own** resources  
- Auth bypass without object reference (different class)

## Vertical note
~11.9% cases were vertical (lower role acting on higher-privilege-owned objects) while still allowed to call the function — test admin-owned objects when roles exist.

## Linked
- PROC-0003 (mutation BOLA check)  
- PAT-0002 (read-oriented object key)  
- STRAT-0002 (expand matrix beyond GET)

## Skill?
No — pattern only until benchmarked procedure exists.
