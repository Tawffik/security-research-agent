# CASE-0034 — Vertical object authorization failure (user → admin-shaped object)

**Type:** CASE  
**Status:** CURATED (Tier B — ~12% vertical share in empirical BOLA sample)  
**Domain:** authorization  
**Generalizable:** true  
**Sources:** SRC-0032

## Security property
authorization / privilege boundary on objects reserved for higher roles

## Actors
- user_low (standard role)
- user_admin (admin role)

## Resource
Admin-shaped object: `/api/admin/users/{id}`, audit records, billing configs keyed by id

## Observation pattern (when vulnerable)
Low user reads or mutates admin object representation that should require elevated role.

## Hypothesis
object_route_reachable_without_role_gate

## Minimum experiment
1. Admin baseline access to object R  
2. Low user same request to R  
3. Compare private admin fields / mutate success

## Evidence required
Role claims, response bodies, side effects

## Alternatives
- Low user legitimately delegated admin scope in IdP  
- Object is intentionally tenant-visible metadata

## Disproof
Low user 403; no admin fields

## Root cause
Missing role gate on admin resource controllers; or security only in SPA routes

## Linked
PAT-0029 (function), PAT-0001 (object), PROC-0034
