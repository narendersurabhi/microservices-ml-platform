# Runbook

## Local Debug
- Use `docker compose logs -f <service>` to tail service logs.
- Use `curl http://localhost:8080/health` to verify gateway.

## Common Failures
- **Auth failures**: ensure JWT_SECRET is consistent across services.
- **Scoring timeouts**: case-service will mark `PENDING_SCORE` and emit `score_pending` events.
- **Redis stream lag**: restart audit-telemetry-service to resume consumption.

## Traces and Metrics
- Jaeger UI: http://localhost:16686
- Prometheus UI: http://localhost:9090
- Grafana UI: http://localhost:3000 (default admin/admin)
