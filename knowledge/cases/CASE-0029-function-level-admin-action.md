# CASE-0029 — Function-level authorization: customer invokes admin action

**Type:** CASE  
**Status:** CURATED (Tier B — OWASP API5 / function-level class; structured like CASE-0001)  
**Domain:** authorization  
**Generalizable:** true  
**Sources:** SRC-0028 (OWASP API5 Broken Function Level Authorization)

## Source
- type: methodology_composite
- related: PAT-0003 (mutation), PAT-0014 (mass assignment role)

## Target
- technology: REST_API
- typical paths: `/api/admin/*`, `/api/users/export`, `/api/reports/generate`

## Security property
authorization / function-level privilege boundary

## Actors
- user_customer (authenticated, role=customer)
- user_admin (authenticated, role=admin)

## Resource
- type: action / capability
- name: admin-only export or delete-all style operation

## Observation pattern (when vulnerable)
Customer session receives 200 and side effect of admin action (export file, global delete marker) without role grant in token.

## Hypothesis
server_checks_authentication_only_not_function_permission

## Experiment
1. As admin: invoke action → record success markers  
2. As customer: identical method/path/body → compare status + side effects  
3. One pair — do not spray all admin routes blindly

## Evidence required
- Both identities and role claims  
- Status codes  
- Side-effect proof (resource created/deleted/exported)  
- Scope ALLOW  

## Alternatives addressed
- Feature intentionally available to all authenticated users (product design)  
- Customer has delegated admin role in IdP (must verify claims)  
- Action is read-only public metrics

## Disproof
Customer consistently 403/404; no admin side effect.

## Root cause
Missing authorization middleware on route; or role check only on UI not API.

## Variants suggested (structural)
- HTTP method override on same path  
- Mobile API twin of admin route  
- GraphQL mutation with same capability name

## Skill promotion
Not a skill. Feeds PAT-0029 + PROC-0029 after benchmarks.
