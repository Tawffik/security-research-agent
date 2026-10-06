# PAT-0036 — HTTP request boundary desync

**Type:** PATTERN  
**Domain:** smuggling  
**Status:** CURATED

## Abstraction
When two HTTP parsers disagree on where a request ends, attackers can prepend/smuggle a second request.

## Not the same as
- Normal reverse-proxy routing errors without framing disagreement  
- HTTP/2 clean end-to-end (different class)
