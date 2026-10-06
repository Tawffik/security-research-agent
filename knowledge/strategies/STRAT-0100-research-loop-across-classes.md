# STRAT-0100 — Evidence-driven loop is class-agnostic

**Type:** STRATEGY  
**Domain:** general  
**Status:** CURATED

## Guidance
For **any** vulnerability class the agent must still run:
Opportunity → Knowledge (domain-aligned) → Competing hypotheses → Minimum discriminating experiment
→ Evidence (positive + negative) → Falsification → Sufficiency → Referee

Never: payload spray as “research.”  
Never: one HTTP status as confirmation.  
Never: knowledge retrieval as execution permission.

## Class routing (methodology, not hard-coded engines)
| Signal in target context | Prefer knowledge domain |
|--------------------------|-------------------------|
| object ids + multi-user | authorization |
| server-side URL fetch | ssrf |
| HTML reflection | xss |
| SQL/XML/template sinks | injection |
| session/JWT/oauth | authentication |
| stock/coupon/state | business_logic |
| Cache-Control/CDN | cache |
| file path/name | traversal / upload |

## Quality invariant
Each class uses the same bar: actors, property, baseline/challenge, disproof, root cause.
