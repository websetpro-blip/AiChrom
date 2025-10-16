param(
  [ValidateSet("start","stop","status","logs")] [string]$action = "start",
  [int]$timeoutSec = 60
)

$ErrorActionPreference = "SilentlyContinue"
$root = "C:\AI\браузер"
$exe  = Join-Path $root "node_modules\electron\dist\electron.exe"
$logs = Join-Path $root "logs"
$healthUrl = "http://127.0.0.1:3070/api/health"
New-Item -ItemType Directory -Path $logs -Force | Out-Null

function Kill-Own {
  Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -in @('node.exe','electron.exe')) -and ($_.CommandLine -match [regex]::Escape($root))
  } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }
}

function Wait-Health([int]$sec) {
  $deadline = (Get-Date).AddSeconds($sec)
  do {
    try {
      $r = Invoke-WebRequest $healthUrl -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -eq 200) { return $true }
    } catch {}
    Start-Sleep -Milliseconds 300
  } while ((Get-Date) -lt $deadline)
  return $false
}

switch ($action) {
  "start" {
    Kill-Own
    $env:ELECTRON_ENABLE_LOGGING = "1"
    $out = Join-Path $logs "electron.out.log"
    $err = Join-Path $logs "electron.err.log"

    # Запускаем Electron, сервер поднимется внутри electron-main.cjs
    Start-Process -WorkingDirectory $root -FilePath $exe -ArgumentList "`"$root`"" `
      -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err

    if (Wait-Health -sec $timeoutSec) {
      Write-Host "OK: UI/Server is up => $healthUrl"
      exit 0
    } else {
      Write-Host "FAIL: health not ready in $timeoutSec sec"
      Write-Host "---- last 60 lines of logs ----"
      if (Test-Path $err) { Get-Content $err -Tail 60 }
      if (Test-Path $out) { Get-Content $out -Tail 60 }
      exit 1
    }
  }

  "stop"   { Kill-Own; Write-Host "Stopped." }
  "status" {
    try {
      $r = Invoke-WebRequest $healthUrl -UseBasicParsing -TimeoutSec 3
      Write-Host $r.Content
    } catch {
      Write-Host "DOWN"
    }
  }
  "logs"   {
    $out = Join-Path $logs "electron.out.log"
    $err = Join-Path $logs "electron.err.log"
    if (Test-Path $err) { Write-Host "=== electron.err ==="; Get-Content $err -Tail 80 }
    if (Test-Path $out) { Write-Host "=== electron.out ==="; Get-Content $out -Tail 80 }
  }
}