$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repositoryRoot "backend"
$virtualEnvironmentPython = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $virtualEnvironmentPython) {
    $pythonCommand = $virtualEnvironmentPython
} else {
    $pythonCommand = "python"
}

Push-Location $backendRoot
try {
    & $pythonCommand -m pytest -m unit
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $pythonCommand -m ruff check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $pythonCommand -m compileall src
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
