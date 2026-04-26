# TMF620 Product Catalog — Troubleshooting Guide

## Issue 1: Product Offering Creation Returns ERR-4001

**Symptom:** `POST /productOffering` returns 400 with error code ERR-4001 "Invalid product specification reference"

**Root Cause:** The `productSpecification` field references an ID that either doesn't exist or is in a non-active lifecycle state (In Study, Retired, Obsolete).

**Resolution Steps:**
1. Verify the specification ID exists: `GET /productSpecification/{id}`
2. Check `lifecycleStatus` is one of: In Test, Active, Launched
3. If spec is in wrong state, update it: `PATCH /productSpecification/{id}` with `{"lifecycleStatus": "Active"}`
4. Retry the product offering creation
5. If spec truly doesn't exist, create it first via `POST /productSpecification`

**Prevention:** Implement pre-validation hook in the product offering creation flow that checks specification existence and state before submission.

**Related Errors:** ERR-4042, ERR-4003

## Issue 2: Duplicate Product Offering Name (ERR-4091)

**Symptom:** `POST /productOffering` returns 409 with ERR-4091

**Root Cause:** Product offering names must be unique within a catalog. A soft-deleted offering may still occupy the name.

**Resolution Steps:**
1. Search for existing offering: `GET /productOffering?name={name}`
2. Check if result includes soft-deleted items (filter by `lifecycleStatus=Obsolete`)
3. If active duplicate exists, update the name to include version suffix
4. If obsolete duplicate, hard-delete if no subscriptions reference it: `DELETE /productOffering/{id}?force=true`
5. Retry creation

**Prevention:** Add name uniqueness check in the offering creation UI before API submission.

## Issue 3: Catalog Search Returns Stale Results (ERR-5001)

**Symptom:** `GET /productCatalog/{id}/productOffering` returns outdated or missing offerings

**Root Cause:** The Elasticsearch index powering catalog search is out of sync with the primary database. This can happen after:
- Bulk import operations
- Database failover events
- Index writer node crashes

**Resolution Steps:**
1. Check index health: `GET /admin/index/health`
2. If status is "yellow" or "red", trigger manual reindex: `POST /admin/index/rebuild`
3. Monitor reindex progress: `GET /admin/index/status` (typically 2-5 minutes for 100K offerings)
4. Verify results match DB count: compare `@totalCount` with DB query
5. If persistent, check Elasticsearch cluster logs for disk space or memory pressure

**Prevention:** Configure automatic reindex on database write events (CDC pipeline). Monitor index lag metric — alert if > 30 seconds.

**Related:** This is related to [[Elasticsearch]] cluster health and [[Database Failover]] scenarios.

## Issue 4: Cannot Delete Offering with Active Subscriptions (ERR-4221)

**Symptom:** `DELETE /productOffering/{id}` returns 422 with ERR-4221

**Root Cause:** The offering has active subscriptions in TMF622 (Product Ordering). The system prevents deletion to maintain referential integrity.

**Resolution Steps:**
1. Check active subscriptions: `GET /productOrder?productOffering={id}&status=active`
2. If subscriptions exist, transition offering to Retired instead: `PATCH /productOffering/{id}` with `{"lifecycleStatus": "Retired"}`
3. Retired offerings are hidden from catalog search but remain accessible by subscription management
4. Once all subscriptions expire (check `validFor.endDate`), hard-delete becomes possible
5. Document retirement date in change management system

**Prevention:** Implement offering deprecation workflow — announce retirement 90 days before, auto-transition on date.

## Issue 5: Lifecycle State Transition Rejected (ERR-4003)

**Symptom:** `PATCH /productOffering/{id}` with new lifecycleStatus returns 400

**Root Cause:** The requested state transition is invalid. Valid transitions:
- In Study → In Design, Obsolete
- In Design → In Test, In Study, Obsolete
- In Test → Active, In Design, Obsolete
- Active → Launched, Retired
- Launched → Retired, Obsolete
- Retired → Obsolete (only after all subscriptions expire)

**Resolution Steps:**
1. Check current state: `GET /productOffering/{id}?fields=lifecycleStatus`
2. Verify target state is in the valid transition list above
3. If intermediate steps needed (e.g., In Study → Active), apply transitions sequentially
4. Check if retirement requires subscription clearance (see Issue 4)

**Related:** [[Product Offering Lifecycle]], [[State Machine Validation]]

## Issue 6: Pricing Engine Unavailable (ERR-5002)

**Symptom:** Product offering creation succeeds but price calculation returns 500

**Root Cause:** The pricing microservice is down or timing out (>5s threshold).

**Resolution Steps:**
1. Check pricing service health: `GET /health/pricing`
2. If down, check Kubernetes pod status: `kubectl get pods -l app=pricing-engine`
3. Restart if crashed: `kubectl rollout restart deployment/pricing-engine`
4. If timing out, check database connection pool: pricing service connects to PostgreSQL for rate cards
5. Temporary workaround: create offering without pricing, add pricing later via PATCH

**Related:** [[Kubernetes Pod Troubleshooting]], [[PostgreSQL Connection Pool]], [[Microservices Health Checks]]
