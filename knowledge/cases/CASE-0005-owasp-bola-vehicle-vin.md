# CASE-0005 — BOLA on vehicle control API via VIN

**Type:** CASE  
**Status:** EXTRACTED  
**Source:** SRC-0002 OWASP API1:2023  
**Tier:** B — Standards

## Security property
Remote vehicle actions (lock/unlock/engine) only for vehicles owned by the logged-in user.

## Model
- **Object key:** VIN  
- **Actions:** start/stop/lock/unlock  
- **Condition:** vehicle.owner == actor

## Failure mode
API accepts VIN without verifying ownership → control of others' vehicles.

## Minimum experiment
Replay legitimate control request with another VIN under attacker session; require proof of successful unauthorized action (not only HTTP 200).

## Impact class
Integrity + safety-adjacent (high severity when confirmed).

## Skill? No.
