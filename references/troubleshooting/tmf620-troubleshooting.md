# TMF620 Product Catalog — Troubleshooting Guide

## Issue 1: ERR-4001 Invalid Product Specification Reference
**Symptom:** POST /productOffering returns 400 with error code ERR-4001
**Root Cause:** The productSpecification field references an ID that either doesn't exist or is in a non-active lifecycle state
**Resolution Steps:**
1. Verify the specification ID exists: GET /productSpecification/{id}
2. Check lifecycleStatus is one of: In Test, Active, Launched
3. If spec is in wrong state, update it: PATCH /productSpecification/{id}
4. Retry the product offering creation
**Prevention:** Pre-validation hook in offering creation flow
**Related:** ERR-4042, ERR-4003

## Issue 2: ERR-4091 Duplicate Product Offering Name
**Symptom:** POST /productOffering returns 409 with ERR-4091
**Root Cause:** Product offering names must be unique within a catalog
**Resolution Steps:**
1. Search for existing offering: GET /productOffering?name={name}
2. Check if soft-deleted items occupy the name
3. If obsolete duplicate, hard-delete: DELETE /productOffering/{id}?force=true
4. Retry creation

## Issue 3: ERR-5001 Catalog Search Index Stale
**Symptom:** GET /productCatalog/{id}/productOffering returns outdated results
**Root Cause:** Elasticsearch index out of sync with primary database
**Resolution Steps:**
1. Check index health: GET /admin/index/health
2. Trigger manual reindex: POST /admin/index/rebuild
3. Monitor reindex progress (2-5 min for 100K offerings)
4. Verify counts match DB
**Prevention:** Configure CDC pipeline for auto-sync

## Issue 4: ERR-4221 Cannot Delete Offering With Active Subscriptions
**Symptom:** DELETE /productOffering/{id} returns 422
**Root Cause:** Offering has active subscriptions in TMF622
**Resolution Steps:**
1. Check active subscriptions: GET /productOrder?productOffering={id}&status=active
2. Transition offering to Retired instead
3. Once all subscriptions expire, hard-delete becomes possible

## Issue 5: ERR-4003 Invalid Lifecycle State Transition
**Symptom:** PATCH with new lifecycleStatus returns 400
**Root Cause:** Requested state transition is invalid
**Valid transitions:** In Study→In Design, In Design→In Test, In Test→Active, Active→Launched, Launched→Retired, Retired→Obsolete
**Resolution Steps:**
1. Check current state
2. Verify target state is in valid transition list
3. Apply intermediate steps if needed
