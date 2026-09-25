# Milvus person-track vector adapter (STO-10)

Each encoder version receives a separate collection named by the storage contract. The adapter
creates and validates the collection idempotently, builds an HNSW/IP index and maintains an alias.
The schema contains track ID, embedding, area ID, camera ID, appearance epoch, encoder version and
index status. Matching Score exists only in `VectorSearchHit` and is never persisted.

Vectors must have the configured dimension, contain finite values and be L2-normalized. Search
filters are constructed only from UUID and timezone-aware datetime values. Area, optional camera,
time range and `READY` status are sent to Milvus in the filter expression before top-k search.

The adapter exposes ensure-collection, upsert, get, delete and search operations. Index/search
parameters are isolated in injectable `VectorIndexConfig`, with demo-safe defaults.
