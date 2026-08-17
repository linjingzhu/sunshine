param(
  [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
  [string]$Workspace = $env:SUNSHINE_CHROMIUM_WORKSPACE,
  [int]$MinimumFreeSpaceGB = 180,
  # 0 lets autoninja saturate the machine. Set this when the runner is also a
  # workstation: ninja otherwise schedules roughly core count plus two jobs and
  # leaves nothing for interactive use.
  [int]$NinjaJobs = $(if ($env:SUNSHINE_NINJA_JOBS) { [int]$env:SUNSHINE_NINJA_JOBS } else { 0 })
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Checked before anything else: $IsWindows does not exist in Windows PowerShell
# 5.1, so under StrictMode the next check would fail with an unrelated error
# instead of naming the real requirement.
if ($PSVersionTable.PSVersion.Major -lt 7) {
  throw ("PowerShell 7 or newer is required; this is Windows PowerShell " +
    "$($PSVersionTable.PSVersion). Install it with: winget install Microsoft.PowerShell")
}
if (-not $IsWindows) {
  throw "Sunshine native Chromium builds require Windows."
}
if ([string]::IsNullOrWhiteSpace($Workspace)) {
  throw "SUNSHINE_CHROMIUM_WORKSPACE must point to a persistent NTFS workspace."
}

$workspacePath = [IO.Path]::GetFullPath($Workspace)
$drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($workspacePath).Substring(0, 1))
$freeSpaceGB = [math]::Floor($drive.Free / 1GB)
if ($freeSpaceGB -lt $MinimumFreeSpaceGB) {
  throw "At least $MinimumFreeSpaceGB GB free is required; $freeSpaceGB GB is available."
}

foreach ($command in @("git", "python", "fetch", "gclient", "gn", "autoninja")) {
  if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
    throw "Required command is not on PATH: $command"
  }
}

$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
  throw "Visual Studio 2022 with Desktop development with C++ is required."
}
$installationPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ([string]::IsNullOrWhiteSpace($installationPath)) {
  throw "Visual Studio C++ x64 tools were not found."
}

python (Join-Path $RepositoryRoot "scripts\bootstrap_chromium.py") --workspace $workspacePath --reset
if ($LASTEXITCODE -ne 0) { throw "Chromium bootstrap failed." }

$src = Join-Path $workspacePath "src"
$out = Join-Path $src "out\Sunshine"
$gnArgs = @(
  "is_debug=false",
  "is_official_build=true",
  "is_component_build=false",
  "symbol_level=0",
  "blink_symbol_level=0",
  "v8_symbol_level=0",
  "use_remoteexec=false",
  "proprietary_codecs=false",
  'ffmpeg_branding="Chromium"'
)

# Written to args.gn rather than passed through --args. PowerShell strips the
# embedded quotes when it hands an argument to a native command, so GN received
# ffmpeg_branding=Chromium and rejected Chromium as an undefined identifier.
# A file removes shell quoting from the path entirely, and leaves the exact
# build configuration readable in the output directory afterwards.
New-Item -ItemType Directory -Force -Path $out | Out-Null
Set-Content -Path (Join-Path $out "args.gn") -Value $gnArgs -Encoding utf8

Push-Location $src
try {
  gn gen "out/Sunshine"
  if ($LASTEXITCODE -ne 0) { throw "GN generation failed." }

  $ninjaArguments = @("-C", "out/Sunshine")
  if ($NinjaJobs -gt 0) {
    Write-Host "Limiting compilation to $NinjaJobs parallel jobs."
    $ninjaArguments += @("-j", $NinjaJobs)
  }
  $ninjaArguments += @("chrome", "mini_installer")

  autoninja @ninjaArguments
  if ($LASTEXITCODE -ne 0) {
    # siso reports a compile failure as one summary line -- "1 steps failed:
    # exit=1" -- and writes the failing command and its compiler output to
    # out/Sunshine/siso_output instead of stdout. That file stays on the runner,
    # so without this block the CI log names no target, no file, and no
    # diagnostic, and the failure cannot be acted on from the log alone.
    foreach ($diagnostic in @("siso_output", "siso_failed_commands.bat")) {
      $diagnosticPath = Join-Path $out $diagnostic
      if (Test-Path $diagnosticPath) {
        Write-Host "===== $diagnostic (last 400 lines) ====="
        Get-Content $diagnosticPath -Tail 400 | ForEach-Object { Write-Host $_ }
      } else {
        Write-Host "===== $diagnostic was not written ====="
      }
    }
    throw "Chromium compilation failed."
  }
}
finally {
  Pop-Location
}

$chrome = Join-Path $out "chrome.exe"
$installer = Join-Path $out "mini_installer.exe"
foreach ($artifact in @($chrome, $installer)) {
  if (-not (Test-Path $artifact)) { throw "Expected build artifact missing: $artifact" }
}

$artifactDirectory = Join-Path $RepositoryRoot "artifacts\windows-x64"
New-Item -ItemType Directory -Force -Path $artifactDirectory | Out-Null
Copy-Item $installer (Join-Path $artifactDirectory "sunshine-installer-windows-x64.exe") -Force

$sizeReport = [ordered]@{
  revision = (Get-Content (Join-Path $RepositoryRoot "config\chromium.version") | Where-Object { $_ -like "CHROMIUM_REVISION=*" }) -replace "CHROMIUM_REVISION=", ""
  builtAtUtc = [DateTime]::UtcNow.ToString("o")
  chromeBytes = (Get-Item $chrome).Length
  installerBytes = (Get-Item $installer).Length
  freeSpaceBeforeBuildGB = $freeSpaceGB
}
$sizeReport | ConvertTo-Json | Set-Content (Join-Path $artifactDirectory "size-report.json") -Encoding utf8

Write-Host "Sunshine Chromium Windows build completed."
Write-Host "Installer: $installer"
