# Runbook: Emergency Catalog Recovery

## Runbook ID: RB-TMF620-001
## Severity: P1 (Critical)

## Scenario 1: Complete API Unavailability
**Symptoms:** All endpoints returning 503, health endpoint DOWN
**Root Cause:** Database failover or pod OOM kill causing cascade failure
**Resolution Steps:**
1. Check application health: curl -s https://api.internal/tmf620/health
2. Check Kubernetes pods: kubectl get pods -n product-platform
3. If CrashLoopBackOff: check logs, rollback deployment
4. If database lost: check PostgreSQL, force failover if needed
5. Verify health endpoint after recovery

## Scenario 2: Stale Catalog Data After Bulk Import
**Symptoms:** New products not visible, updated details show old values
**Root Cause:** Elasticsearch index out of sync
**Resolution Steps:**
1. Compare DB vs index count
2. Trigger reindex: POST /admin/index/rebuild
3. Monitor progress
4. Verify counts match

## Scenario 3: Performance Degradation
**Symptoms:** P95 latency > 2 seconds
**Root Cause:** Low cache hit rate, slow DB queries, or pod saturation
**Resolution Steps:**
1. Check cache hit rate (target > 80%)
2. Check slow queries: pg_stat_statements
3. Scale horizontally if pods saturated
4. Check for missing indexes
