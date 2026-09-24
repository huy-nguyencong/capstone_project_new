#!/usr/bin/env sh
set -eu

: "${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required}"
: "${MINIO_APP_ACCESS_KEY:?MINIO_APP_ACCESS_KEY is required}"
: "${MINIO_APP_SECRET_KEY:?MINIO_APP_SECRET_KEY is required}"
: "${MINIO_APP_BUCKET:?MINIO_APP_BUCKET is required}"
: "${MINIO_APP_POLICY:?MINIO_APP_POLICY is required}"

mc alias set storage http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing "storage/$MINIO_APP_BUCKET"
mc anonymous set none "storage/$MINIO_APP_BUCKET"

if ! mc admin user info storage "$MINIO_APP_ACCESS_KEY" >/dev/null 2>&1; then
    mc admin user add storage "$MINIO_APP_ACCESS_KEY" "$MINIO_APP_SECRET_KEY"
fi

mc admin policy create storage "$MINIO_APP_POLICY" /bootstrap/app-policy.json
mc admin policy attach storage "$MINIO_APP_POLICY" --user "$MINIO_APP_ACCESS_KEY"

mc stat "storage/$MINIO_APP_BUCKET" >/dev/null
anonymous_policy=$(mc anonymous get "storage/$MINIO_APP_BUCKET")
case "$anonymous_policy" in
    *private*) ;;
    *)
        echo "Expected a private bucket, got: $anonymous_policy" >&2
        exit 1
        ;;
esac
echo "MinIO bucket, application user and private policy are ready."
