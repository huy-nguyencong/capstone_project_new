param(
    [ValidateSet("validate", "up", "down", "status", "logs", "smoke")]
    [string]$Action = "status",
    [string]$Service = ""
)

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repositoryRoot "infra\compose.yaml"
$environmentFile = Join-Path $repositoryRoot "infra\.env"
$exampleEnvironmentFile = Join-Path $repositoryRoot "infra\.env.example"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install and start Docker Desktop first."
}

if (-not (Test-Path -LiteralPath $environmentFile)) {
    if ($Action -in @("validate", "down", "status", "logs")) {
        $environmentFile = $exampleEnvironmentFile
        Write-Host "infra/.env not found; using infra/.env.example for this read-only/stop operation."
    }
    else {
        throw "infra/.env not found. Copy infra/.env.example to infra/.env and change the development passwords."
    }
}

$composeArguments = @(
    "compose",
    "--env-file", $environmentFile,
    "-f", $composeFile
)

function Invoke-Compose {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & docker @composeArguments @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE."
    }
}

switch ($Action) {
    "validate" {
        Invoke-Compose -Arguments @("config", "--quiet")
        Write-Host "Compose configuration is valid."
    }
    "up" {
        Invoke-Compose -Arguments @("config", "--quiet")
        Invoke-Compose -Arguments @("up", "-d", "--wait", "--wait-timeout", "240")
        Invoke-Compose -Arguments @("ps", "--all")
        & $PSCommandPath -Action smoke
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    "down" {
        Invoke-Compose -Arguments @("down", "--remove-orphans")
        Write-Host "Services stopped. Named volumes were preserved."
    }
    "status" {
        Invoke-Compose -Arguments @("ps", "--all")
    }
    "logs" {
        $arguments = @("logs", "--tail", "200", "--follow")
        if ($Service) { $arguments += $Service }
        Invoke-Compose -Arguments $arguments
    }
    "smoke" {
        Invoke-Compose -Arguments @(
            "exec", "-T", "postgres", "sh", "-ec",
            'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
        )
        Invoke-Compose -Arguments @(
            "exec", "-T", "milvus", "curl", "--fail", "--silent", "--show-error",
            "http://localhost:9091/healthz"
        )
        Invoke-Compose -Arguments @(
            "run", "--rm", "--no-deps", "--entrypoint", "/bin/sh", "minio-init",
            "/bootstrap/smoke.sh"
        )
        Write-Host "PostgreSQL, Milvus and MinIO smoke checks passed."
    }
}
