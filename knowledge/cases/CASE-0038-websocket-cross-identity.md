# CASE-0038 — WebSocket message channel missing object/session bind

**Type:** CASE  
**Status:** CURATED (Tier B)  
**Domain:** authorization  
**Generalizable:** true

## Security property
WS messages that address objects/rooms must enforce membership/ownership like HTTP

## Actors
user_a, user_b

## Observation pattern (when vulnerable)
B subscribes or reads A’s private channel/object over WS after connect

## Hypothesis
ws_auth_only_at_handshake_not_per_message

## Minimum experiment
1. A opens private channel/object events  
2. B connects with own session; requests A’s id/room  
3. Diff event payloads

## Evidence required
Both sessions, message transcripts

## Disproof
B never receives A’s private events

## Root cause
Authorization only on HTTP upgrade, not on subscribe/message handlers
