# CASE-0007 — GraphQL alternate channel: weak mutation authorization

**Type:** CASE  
**Status:** EXTRACTED  
**Source:** HackerOne Blog — How a GraphQL Bug Resulted in Authentication Bypass  
**URL:** https://www.hackerone.com/blog/how-graphql-bug-resulted-authentication-bypass  
**Tier:** A/B — platform research writeup (ecommerce promo integration)

## Security property
Sensitive mutations (register, create admin, modify promo content) must enforce authentication and authorization per operation — schema exposure ≠ permission.

## Model
- **Channel:** GraphQL on third-party subdomain embedded in main site  
- **Signals:** introspection enabled → enumerate mutations  
- **Failure:** Register / CreateAdminUser (and further content mutations) callable without adequate access control  
- **Impact path:** privilege escalation → modify front-page promotional banner/product details  

## Researcher process (useful for agent)
1. Discover GraphQL endpoint  
2. Introspection / schema map  
3. Authorization checks on restricted mutations  
4. Sensitive field analysis  

## Distinction
This is closer to **broken function-level / missing auth on operations** than classic single-object BOLA — still “authorization research”, different hypothesis family.

## Agent implications
- GraphQL adapter later: treat each mutation as its own authorization surface  
- Do not equate “authenticated to site” with “authorized for mutation X”  
- Introspection is reconnaissance signal, not the vulnerability itself  

## Root cause (source emphasis)
Missing explicit authorization on each query/mutation; excess admin functionality exposed on API.

## Skill? No.
