# CASE-0001 — Lab: Cross-Identity Order Object Access

**Type:** CASE  
**Status:** DRAFT (from deterministic lab closed-loop; not production BB)  
**Domain:** authorization  
**Generalizable:** true

## Source
- type: internal_lab
- path: examples/fixtures/sample_recon.json + LabScenario default_idor_lab_scenario

## Target
- technology: REST_API
- host (lab): api.acme-demo.test

## Security property
authorization / object ownership

## Actors
- user_a (owner)
- user_b (non-owner)

## Resource
- type: object
- name: order-1001

## Observation
attacker (user_b) retrieved resource owned by victim (user_a) with status 200 and matching private fields

## Hypothesis
server_does_not_verify_object_ownership

## Experiment
cross_identity_resource_access (GET /api/orders/{id} as A then B)

## Evidence required
- response_status both identities
- response_body ownership markers
- actor_resource_relationship from recon model

## Result
confirmed (lab only)

## Alternatives addressed
- shared ACL: not present in body
- public endpoint: auth_required true in model
- role grant: both actors customer role

## Root cause (lab-derived)
Missing or inconsistent server-side ownership enforcement — signature: resource_resolver + missing_ownership_middleware

## Variants suggested (structural)
- GET /api/users/{id}
- GET /api/invoices/{id}

## Skill promotion
Not a skill. Feeds PAT-0001 pattern only after more cases + benchmark.
