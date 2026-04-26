# TMF620 Product Catalog Management API — Specification Reference

## Overview
TMF620 defines the Product Catalog Management API for the Open Digital Architecture (ODA). It enables telecom service providers to manage product offerings, product specifications, and product catalogs through a standardized REST interface.

## Key Entities

### Product Offering
A product offering represents a commercial product available for sale to customers. It bundles one or more product specifications with pricing, terms, and conditions.

- **Fields:** name, description, lifecycleStatus, validFor, productSpecification, category, channel, marketSegment, pricing
- **Lifecycle States:** In Study, In Design, In Test, Active, Launched, Retired, Obsolete
- **Endpoints:**
  - `GET /productOffering` — List all offerings
  - `GET /productOffering/{id}` — Get specific offering
  - `POST /productOffering` — Create offering
  - `PATCH /productOffering/{id}` — Update offering
  - `DELETE /productOffering/{id}` — Delete offering

### Product Specification
A product specification defines the technical characteristics and features of a product. Multiple product offerings can reference the same specification with different pricing.

- **Fields:** name, description, brand, lifecycleStatus, productNumber, relatedParty, characteristicSpec, attachment
- **Characteristic Types:** String, Number, Boolean, Date, Range, Object
- **Endpoints:**
  - `GET /productSpecification` — List all specs
  - `POST /productSpecification` — Create spec
  - `PATCH /productSpecification/{id}` — Update spec

### Product Catalog
A product catalog groups product offerings into a structured hierarchy for browsing and discovery.

- **Fields:** name, description, lifecycleStatus, validFor, relatedParty, category
- **Catalog Types:** Sales Catalog, Product Catalog, Partner Catalog
- **Endpoints:**
  - `GET /productCatalog` — List catalogs
  - `POST /productCatalog` — Create catalog
  - `GET /productCatalog/{id}/productOffering` — List offerings in catalog

### Catalog Category
Categories organize product offerings within a catalog into a tree structure.

- **Fields:** name, description, parentId, lifecycleStatus
- **Hierarchy:** Root → Subcategory → Leaf (max 5 levels)
- **Endpoints:**
  - `GET /category` — List categories
  - `POST /category` — Create category

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| ERR-4001 | 400 | Invalid product specification reference |
| ERR-4002 | 400 | Missing required characteristic value |
| ERR-4003 | 400 | Invalid lifecycle state transition |
| ERR-4041 | 404 | Product offering not found |
| ERR-4042 | 404 | Product specification not found |
| ERR-4043 | 404 | Catalog not found |
| ERR-4091 | 409 | Duplicate product offering name |
| ERR-4092 | 409 | Catalog version conflict |
| ERR-4221 | 422 | Cannot delete offering with active subscriptions |
| ERR-5001 | 500 | Catalog search index failure |
| ERR-5002 | 500 | Pricing engine unavailable |

## Authentication
All TMF620 endpoints require OAuth 2.0 Bearer Token. Scopes:
- `product-offering:read` — Read access
- `product-offering:write` — Create/update access
- `product-specification:read` — Read specs
- `product-specification:write` — Create/update specs
- `catalog:admin` — Full catalog management

## Rate Limits
- Standard tier: 100 requests/minute
- Premium tier: 500 requests/minute
- Bulk operations: 20 requests/minute

## Pagination
All list endpoints support:
- `offset` — Starting position (default: 0)
- `limit` — Page size (default: 20, max: 100)
- `fields` — Field filtering (comma-separated)
- Response includes `@totalCount` and `@paginationLinks`
