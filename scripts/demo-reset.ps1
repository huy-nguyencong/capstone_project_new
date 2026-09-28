param(
    # Backup folder to return to; defaults to the newest folder under backups/.
    [string]$Backup = ""
)

# Return the demo data to a verified backup after a rehearsal (files/demo-script.md):
# restore PostgreSQL/MinIO/Milvus, then delete frames and vectors created after the backup
# (for example by the RTSP session started during the demo) and check that storage is clean.
# Stop the API and the worker first; the storage stack must be running.

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repositoryRoot "backend"
$python = Join-Path $backendRoot ".venv\Scripts\python.exe"
$storageCli = Join-Path $backendRoot ".venv\Scripts\person-search-storage.exe"

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -ne "bash.exe" -and
    $_.CommandLine -match 'person-search-production-worker|person_search\.workers|-m person_search(\s|$)'
}
if ($running) {
    throw "Stop the API and the worker first (running process ids: $($running.ProcessId -join ', '))."
}

if (-not $Backup) {
    $latest = Get-ChildItem -Directory (Join-Path $repositoryRoot "backups") |
        Sort-Object Name -Descending | Select-Object -First 1
    if (-not $latest) { throw "No backup folder found under backups/." }
    $Backup = $latest.FullName
}
Write-Host "Restoring $Backup"

$adminId = (& docker exec person-search-storage-postgres-1 psql -U person_search -d person_search -tAc "SELECT id FROM users WHERE username = 'admin'").Trim()
if (-not $adminId) { throw "Seed admin account not found." }

Push-Location $backendRoot
# The tools log progress to stderr; judge success by exit codes only (PowerShell 5.1).
$ErrorActionPreference = "Continue"
try {
    & $python tools/storage_backup.py restore $Backup --yes
    if ($LASTEXITCODE -ne 0) { throw "Restore failed with exit code $LASTEXITCODE." }
    & $storageCli reconcile --delete-orphans --actor-user-id $adminId
    if ($LASTEXITCODE -notin 0, 2) { throw "Orphan cleanup failed with exit code $LASTEXITCODE." }
    & $storageCli reconcile
    if ($LASTEXITCODE -ne 0) { throw "Storage is not clean after the reset (exit $LASTEXITCODE)." }
}
finally {
    Pop-Location
}
Write-Host "Demo data reset to $Backup. Start the API and the worker again."
