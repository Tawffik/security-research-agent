# CASE-0033 — Action-level object BOLA (state-changing on another’s object)

**Type:** CASE  
**Status:** CURATED (Tier A/B — empirical BOLA taxonomy; Action-Level Object family)  
**Domain:** authorization  
**Generalizable:** true  
**Sources:** SRC-0032 (BOLA-in-the-wild taxonomy 2026), OWASP API1

## Source
- Empirical note: action-level object BOLA is a *dominant* disclosed family alongside direct object reference reads.
- Distinct from function-level admin routes (CASE-0029): here the *function* is allowed to the role, but the *object* is not.

## Target
- technology: REST_API | GraphQL mutation
- examples: `POST /orders/{id}/cancel`, `PATCH /docs/{id}`, `DELETE /comments/{id}`, share/transfer endpoints

## Security property
authorization / object ownership on **state-changing** actions

## Actors
- user_a (owner of object O)
- user_b (authenticated peer, same role, not owner of O)

## Resource
- type: object + action
- object key: path/body id of O
- action: mutate/delete/share/cancel (not merely GET)

## Observation pattern (when vulnerable)
B successfully changes state of A’s object (status flip, field write, delete marker) with 2xx and durable side effect.

## Hypothesis
server_authorizes_action_for_role_but_not_object_binding

## Minimum discriminating experiment
1. As A: create or identify owned object O; record state S0  
2. As A: perform sensitive action on O → success baseline S1  
3. As B: **same method + same object key** → compare status and durable state  
4. Prefer one controlled pair — no ID spray

## Evidence required
- Both identities and ownership of O  
- Pre/post state of O  
- Response status **and** side effect (GET-after or list membership)  
- Scope ALLOW  

## Alternatives addressed
- Shared workspace / explicit ACL grant to B  
- Public “anyone can cancel unpaid orders” product rule  
- Idempotent no-op that looks like 200 without state change

## Disproof / falsification
B receives 403/404; object state unchanged when re-read as A.

## Root cause
Role check without ownership bind on mutating handlers; or IDOR tested only on GET.

## Variants
- Soft-delete vs hard-delete  
- Batch mutate with mixed owned/foreign ids  
- GraphQL mutation with Global ID of foreign object

## Skill promotion
No — feeds PAT-0033 / PROC-0033; needs lab + utility benchmark.
