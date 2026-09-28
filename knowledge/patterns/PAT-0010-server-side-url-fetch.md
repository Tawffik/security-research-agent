# PAT-0010 — Server-side URL fetch without allowlist

**Type:** PATTERN  
**Domain:** ssrf  
**Security property:** ssrf  
**Tags:** ssrf, url-fetch, server-side

## Abstraction
User-controlled URL or host is retrieved by the server without strict allowlist / block of link-local and private ranges.

## Not same as
- Client-side only redirects
- Open redirect without server fetch

## Related
CASE-0010 PROC-0010
