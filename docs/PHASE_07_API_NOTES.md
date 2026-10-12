# Phase 07 API configuration notes

`POST /v1/recommendations` accepts `{ "user_id": <non-negative int>, "top_k": <positive int> }` and returns only the uncached Safe Top-K with `graph_version`, `trust_version`, `trust_policy_version`, and `raw_cache_hit` metadata. Raw PYMK candidates are never serialized or stored as a Safe Top-K cache entry.

For local development, `MAX_TOP_K` defaults to `10` and `RAW_TOP_M` defaults to `50`. These are transport safeguards for development, not a finalized production product policy; a production deployment must set and review them explicitly. `RAW_TOP_M` must be at least `MAX_TOP_K`.

The bundled CSV has no Trust artifact manifest or model version. Therefore the default response metadata is `unversioned-csv-no-manifest`; it is intentionally not represented as an authoritative Trust model version. Tier-3 admission remains fail-safe because no authoritative mutual Tier-1 count source exists.

`TRUST_PROVIDER=csv` is the default. `mock` and `allow-all` are explicit test/local-only options and cannot be selected when `API_ENVIRONMENT=production`. CORS defaults to localhost development origins and rejects the unsafe wildcard-origin plus credentials combination.

For a reproducible local load smoke against a separately running API, use `python scripts/load_test_api.py --requests 20 --concurrency 4`. It emits request count, p50/p95/p99, error rate and raw-cache hit/miss mix, and identifies itself as a non-production-capacity test.
