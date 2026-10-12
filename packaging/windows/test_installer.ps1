# Doremi Windows installer test (F0B-2B).
# Runs on windows-latest CI. Isolated: installs into RUNNER_TEMP, never
# touches Program Files, never elevates. User-data sentinels live in the
# ephemeral runner HOME (no real user data exists there).
#
# Usage:
#   pwsh -File packaging/windows/test_installer.ps1 `
#     -SetupExe dist/installer/Doremi-v2.1.4-Setup.exe `
#     -InstallDir "$env:RUNNER_TEMP\Doremi-Test\Doremi" `
#     -Version "2.1.4"
#
# Exit code 0 = all scenarios passed (A install, B reinstall, C simulated
# upgrade, D uninstall) with sentinel checksums preserved. Writes a JSON
# summary to -ResultJson (default RUNNER_TEMP/doremi-installer-results.json).
# NEVER run this against a machine with real Doremi user data.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SetupExe,
    [string]$InstallDir = (Join-Path $env:RUNNER_TEMP "Doremi-Test\Doremi"),
    [string]$Version = "2.1.4",
    [string]$ResultJson = (Join-Path $env:RUNNER_TEMP "doremi-installer-results.json")
)

$ErrorActionPreference = "Stop"
$summary = [ordered]@{
    version = $Version
    setup = $SetupExe
    install_dir = $InstallDir
    scenarios = [ordered]@{}
    sentinels = @()
    ok = $false
}

function Fail([string]$msg) { throw $msg }

function Sentinel-Roots {
    # Effective AppDirs on Windows (see src/doremi/config/paths.py):
    #   config = $XDG_CONFIG_HOME or $HOME/.config  + /doremi
    #   data   = $XDG_DATA_HOME   or $HOME/.local/share + /doremi
    #   cache  = $XDG_CACHE_HOME  or $HOME/.cache + /doremi
    # XDG overrides are NOT set for the installed-app runs below, so the
    # defaults apply. Plus the legacy %LOCALAPPDATA%\Doremi path that the
    # old [UninstallDelete] rule would have wiped.
    $homeDir = $env:USERPROFILE
    if (-not $homeDir) { $homeDir = [Environment]::GetFolderPath("UserProfile") }
    return @(
        (Join-Path $homeDir ".config\doremi\settings.toml"),
        (Join-Path $homeDir ".local\share\doremi\doremi.db"),
        (Join-Path $homeDir ".local\share\doremi\library.json"),
        (Join-Path $homeDir ".local\share\doremi\downloads\sentinel.txt"),
        (Join-Path $homeDir ".cache\doremi\artwork\sentinel.bin"),
        (Join-Path $env:LOCALAPPDATA "Doremi\sentinel-legacy.txt")
    )
}

function New-Sentinels {
    $files = Sentinel-Roots
    $records = @()
    $i = 0
    foreach ($f in $files) {
        $i++
        $dir = Split-Path $f -Parent
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $content = "doremi-f0b2b-sentinel-$i v=$Version content=DO-NOT-DELETE"
        # binary-ish sentinel for artwork to prove byte preservation
        if ($f -like "*sentinel.bin") {
            $bytes = [Text.Encoding]::UTF8.GetBytes($content + "`n\x00\x01\x02bin")
            [IO.File]::WriteAllBytes($f, $bytes)
        } else {
            Set-Content -Path $f -Value $content -Encoding UTF8 -NoNewline
        }
        $h = (Get-FileHash $f -Algorithm SHA256).Hash
        $records += [ordered]@{ path = $f; sha256 = $h }
        Write-Host "sentinel: $f $h"
    }
    return $records
}

function Assert-Sentinels($records, [string]$stage) {
    foreach ($r in $records) {
        if (-not (Test-Path $r.path)) { Fail "[$stage] sentinel MISSING: $($r.path)" }
        $h = (Get-FileHash $r.path -Algorithm SHA256).Hash
        if ($h -ne $r.sha256) { Fail "[$stage] sentinel MODIFIED: $($r.path) ($h != $($r.sha256))" }
    }
    Write-Host "[$stage] sentinels preserved ($($records.Count) files)"
}

function Install-Doremi([string]$stage) {
    Write-Host "=== $stage : installing to $InstallDir ==="
    $log = Join-Path $env:RUNNER_TEMP ("doremi-install-{0}.log" -f $stage)
    $proc = Start-Process -FilePath $SetupExe -ArgumentList @(
        "/SP-", "/SILENT", "/NORESTART", "/SUPPRESSMSGBOXES",
        ("/DIR=" + $InstallDir), ("/LOG=" + $log)
    ) -Wait -PassThru -NoNewWindow
    Write-Host "installer exit code: $($proc.ExitCode) (log: $log)"
    if ($proc.ExitCode -ne 0) {
        if (Test-Path $log) { Get-Content $log -Tail 40 }
        Fail "[$stage] installer exit code $($proc.ExitCode)"
    }
    $exe = Join-Path $InstallDir "Doremi.exe"
    if (-not (Test-Path $exe)) { Fail "[$stage] missing $exe" }
    Write-Host "[$stage] Doremi.exe present ($([math]::Round((Get-Item $exe).Length / 1MB, 1)) MB)"
}

