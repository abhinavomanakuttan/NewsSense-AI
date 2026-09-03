# Monitoring

SmartFeed exposes Prometheus metrics from the FastAPI backend and ships a
pre-configured Prometheus + Grafana stack under `infra/monitoring/`.

## Backend /metrics endpoint

The backend exposes a standard Prometheus text-format endpoint at
`GET /metrics` (requires no auth, same as `/health`). It is emitted by
`app/core/metrics.py` and enabled automatically — there is no flag to turn it
on or off.

### Metrics

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `http_requests_total` | Counter | `method`, `path`, `status` | Request count per normalized route |
| `http_request_duration_seconds` | Histogram | `method`, `path`, `status` | Request latency (buckets up to 30s) |
| `http_requests_inflight` | Gauge | `method`, `path` | Concurrent in-flight requests |
| `ws_connections_active` | Gauge | – | Open WebSocket connections |
| `notifications_dispatched_total` | Counter | – | Notifications pushed over WebSocket/Redis |
| `articles_ingested_total` | Counter | – | New articles persisted from feed fetches |
| `enrichment_runs_total` | Counter | – | Enrichment pipeline runs |

Paths are normalized so high-cardinality segments (UUIDs) collapse to `{id}`
(e.g. `/api/v1/sources/{id}/refresh`), keeping the label set bounded.

### Querying directly

```bash
curl http://localhost:8000/metrics
```

## Local dashboard stack

The `infra/docker-compose.yml` includes:

- **Prometheus** – scrapes the backend job (`backend:8000`) every 15s.
  Config: `infra/monitoring/prometheus.yml`.
- **Grafana** – dashboards auto-provisioned from
  `infra/monitoring/grafana/dashboards/backend.json`, datasource from
  `infra/monitoring/grafana/datasources/prometheus.yml`.

Start it:

```bash
cd infra
docker-compose up -d prometheus grafana
```

Access:

- Grafana: http://localhost:3001 (admin / admin)
- Prometheus: http://localhost:9090

The "SmartFeed Backend" dashboard includes request rate, 5xx error rate,
latency p95/p99, active WebSockets, and pipeline activity (notifications,
ingested articles, enrichment runs).

## Adding or editing dashboards

Edit `infra/monitoring/grafana/dashboards/backend.json` (or add a new JSON
file in that directory) and restart Grafana — provisioning reloads from disk:

```bash
docker-compose restart grafana
```

## Alerting

Grafana alert rules can be added from the dashboard UI, or by adding
`infra/monitoring/grafana/provisioning/alerting.yml` for rule provisioning.
Suggested starting points:

- 5xx rate > 0 for 5m
- p99 latency > 5s for 5m
- `up == 0` for the backend job for 2m (backend down)

## Verification

Run the metrics test suite (covers the endpoint, normalization, and counters):

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests\api\test_metrics.py
```
