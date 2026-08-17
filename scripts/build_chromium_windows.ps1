param(
  [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
  [string]$Workspace = $env:SUNSHINE_CHROMIUM_WORKSPACE,
  [int]$MinimumFreeSpaceGB = 180
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

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
) -join " "

Push-Location $src
try {
  gn gen "out/Sunshine" "--args=$gnArgs"
  if ($LASTEXITCODE -ne 0) { throw "GN generation failed." }

  autoninja -C "out/Sunshine" chrome mini_installer
  if ($LASTEXITCODE -ne 0) { throw "Chromium compilation failed." }
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
