# ADR 0003: Schema Versioning Strategy

## Status
Accepted

## Context
We need to show explicit versioning for service contracts while remaining backward compatible.

## Decision
Expose versioned routes (/v1, /v2) and ship JSON Schema contracts in /libs/schemas. Case service introduces a v2 field (priority).

## Consequences
- Clients can migrate at their own pace.
- Contract tests validate schemas against example payloads.
