param(
    [ValidateSet("create", "drop", "dsn")]
    [string]$Action = "dsn",
    [ValidatePattern("_(test|citest)$")]
    [string]$Database = "person_search_citest"
)

# Disposable PostgreSQL database for integration/E2E tests, inside the running storage stack.
# create: drop if present, create, migrate to head, print the DSN to export.
# drop:   remove it. dsn: print the DSN only.
# tests/conftest.py refuses writing test suites unless the database name ends with _test/_citest.

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repositoryRoot "infra\compose.yaml"
$environmentFile = Join-Path $repositoryRoot "infra\.env"
$backendRoot = Join-Path $repositoryRoot "backend"
$backendEnvironmentFile = Join-Path $backendRoot ".env"
$python = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "infra/.env not found. Start the storage stack first (scripts/storage.ps1 up)."
}
if (-not (Test-Path -LiteralPath $backendEnvironmentFile)) {
    throw "backend/.env not found; it provides the demo DSN the test DSN is derived from."
}

$composeArguments = @("compose", "--env-file", $environmentFile, "-f", $composeFile)

function Invoke-Psql {
    param([Parameter(Mandatory)][string]$Sql)

    # SQL goes through stdin: PowerShell 5.1 strips double quotes from native arguments.
    $Sql | & docker @composeArguments exec -T postgres sh -ec `
        'psql -q -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB'
    if ($LASTEXITCODE -ne 0) {
        throw "psql failed with exit code $LASTEXITCODE."
    }
}

function Get-TestDsn {
    $line = Get-Content -LiteralPath $backendEnvironmentFile |
        Where-Object { $_ -match '^\s*PERSON_SEARCH_POSTGRES_DSN\s*=' } |
        Select-Object -First 1
    if (-not $line) {
        throw "PERSON_SEARCH_POSTGRES_DSN is missing from backend/.env."
    }
    $demoDsn = ($line -split "=", 2)[1].Trim().Trim('"', "'")
    return ($demoDsn -replace '/[^/?]+(\?.*)?$', "/$Database`$1")
}

$testDsn = Get-TestDsn

switch ($Action) {
    "create" {
        Invoke-Psql -Sql "DROP DATABASE IF EXISTS $Database WITH (FORCE)"
        Invoke-Psql -Sql "CREATE DATABASE $Database"
        $previousDsn = $env:PERSON_SEARCH_POSTGRES_DSN
        try {
            $env:PERSON_SEARCH_POSTGRES_DSN = $testDsn
            Push-Location $backendRoot
            & $python -m alembic upgrade head
            if ($LASTEXITCODE -ne 0) {
                throw "alembic upgrade head failed with exit code $LASTEXITCODE."
            }
        }
        finally {
            Pop-Location
            $env:PERSON_SEARCH_POSTGRES_DSN = $previousDsn
        }
        Write-Host "Created $Database at migration head."
    }
    "drop" {
        Invoke-Psql -Sql "DROP DATABASE IF EXISTS $Database WITH (FORCE)"
        Write-Host "Dropped $Database."
        return
    }
}

Write-Host ""
Write-Host "Export before running integration/E2E tests:"
Write-Host "`$env:PERSON_SEARCH_POSTGRES_DSN = '$testDsn'"
Write-Host "`$env:PERSON_SEARCH_CAMERA_TEST_DSN = '$testDsn'"
