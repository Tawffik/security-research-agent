# NEG-0002 — Encoded reflection is not XSS

**Type:** NEGATIVE / FP GUIDANCE  
**Domain:** xss  
**Security property:** xss  
**Tags:** negative, false_positive, xss  

## Abstraction
Seeing a user string in the response is not XSS if context-appropriate encoding prevents interpretation as markup/script.