function Find-UninstallKeys {
    # Inno Setup is a 32-bit process by default, so on 64-bit Windows its
    # uninstall registration may land in the native Uninstall view or the
    # WOW6432Node view. Search every plausible per-user/machine view for
    # our stable AppId GUID instead of assuming one path.
    $guid = "b2285fdf-22de-411a-93b2-4ce4d8a5fa8a"
    $roots = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKCU:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    )
    $found = @()
    foreach ($r in $roots) {
        if (-not (Test-Path $r)) { continue }
        foreach ($k in (Get-ChildItem $r -ErrorAction SilentlyContinue)) {
            if ($k.PSChildName -like "*$guid*") { $found += $k.PSPath }
        }
    }
    return $found
}

function Check-AppId([string]$stage) {
    $keys = @(Find-UninstallKeys)
    if ($keys.Count -eq 0) {
        Write-Host "[$stage] DIAGNOSTICS: listing Doremi-ish uninstall entries (all views):"
        foreach ($r in @("HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
                         "HKCU:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")) {
            if (Test-Path $r) {
                Get-ChildItem $r -ErrorAction SilentlyContinue |
                    Where-Object { $_.PSChildName -like "*oremi*" -or $_.PSChildName -like "*{*}" } |
                    Select-Object -First 5 PSPath | ForEach-Object { Write-Host "  $($_.PSPath)" }
            } else { Write-Host "  (missing view: $r)" }
        }
        $log = Join-Path $env:RUNNER_TEMP ("doremi-install-{0}.log" -f $stage)
        if ($stage -eq "A" -and (Test-Path $log)) {
            Write-Host "[$stage] install log tail:"; Get-Content $log -Tail 25
        }
        Fail "[$stage] uninstall registry key for AppId GUID missing in HKCU/HKLM x64+WOW6432Node views"
    }
    if ($keys.Count -gt 1) { Fail "[$stage] multiple uninstall keys for AppId: $($keys -join ', ')" }
    $keyPath = $keys[0]
    if ($keyPath -notlike "*HKEY_CURRENT_USER*") {
        Fail "[$stage] per-user install registered outside HKCU (elevation leak?): $keyPath"
    }
    $props = Get-ItemProperty $keyPath
    Write-Host "[$stage] AppId key: $keyPath DisplayName='$($props.DisplayName)' DisplayVersion='$($props.DisplayVersion)' InstallLocation='$($props.InstallLocation)'"
    if ($props.DisplayVersion -ne $Version) {
        Write-Host "WARNING [$stage] DisplayVersion '$($props.DisplayVersion)' != $Version (check stamping)"
    }
    return $keyPath
}

function Check-Shortcuts([string]$stage) {
    $group = Join-Path ([Environment]::GetFolderPath("ApplicationData")) "Microsoft\Windows\Start Menu\Programs\Doremi"
    $lnk = Join-Path $group "Doremi.lnk"
    if (-not (Test-Path $lnk)) { Fail "[$stage] missing Start Menu shortcut: $lnk" }
    Write-Host "[$stage] Start Menu shortcut OK: $lnk"
    # The old script created a duplicate top-level {userstartmenu}\Doremi.lnk;
    # it must NOT exist anymore.
    $dup = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Doremi.lnk"
    if (Test-Path $dup) { Fail "[$stage] duplicate top-level shortcut still present: $dup" }
    Write-Host "[$stage] no duplicate top-level shortcut (good)"
}

function Invoke-InstalledSmoke([string]$stage) {
    $exe = Join-Path $InstallDir "Doremi.exe"
    $smokeRoot = Join-Path $env:RUNNER_TEMP ("doremi-inst-smoke-{0}" -f $stage)
    New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null
    # Isolate the SMOKE run itself (installed exe honors the same XDG
    # overrides as the portable; sentinels under HOME are untouched because
    # run_smoke_test mkdtemps its own XDG already, but belt and suspenders).
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:DOREMI_SMOKE_OUT = Join-Path $smokeRoot "smoke-result.json"
    Write-Host "=== $stage : smoke from installed exe ==="
    $proc = Start-Process -FilePath $exe -ArgumentList "--smoke-test" -Wait -PassThru -NoNewWindow
    $code = $proc.ExitCode
    if (Test-Path $env:DOREMI_SMOKE_OUT) { Get-Content $env:DOREMI_SMOKE_OUT }
    else { Fail "[$stage] smoke-result.json not written" }
    if ($code -ne 0) { Fail "[$stage] installed smoke exit code: $code" }
    $r = Get-Content $env:DOREMI_SMOKE_OUT -Raw | ConvertFrom-Json
    if (-not $r.ok) { Fail "[$stage] installed smoke ok != true" }
    if (-not $r.checks.vlc) { Fail "[$stage] installed smoke vlc check false (bundle vlc_libs not loading)" }
    if (-not $r.checks.rust) { Fail "[$stage] installed smoke rust check false" }
    if ($r.meipass -notlike "*$([IO.Path]::GetFileName($InstallDir))*" -and $r.meipass -notlike "*Doremi*") {
        Write-Host "WARNING [$stage] meipass not obviously inside install dir: $($r.meipass)"
    }
    # Prove VLC + Rust resolve from the INSTALL dir, not the repo/dist.
    $vlcDll = Join-Path $InstallDir "_internal\vlc_libs\libvlc.dll"
    if (-not (Test-Path $vlcDll)) { Fail "[$stage] missing installed VLC: $vlcDll" }
    $pyd = Get-ChildItem (Join-Path $InstallDir "_internal\doremi\native_rs\*.pyd") -ErrorAction SilentlyContinue
    if (-not $pyd) { Fail "[$stage] missing installed Rust extension (*.pyd under _internal/doremi/native_rs)" }
    Write-Host "[$stage] smoke OK (version $($r.version), build $($r.build_id)) vlc+rUST from bundle"
}

