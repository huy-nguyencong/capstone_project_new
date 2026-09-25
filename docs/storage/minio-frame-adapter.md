# Private MinIO frame adapter (STO-09)

Objects use the deterministic key
`tracks/v1/{camera_id}/{yyyy}/{mm}/{dd}/{track_id}/representative.{jpg|png}`. The adapter validates the
declared MIME type against decoded image bytes, exact dimensions and a 20 MiB default size limit.

Each object stores only track ID and SHA-256 metadata. Repeating a put with the same key and checksum
is idempotent; a different checksum raises a conflict. Every get recomputes SHA-256 before returning
bytes. The API provides put/head/get/delete and never returns a public or presigned URL.

The integration test verifies round-trip integrity and confirms anonymous HTTP access is denied.
