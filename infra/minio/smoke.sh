#!/usr/bin/env sh
set -eu

mc alias set app http://minio:9000 "$MINIO_APP_ACCESS_KEY" "$MINIO_APP_SECRET_KEY" >/dev/null
mc stat "app/$MINIO_APP_BUCKET" >/dev/null
if mc stat "app/$MINIO_MILVUS_BUCKET" >/dev/null 2>&1; then
    echo "Application user unexpectedly has access to the Milvus bucket." >&2
    exit 1
fi

mc alias set root http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
anonymous_policy=$(mc anonymous get "root/$MINIO_APP_BUCKET")
case "$anonymous_policy" in
    *private*) ;;
    *)
        echo "Expected a private bucket, got: $anonymous_policy" >&2
        exit 1
        ;;
esac

echo "MinIO application bucket is reachable and private."
