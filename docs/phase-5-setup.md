# Phase 5 search setup

Phase 5 uses the active row in `ai_config_versions` to select the vector space. The demo worker config `fake_demo_v1` automatically uses the in-process deterministic encoder and the demo Milvus collection. This keeps local development self-contained.

For any other active encoder, set `PERSON_SEARCH_ENCODER_URL` to an internal HTTP service. The backend calls:

- `POST /encode/image` with `{ "image_base64", "encoder_version" }`
- `POST /encode/text` with `{ "text", "encoder_version" }`

Both operations must return `{ "encoder_version", "embedding" }`. The embedding length must match `ai_config_versions.encoder_dimension`; it must be finite and L2-normalized. Encoder failures return `503 encoder_unavailable` without exposing upstream details.

Search requests require an Operator session and CSRF token. The browser obtains the selectable camera set from `GET /api/v1/me/cameras`. `top_k` accepts only `4`, `8`, `12`, or `16`.

Track media is rendered on demand from the stored representative frame. Responses are JPEG with `Cache-Control: private, no-store`; no derived crop is persisted.
