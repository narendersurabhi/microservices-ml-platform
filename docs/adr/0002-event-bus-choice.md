# ADR 0002: Redis Streams for Event Bus

## Status
Accepted

## Context
Services need to publish and consume events (case created, score updated) without heavyweight infrastructure.

## Decision
Use Redis Streams as the event bus for local development.

## Consequences
- Lightweight and easy to run in docker-compose.
- Consumers need to handle at-least-once delivery semantics.
