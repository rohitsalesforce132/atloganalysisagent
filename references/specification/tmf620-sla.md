# TMF620 Product Catalog API — Service Level Agreement

## Document ID: SLA-TMF620-2026-Q2
## Effective Date: 2026-04-01
## Review Date: 2026-07-01
## Stakeholders: Product Platform Team, Enterprise Architecture, Customer Operations

## 1. Service Description
TMF620 Product Catalog Management API provides RESTful endpoints for managing product offerings, product specifications, and product catalogs. It serves as the product data backbone for all customer-facing sales channels (web, mobile, partner portal, B2B API).

## 2. Service Level Objectives (SLOs)

### 2.1 Availability
| Metric | Target | Measurement |
|--------|--------|-------------|
| API Availability | 99.95% | (Total minutes - Downtime minutes) / Total minutes per month |
| Product Offering Read | 99.99% | Successful GET responses / Total GET requests |
| Product Offering Write | 99.95% | Successful POST/PATCH/DELETE responses / Total write requests |
| Catalog Search | 99.90% | Successful search responses / Total search requests |

**Exclusions from availability calculation:**
- Scheduled maintenance windows (Sunday 02:00-04:00 UTC, announced 72h in advance)
- Force majeure events (cloud provider region outage)
- Client-side errors (4xx responses)

### 2.2 Latency
| Endpoint | P50 Target | P95 Target | P99 Target |
|----------|------------|------------|------------|
| `GET /productOffering/{id}` | 50ms | 200ms | 500ms |
| `GET /productOffering` (list) | 100ms | 500ms | 1000ms |
| `POST /productOffering` | 200ms | 800ms | 1500ms |
| `PATCH /productOffering/{id}` | 150ms | 600ms | 1200ms |
| `GET /productCatalog/{id}/productOffering` | 150ms | 500ms | 1000ms |
| `GET /productSpecification/{id}` | 50ms | 200ms | 500ms |

**Measurement:** Server-side processing time (excludes network transit). Measured via Prometheus histograms at the API gateway.

### 2.3 Throughput
| Tier | Rate Limit | Burst Allowance |
|------|------------|-----------------|
| Standard | 100 req/min | 20 req burst |
| Premium | 500 req/min | 100 req burst |
| Internal (microservices) | 2000 req/min | 500 req burst |
| Bulk Operations | 20 req/min | No burst |

### 2.4 Data Freshness
| Metric | Target |
|--------|--------|
| Catalog search index lag | < 30 seconds after write |
| Cache invalidation | < 5 seconds after write |
| Cross-region replication | < 60 seconds |

### 2.5 Error Budget
- Monthly error budget: 0.05% of total requests (based on 99.95% availability SLO)
- Error budget resets monthly
- Error budget tracking: Grafana → TMF620 → Error Budget Dashboard
- When 80% of error budget consumed: alert to Product Platform Lead for review

## 3. Incident Response SLAs

### 3.1 Severity Definitions
| Severity | Definition | Examples |
|----------|------------|----------|
| P1 (Critical) | Complete service outage or data corruption | All endpoints returning 5xx, data loss detected |
| P2 (High) | Major feature degraded, significant customer impact | Catalog search stale by > 5 minutes, write latency > 5s |
| P3 (Medium) | Minor feature degraded, limited customer impact | Single endpoint slow, cache miss rate > 40% |
| P4 (Low) | Cosmetic or informational issue | Incorrect field in API docs, metric discrepancy |

### 3.2 Response Times
| Severity | Acknowledgment | Update Frequency | Target Resolution |
|----------|---------------|------------------|-------------------|
| P1 | 15 minutes | Every 30 minutes | 4 hours |
| P2 | 30 minutes | Every 60 minutes | 8 hours |
| P3 | 2 hours | Daily | 24 hours |
| P4 | 1 business day | As needed | Next sprint |

### 3.3 Escalation Matrix
| Time Since P1 Detection | Escalation |
|--------------------------|------------|
| 0-15 min | L1 On-Call responds |
| 15-30 min | L2 Product Platform Lead joins |
| 30-60 min | Architecture Team engaged |
| 60-120 min | VP Engineering notified |
| > 120 min | CTO incident bridge opened |

## 4. Disaster Recovery

### 4.1 Recovery Time Objective (RTO)
| Scenario | RTO | RPO |
|----------|-----|-----|
| Single pod failure | 30 seconds (auto-restart) | 0 (no data loss) |
| Node failure | 2 minutes (pod reschedule) | 0 |
| Database failover | 5 minutes (Patroni) | < 10 seconds |
| Region failover | 30 minutes | < 1 minute |
| Full platform rebuild | 4 hours | < 1 hour (from backup) |

### 4.2 Backup Policy
- PostgreSQL: Continuous WAL archiving + daily full backup (retained 30 days)
- Elasticsearch: Daily snapshot (retained 14 days)
- Redis: RDB snapshot every 15 minutes + AOF persistence
- Configuration: GitOps (ArgoCD) — all config in Git, no manual config

### 4.3 DR Testing
- Quarterly DR drill: full region failover simulation
- Monthly: database failover test during maintenance window
- Weekly: automated backup restoration verification

## 5. Change Management

### 5.1 Change Windows
- Standard changes: Anytime (auto-approved if CI passes)
- Significant changes: Sunday 02:00-06:00 UTC
- Major releases: Last Sunday of month, 02:00-06:00 UTC

### 5.2 Rollback Criteria
- Error rate exceeds 1% within 15 minutes of deployment
- P95 latency increases > 50% above baseline
- Any P1 incident within 30 minutes of deployment

## 6. Reporting

### 6.1 Monthly SLA Report
- Distributed to: Product Platform Team, Architecture, Customer Ops, Management
- Contents: Availability %, latency percentiles, incident count, error budget consumption
- Generated: 5th of each month (automated from Grafana + PagerDuty data)

### 6.2 Real-time Dashboards
- Grafana → Product Platform → TMF620 SLO Dashboard
- Shows: availability gauge, latency histograms, error budget burn rate, active incidents

## 7. Penalties and Credits
| Availability Breach | Credit |
|---------------------|--------|
| 99.90% - 99.94% (below target) | 5% of monthly service fee |
| 99.50% - 99.89% | 10% of monthly service fee |
| 99.00% - 99.49% | 15% of monthly service fee |
| < 99.00% | 25% of monthly service fee + executive review |

## 8. Review and Amendments
- Quarterly SLA review with all stakeholders
- SLA targets may be tightened (never relaxed) with 30 days notice
- Any amendments require sign-off from Product Platform Lead and Architecture Team