function Uninstall-Doremi {
    $unins = Join-Path $InstallDir "unins000.exe"
    if (-not (Test-Path $unins)) { Fail "[uninstall] missing $unins" }
    Write-Host "=== uninstall ==="
    $proc = Start-Process -FilePath $unins -ArgumentList @("/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES") -Wait -PassThru -NoNewWindow
    Write-Host "uninstaller exit code: $($proc.ExitCode)"
    if ($proc.ExitCode -ne 0) { Fail "[uninstall] exit code $($proc.ExitCode)" }
    if (Test-Path (Join-Path $InstallDir "Doremi.exe")) { Fail "[uninstall] Doremi.exe still present after uninstall" }
    # Install dir itself should be gone or empty (only logs may remain).
    if (Test-Path $InstallDir) {
        $left = Get-ChildItem $InstallDir -Recurse -ErrorAction SilentlyContinue
        if ($left -and $left.Count -gt 0) {
            Write-Host "WARNING [uninstall] leftovers under InstallDir:"
            $left | ForEach-Object { Write-Host "  $($_.FullName)" }
        } else { Write-Host "[uninstall] install dir empty/gone (good)" }
    } else { Write-Host "[uninstall] install dir removed (good)" }
    # Start Menu group entries owned by Doremi should be gone.
    $group = Join-Path ([Environment]::GetFolderPath("ApplicationData")) "Microsoft\Windows\Start Menu\Programs\Doremi"
    if (Test-Path (Join-Path $group "Doremi.lnk")) { Fail "[uninstall] Start Menu shortcut still present" }
    Write-Host "[uninstall] binaries + own shortcuts removed; user data checked separately"
}

# ---------------- main ----------------
if (-not (Test-Path $SetupExe)) { Fail "setup exe not found: $SetupExe" }
Write-Host "setup: $SetupExe ($([math]::Round((Get-Item $SetupExe).Length / 1MB, 1)) MB)"

$sentinels = New-Sentinels
$summary.sentinels = $sentinels

Install-Doremi "A-fresh"
$summary.scenarios["A_fresh_install"] = "pass"
Assert-Sentinels $sentinels "A"
$keyA = Check-AppId "A"
$summary.scenarios["A_AppId_key"] = $keyA
Check-Shortcuts "A"
Invoke-InstalledSmoke "A"

Install-Doremi "B-reinstall"
$summary.scenarios["B_reinstall_same_version"] = "pass"
Assert-Sentinels $sentinels "B"
$keyB = Check-AppId "B"
if ($keyB -ne $keyA) { Fail "[B] AppId key changed across reinstall: $keyA -> $keyB" }
Write-Host "[B] AppId stable across reinstall (good)"
Invoke-InstalledSmoke "B"

# C: no second version exists yet, so a cross-version upgrade cannot be
# exercised. Reinstalling with the same AppId + UsePreviousAppDir covers
# the upgrade code path (stable identity, dir reuse). Record honestly.
Install-Doremi "C-upgrade-simulated"
$summary.scenarios["C_upgrade_simulated_same_AppId"] = "pass (same-version reinstall; cross-version NOT verified)"
Assert-Sentinels $sentinels "C"
$keyC = Check-AppId "C"
if ($keyC -ne $keyA) { Fail "[C] AppId key changed across simulated upgrade: $keyA -> $keyC" }
$summary.scenarios["C_AppId_stable"] = $keyC

Uninstall-Doremi
$summary.scenarios["D_uninstall_binaries_removed"] = "pass"
Assert-Sentinels $sentinels "D"
$summary.scenarios["D_data_preserved"] = "pass ($($sentinels.Count) sentinel files incl. LOCALAPPDATA legacy path)"

$summary.ok = $true
$summary | ConvertTo-Json -Depth 6 | Set-Content $ResultJson -Encoding UTF8
Write-Host "ALL INSTALLER SCENARIOS PASSED. Summary: $ResultJson"
Get-Content $ResultJson
