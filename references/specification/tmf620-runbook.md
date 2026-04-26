# TMF620 Product Catalog — Runbook: Emergency Catalog Recovery

## Runbook ID: RB-TMF620-001
## Severity: P1 (Critical)
## Last Updated: 2026-04-20
## Owner: Product Platform Team

## Context
This runbook covers recovery scenarios when the TMF620 Product Catalog API becomes fully or partially unavailable, impacting customer-facing product browsing and ordering.

## Alert Trigger
- Alert: `TMF620_Catalog_API_Down` fires when health endpoint fails 3 consecutive checks (30s interval)
- Dashboard: Grafana → Product Platform → TMF620 Overview
- PagerDuty: Routes to Product Platform on-call

## Scenario 1: Complete API Unavailability

### Symptoms
- All `/productOffering`, `/productSpecification`, `/productCatalog` endpoints return 503
- Health endpoint `GET /health` returns `{"status": "DOWN"}`
- Customer-facing catalog page shows "Products unavailable"

### Diagnosis
```bash
# Step 1: Check application health
curl -s https://api.internal/tmf620/health | jq .status

# Step 2: Check Kubernetes pods
kubectl get pods -n product-platform -l app=tmf620-api

# Step 3: Check recent deployments
kubectl rollout history deployment/tmf620-api -n product-platform

# Step 4: Check database connectivity
kubectl exec -n product-platform deploy/tmf620-api -- pg_isready -h postgres-primary -p 5432

# Step 5: Check Redis cache
kubectl exec -n product-platform deploy/tmf620-api -- redis-cli -h redis-cluster ping
```

### Resolution
1. **If pods are CrashLoopBackOff:**
   - Check logs: `kubectl logs -n product-platform deploy/tmf620-api --tail=100`
   - Common cause: failed database migration on deploy
   - Rollback: `kubectl rollout undo deployment/tmf620-api -n product-platform`
   - Verify: wait 60s, check health endpoint

2. **If database connectivity lost:**
   - Check PostgreSQL: `kubectl get pods -n data -l app=postgres`
   - If primary failed, check replica promotion: `patronictl list`
   - Force failover if needed: `patronictl failover --force`
   - Verify TMF620 connection: restart pods after DB recovery

3. **If Redis unavailable:**
   - Product catalog reads cache first, DB second
   - Service degrades but doesn't fully fail without Redis
   - Check Redis cluster: `redis-cli --cluster check redis-0:6379`
   - If cluster split-brain, follow [[Redis Cluster Recovery]] runbook

### Verification
```bash
# Full health check
curl -s https://api.internal/tmf620/health
# Expected: {"status": "UP", "db": "UP", "cache": "UP", "search": "UP"}

# Functional test
curl -s https://api.internal/tmf620/productOffering?limit=5 | jq '.[0].name'
# Expected: returns product name

# Customer-facing check
curl -s https://catalog.example.com/api/products | jq '.items | length'
# Expected: > 0
```

## Scenario 2: Stale Catalog Data After Bulk Import

### Symptoms
- New products not visible in catalog search
- Updated product details show old values
- `GET /productOffering` returns correct data but catalog search is wrong

### Diagnosis
```bash
# Check index vs DB count
DB_COUNT=$(kubectl exec -n data deploy/postgres -- psql -U tmf620 -t -c "SELECT COUNT(*) FROM product_offering WHERE lifecycle_status='Active'")
API_COUNT=$(curl -s 'https://api.internal/tmf620/productOffering?lifecycleStatus=Active&limit=1' | jq '."@totalCount"')
echo "DB: $DB_COUNT, Index: $API_COUNT"

# Check index lag
curl -s https://api.internal/tmf620/admin/index/status | jq '.lag_seconds'
```

### Resolution
1. If counts mismatch or lag > 60s, trigger reindex:
   ```bash
   curl -X POST https://api.internal/tmf620/admin/index/rebuild
   ```
2. Monitor progress (typically 2-5 min for 100K products):
   ```bash
   watch -n 10 'curl -s https://api.internal/tmf620/admin/index/status | jq "{progress: .progress_pct, eta: .eta_seconds}"'
   ```
3. Verify counts match after reindex completes
4. If reindex fails, check Elasticsearch disk space:
   ```bash
   curl -s elasticsearch:9200/_cat/allocation?v
   ```

### Prevention
- CDC pipeline (Debezium) auto-syncs DB changes to index
- Monitor CDC lag: alert if > 30 seconds
- Weekly full reindex scheduled: Sunday 03:00 UTC

## Scenario 3: Performance Degradation — Slow API Responses

### Symptoms
- P95 latency > 2 seconds (SLA threshold: 500ms)
- Customer complaints about slow catalog browsing
- Grafana shows rising response times

### Diagnosis
```bash
# Check current latency
curl -s https://api.internal/tmf620/metrics | grep 'http_server_requests_seconds{uri="/productOffering"'

# Check database query performance
kubectl exec -n data deploy/postgres -- psql -U tmf620 -c "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10"

# Check cache hit rate
curl -s https://api.internal/tmf620/metrics | grep 'cache_hit_rate'

# Check pod resource usage
kubectl top pods -n product-platform -l app=tmf620-api
```

### Resolution
1. **Low cache hit rate (< 80%):**
   - Check Redis memory: `redis-cli info memory`
   - If memory full, increase maxmemory or evict cold keys
   - Verify TTL settings: catalog data should cache for 5 minutes

2. **Slow database queries:**
   - Check for missing indexes: `EXPLAIN ANALYZE` on slow queries
   - Common fix: `CREATE INDEX CONCURRENTLY idx_po_lifecycle ON product_offering(lifecycle_status, catalog_id)`
   - Vacuum if table bloat: `VACUUM ANALYZE product_offering`

3. **Pod resource saturation:**
   - Scale horizontally: `kubectl scale deployment/tmf620-api --replicas=5 -n product-platform`
   - Check if HPA is configured: `kubectl get hpa -n product-platform`

### Related Runbooks
- [[Redis Cluster Recovery]]
- [[PostgreSQL Performance Tuning]]
- [[Kubernetes HPA Configuration]]
- [[Elasticsearch Cluster Health]]

## Escalation Path
| Level | Team | Contact | SLA |
|-------|------|---------|-----|
| L1 | Product Platform On-Call | PagerDuty | 15 min response |
| L2 | Product Platform Lead | Slack: #product-platform | 30 min |
| L3 | Architecture Team | Slack: #architecture | 1 hour |
| Vendor | TMF620 vendor support | Support portal | 4 hours |
