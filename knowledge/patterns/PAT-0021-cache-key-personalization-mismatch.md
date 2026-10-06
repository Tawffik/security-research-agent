# PAT-0021 — Cache key misses personalization while body is private

**Type:** PATTERN  
**Domain:** cache  
**Status:** CURATED

## Abstraction
When caches key on URL path/extension but origin returns cookie-specific content,
attackers craft paths that are cached as public yet still execute authenticated handlers.

## Not the same as
- Intentional public caching of marketing pages  
- Client-only browser cache

## Discriminating experiment
Authenticated poison/populate → unauthenticated read of same key; require private markers.
