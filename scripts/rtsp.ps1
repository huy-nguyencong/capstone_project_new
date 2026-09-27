param(
    [ValidateSet("up", "down", "status")]
    [string]$Action = "status",
    # Host IPv4 that MediaMTX binds to and cameras point at. Loopback is rejected by the backend,
    # so the default is the address of the interface that owns the default route.
    [string]$BindAddress = "",
    [int[]]$Cameras = @(1, 2, 3, 4, 5, 6, 7),
    [string]$Dataset = ""
)

# Simulated camera system (architect.md 3/6.1): FFmpeg publishes each WILDTRACK video in a loop
# to MediaMTX, one RTSP path per logical camera: rtsp://<BindAddress>:8554/cam<n>.

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repositoryRoot "infra\compose.yaml"
$environmentFile = Join-Path $repositoryRoot "infra\.env"
if (-not (Test-Path -LiteralPath $environmentFile)) {
    $environmentFile = Join-Path $repositoryRoot "infra\.env.example"
}
if (-not $Dataset) { $Dataset = Join-Path $repositoryRoot "wildtrack-dataset" }
$stateFile = Join-Path $env:TEMP "person-search-rtsp-publishers.json"
$port = 8554

function Get-DefaultAddress {
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric | Select-Object -First 1
    if (-not $route) { throw "No default route found; pass -BindAddress explicitly." }
    $address = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $route.InterfaceIndex |
        Select-Object -First 1
    if (-not $address) { throw "Default interface has no IPv4 address; pass -BindAddress." }
    return $address.IPAddress
}

function Stop-Publishers {
    if (-not (Test-Path -LiteralPath $stateFile)) { return }
    $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    foreach ($publisher in $state.publishers) {
        $process = Get-Process -Id $publisher.pid -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -eq "ffmpeg") {
            Stop-Process -Id $publisher.pid -Force -Confirm:$false
        }
    }
    Remove-Item -LiteralPath $stateFile -Force -Confirm:$false
}

function Invoke-Compose {
    param([string[]]$Arguments)
    # docker writes progress to stderr; judge success by the exit code only (PowerShell 5.1).
    $ErrorActionPreference = "Continue"
    & docker compose --env-file $environmentFile -f $composeFile --profile rtsp @Arguments 2>&1 |
        ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed with exit code $LASTEXITCODE." }
}

switch ($Action) {
    "up" {
        if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            throw "ffmpeg was not found in PATH."
        }
        if (-not $BindAddress) { $BindAddress = Get-DefaultAddress }
        Stop-Publishers
        # Shell variables override values from --env-file.
        $env:MEDIAMTX_BIND_ADDRESS = $BindAddress
        $env:MEDIAMTX_RTSP_PORT = "$port"
        Invoke-Compose @("up", "-d", "--force-recreate", "mediamtx")
        Start-Sleep -Seconds 2

        $publishers = @()
        foreach ($camera in $Cameras) {
            $video = Join-Path $Dataset "cam$camera.mp4"
            if (-not (Test-Path -LiteralPath $video)) { throw "Missing video: $video" }
            $url = "rtsp://${BindAddress}:$port/cam$camera"
            $process = Start-Process ffmpeg -WindowStyle Hidden -PassThru -ArgumentList @(
                "-hide_banner", "-loglevel", "error", "-re", "-stream_loop", "-1",
                "-i", "`"$video`"", "-c", "copy", "-f", "rtsp", "-rtsp_transport", "tcp", $url
            )
            $publishers += [pscustomobject]@{ camera = $camera; pid = $process.Id; url = $url }
        }
        [pscustomobject]@{ bind = $BindAddress; publishers = $publishers } |
            ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $stateFile -Encoding utf8

        Write-Host "MediaMTX is publishing $($publishers.Count) simulated camera(s):"
        $publishers | ForEach-Object { Write-Host "  cam$($_.camera): $($_.url)" }
        Write-Host ""
        Write-Host "Backend must allow this network, e.g. in backend/.env:"
        Write-Host "  PERSON_SEARCH_RTSP_NETWORKS=$BindAddress/32"
        Write-Host "Restart API and worker after changing backend/.env."
    }
    "down" {
        Stop-Publishers
        Invoke-Compose @("stop", "mediamtx")
        Write-Host "RTSP simulation stopped."
    }
    "status" {
        Invoke-Compose @("ps", "mediamtx")
        if (Test-Path -LiteralPath $stateFile) {
            $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
            foreach ($publisher in $state.publishers) {
                $alive = [bool](Get-Process -Id $publisher.pid -ErrorAction SilentlyContinue)
                Write-Host ("  cam{0}: {1} ({2})" -f $publisher.camera, $publisher.url,
                    $(if ($alive) { "publishing" } else { "stopped" }))
            }
        }
        else {
            Write-Host "No FFmpeg publishers recorded."
        }
    }
}
