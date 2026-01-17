# ADR 0001: Edge Gateway Using FastAPI

## Status
Accepted

## Context
We need a lightweight API gateway for local development that enforces JWTs, rate limits, and request ID propagation without requiring an additional managed dependency.

## Decision
Implement an edge gateway using FastAPI with httpx-based proxying and SlowAPI for rate limiting.

## Consequences
- Simple local setup with Python-only runtime.
- Limited advanced gateway features compared to Kong/NGINX, but sufficient for demo purposes.
