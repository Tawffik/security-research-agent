# CASE-0031 — Stored value rendered in privileged HTML without encoding

**Type:** CASE  
**Status:** CURATED (Tier B — stored XSS class; structured like CASE-0001)  
**Domain:** xss  
**Generalizable:** true

## Security property
output encoding in privileged HTML contexts

## Actors
- user_low (can write a field)
- user_admin (views field in admin HTML UI)

## Resource
stored string field (name, comment, filename)

## Observation pattern (when vulnerable)
Admin HTML includes raw low-user content in executable context.

## Hypothesis
storage_path_encodes_nothing_admin_template_unsafe

## Experiment
1. Low user stores unique marker  
2. Admin opens view that should display it  
3. Classify context; test encoding boundary

## Evidence required
- Stored marker  
- Admin response snippet with context  
- Encoding behavior  

## Alternatives
- Admin API returns JSON only (NEG-0006)  
- Encoding on output present

## Disproof
Admin HTML fully encodes; or no HTML sink

## Root cause
Missing contextual encoding on privileged renderer

## Skill promotion
No — pattern PAT-0013 + stored variant notes only
