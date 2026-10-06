# PAT-0013 — Unencoded reflection into HTML document context

**Type:** PATTERN  
**Domain:** xss  
**Status:** CURATED

## Abstraction
User-controlled data is written into an HTML response without encoding appropriate to the
surrounding context, enabling script execution or HTML injection when the browser parses it.

## Not the same as
- Encoded reflection that only “looks like” the payload in view-source differences  
- JSON API responses consumed by a safe client serializer  
- Stored content that is encoded on output (input storage alone is not the bug)

## Discriminating experiment
Classify context → baseline marker → challenge encoding boundaries → observe execution necessity.

## Related
CASE-0013, PROC-0013, NEG-0002, NEG-0006
