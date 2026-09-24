#!/usr/bin/env sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infra/compose.yaml"
environment_file="$repository_root/infra/.env"
example_environment_file="$repository_root/infra/.env.example"
action=${1:-status}
service=${2:-}

case "$action" in
    validate|up|down|status|logs|smoke) ;;
    *)
        echo "Usage: $0 {validate|up|down|status|logs|smoke} [service]" >&2
        exit 2
        ;;
esac

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker CLI was not found. Install and start Docker first." >&2
    exit 1
fi

if [ ! -f "$environment_file" ]; then
    case "$action" in
        validate|down|status|logs)
            environment_file=$example_environment_file
            echo "infra/.env not found; using infra/.env.example for this read-only/stop operation."
            ;;
        *)
            echo "infra/.env not found. Copy infra/.env.example to infra/.env and change the development passwords." >&2
            exit 1
            ;;
    esac
fi

compose() {
    docker compose --env-file "$environment_file" -f "$compose_file" "$@"
}

smoke() {
    compose exec -T postgres sh -ec 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
    compose exec -T milvus curl --fail --silent --show-error http://localhost:9091/healthz
    compose run --rm --no-deps --entrypoint /bin/sh minio-init /bootstrap/smoke.sh
    echo "PostgreSQL, Milvus and MinIO smoke checks passed."
}

case "$action" in
    validate)
        compose config --quiet
        echo "Compose configuration is valid."
        ;;
    up)
        compose config --quiet
        compose up -d --wait --wait-timeout 240
        compose ps --all
        smoke
        ;;
    down)
        compose down --remove-orphans
        echo "Services stopped. Named volumes were preserved."
        ;;
    status)
        compose ps --all
        ;;
    logs)
        if [ -n "$service" ]; then
            compose logs --tail 200 --follow "$service"
        else
            compose logs --tail 200 --follow
        fi
        ;;
    smoke)
        smoke
        ;;
esac
