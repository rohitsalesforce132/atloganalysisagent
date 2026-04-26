# TMF620 Product Catalog API — Service Level Agreement

## Latency Targets
| Endpoint | P50 | P95 | P99 |
|----------|-----|-----|-----|
| GET /productOffering/{id} | 50ms | 500ms | 1000ms |
| GET /productOffering (list) | 100ms | 500ms | 1000ms |
| POST /productOffering | 200ms | 800ms | 1500ms |
| GET /productCatalog/{id}/productOffering | 150ms | 500ms | 1000ms |

## Availability: 99.95%
## Error Budget: 0.05% monthly
## P1 Response: 15 minutes
