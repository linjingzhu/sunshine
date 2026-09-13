param(
  [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
  [string]$Workspace = $env:SUNSHINE_CHROMIUM_WORKSPACE,
  [int]$MinimumFreeSpaceGB = 180,
  # 0 lets autoninja saturate the machine. Set this when the runner is also a
  # workstation: ninja otherwise schedules roughly core count plus two jobs and
  # leaves nothing for interactive use.
  [int]$NinjaJobs = $(if ($env:SUNSHINE_NINJA_JOBS) { [int]$env:SUNSHINE_NINJA_JOBS } else { 0 }),
  # The OAuth client this build is given, or nothing. Read from the environment
  # so the release pipeline can supply it from a secret and it never appears on
  # a command line, where Windows shows it to every process that can enumerate
  # them. Empty is the normal case: a build without it simply has no account
  # link, which is the state docs/ACCOUNT_LINK_PLAN.md section 5 describes as
  # absent rather than broken.
  [string]$AccountClientId = $env:SUNSHINE_ACCOUNT_CLIENT_ID
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
  # H.264/AAC. Not Chromium's default: `proprietary_codecs` derives from
  # `is_chrome_branded`, which is false here, so an unmodified build cannot play
  # most web video. Enabled deliberately under the personal-use premise recorded
  # in docs/decisions/0004-media-codecs.md -- that premise, not convenience, is
  # what makes it permissible, and it must be revisited before any distribution.
  "proprietary_codecs=true",
  'ffmpeg_branding="Chrome"',
  # Widevine, and therefore Netflix and every other DRM site. Also not
  # Chromium's default and also not switched off by anyone: `enable_widevine`
  # derives from `is_chrome_branded`, so this build had no key system at all
  # and said so as Netflix error M7701-1003.
  #
  # This adds no binary to the tree. `bundle_widevine_cdm` stays false because
  # its default wants a branded build, so `widevinecdm.dll` is never looked for
  # here; `enable_widevine_cdm_component` derives true on Windows and the CDM is
  # fetched at run time by Chromium's own component updater.
  #
  # Host verification stays off for the same branding reason, which matters more
  # than it reads: `ignore_missing_widevine_signing_cert` defaults to
  # `!is_official_build` and this build is official, so a signing step would
  # have failed the build outright for want of a certificate. No signing step is
  # generated.
  #
  # The premise is in docs/decisions/0024-drm-widevine.md and it is narrower
  # than ADR 0004's: Widevine's licence names *use*, not only distribution.
  # Revisit it before this build reaches anyone else.
  "enable_widevine=true"
)

# Appended only when a client was supplied, so args.gn in a build without one
# is byte-identical to what it was before this feature existed. That matters
# more than it looks: args.gn stays in the output directory and is the first
# thing anyone reads to find out what a build actually is, so an argument that
# is present but empty would invite the reader to wonder which builds have a
# credential and which do not.
#
# The id is a public identifier -- Google's own installed-app documentation
# says so -- but it is still not echoed. `gn gen` prints args.gn back on
# failure, and a build log is a more durable place than anyone intends.
if (-not [string]::IsNullOrWhiteSpace($AccountClientId)) {
  $gnArgs += ("sunshine_account_client_id=" + [char]34 + $AccountClientId + [char]34)
  Write-Host "Account link: a client id was supplied."
} else {
  Write-Host "Account link: no client id supplied; this build will not offer one."
}

# Written to args.gn rather than passed through --args. PowerShell strips the
# embedded quotes when it hands an argument to a native command, so GN received
# ffmpeg_branding=Chromium and rejected Chromium as an undefined identifier.
# A file removes shell quoting from the path entirely, and leaves the exact
# build configuration readable in the output directory afterwards.
New-Item -ItemType Directory -Force -Path $out | Out-Null
Set-Content -Path (Join-Path $out "args.gn") -Value $gnArgs -Encoding utf8

# A process still running from a previous build holds its own binaries open,
# and Windows refuses to overwrite an open file. Build #21 died on
# `lld-link: failed to write output './chrome_elf.dll': permission denied`
# because a `chrome.exe` started by the previous run's verification step was
# still alive. The verification step no longer launches anything, but a build
# that cannot recover from a stale process is one crashed browser away from
# needing manual cleanup on a machine nobody is sitting at.
#
# Scoped to this output directory on purpose. It matches by executable path, so
# a Chrome, an Edge, or a Sunshine build the owner is using from anywhere else
# on the machine is not touched -- only processes running the artifacts this
# script is about to overwrite.
$stale = Get-Process -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Path -and $_.Path.StartsWith($out, [StringComparison]::OrdinalIgnoreCase)
  }
if ($stale) {
  Write-Host "Stopping $($stale.Count) stale process(es) holding files in $out."
  $stale | ForEach-Object {
    Write-Host "  $($_.ProcessName) (pid $($_.Id)) -- $($_.Path)"
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
  }
  # Windows releases the file handles asynchronously; linking immediately after
  # the kill can still hit the lock.
  Start-Sleep -Seconds 3
}

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
