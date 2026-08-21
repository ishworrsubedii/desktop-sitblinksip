<#
.SYNOPSIS
    Builds SitBlinkSip Desktop for Windows: a frozen app directory, plus an
    Inno Setup installer when ISCC.exe is available.

.DESCRIPTION
    Mirrors packaging/linux/build-deb.sh. Freezes the app with PyInstaller so
    end users need no Python, MediaPipe, OpenCV or Qt install of their own,
    then wraps the result in a per-user installer with Start Menu and
    uninstall entries.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging\windows\build-windows.ps1

.OUTPUTS
    dist\SitBlinkSipDesktop\            the frozen app
    dist\SitBlinkSipDesktop-<ver>-setup.exe   the installer (if Inno Setup is present)
#>
[CmdletBinding()]
param(
    # Skip the installer step even if Inno Setup is installed.
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$BuildDir    = Join-Path $ProjectRoot 'build'
$DistDir     = Join-Path $ProjectRoot 'dist'
$VenvDir     = Join-Path $BuildDir 'venv'
$AppName     = 'SitBlinkSipDesktop'

# mediapipe is pinned to ==0.10.14 on Windows (see requirements.txt), and that
# release only ships wheels for CPython 3.9-3.12. Whatever "python" means in
# the invoking shell is not trustworthy - conda, the Microsoft Store stub, and
# a 3.13 install all shadow it and fail deep inside pip with a confusing
# "no matching distribution" error. Ask the py launcher for a known-good
# version explicitly instead.
function Resolve-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($version in @('3.11', '3.10', '3.12', '3.9')) {
            # Probing for an absent version is an expected miss, not an error.
            # PowerShell 7.3+ turns a non-zero native exit code into a thrown
            # terminating error when $ErrorActionPreference is 'Stop', so this
            # loop has to catch rather than just read $LASTEXITCODE.
            try {
                & py "-$version" --version *> $null
                if ($LASTEXITCODE -eq 0) {
                    return [pscustomobject]@{ Exe = 'py'; Args = @("-$version") }
                }
            } catch {
                continue
            }
        }
    }

    # No py launcher: fall back to whatever `python` is, but only if its
    # version is actually one mediapipe builds for.
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $raw = (& python -c 'import sys; print("%d.%d" % sys.version_info[:2])').Trim()
        if ($raw -in @('3.9', '3.10', '3.11', '3.12')) {
            return [pscustomobject]@{ Exe = 'python'; Args = @() }
        }
        throw "Found python $raw, but mediapipe==0.10.14 has no wheel for it. Install Python 3.11 from python.org and re-run."
    }

    throw 'No suitable Python found. Install Python 3.11 (python.org, "Add to PATH" checked) and re-run.'
}

$Py = Resolve-Python

function Invoke-BuildPython {
    # Splat via a variable: `@($Py.Args + $args)` would be an array
    # *subexpression*, passing one array as a single argument instead of
    # spreading it, so `py -3.11 -m venv ...` would arrive as one string.
    $pythonArgs = @($Py.Args) + $args
    & $Py.Exe @pythonArgs
}

Write-Host "==> Using $($Py.Exe) $($Py.Args -join ' ') ($(Invoke-BuildPython --version 2>&1))"

$InitPath = Join-Path $ProjectRoot 'sitblinksip_desktop\__init__.py'
$Version = [regex]::Match((Get-Content -Raw $InitPath), '__version__\s*=\s*"([^"]+)"').Groups[1].Value
if (-not $Version) { throw "Could not read __version__ from $InitPath" }

Write-Host "==> Building $AppName $Version (win64)"

if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
if (Test-Path $DistDir)  { Remove-Item -Recurse -Force $DistDir }
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

Write-Host '==> Creating isolated build venv'
Invoke-BuildPython -m venv $VenvDir
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

& $VenvPython -m pip install --upgrade pip | Out-Null
& $VenvPython -m pip install -r (Join-Path $ProjectRoot 'requirements.txt') pyinstaller | Out-Null

Write-Host '==> Generating platform icons'
& $VenvPython (Join-Path $ProjectRoot 'scripts\generate_icons.py')

# mediapipe's legacy Pose Solutions API downloads its .tflite model into its
# own site-packages directory on first use instead of shipping it in the wheel
# (unlike FaceMesh, which is bundled). Triggering that download here means the
# spec's `collect_all("mediapipe")` picks the file up like any other bundled
# package data - otherwise every installed copy would re-download it, and any
# user without network access would silently get no posture checks.
Write-Host '==> Warming MediaPipe Pose model cache (one-time download)'
& $VenvPython -c "import mediapipe as mp; mp.solutions.pose.Pose(model_complexity=0).close()"

Write-Host '==> Freezing with PyInstaller'
& $VenvPython -m PyInstaller --noconfirm `
    --distpath $DistDir `
    --workpath (Join-Path $BuildDir 'pyinstaller-work') `
    (Join-Path $ProjectRoot 'packaging\pyinstaller\sitblinksip-desktop.spec')

$FrozenExe = Join-Path $DistDir "$AppName\$AppName.exe"
if (-not (Test-Path $FrozenExe)) { throw "PyInstaller did not produce $FrozenExe" }
Write-Host "==> Frozen app: $(Join-Path $DistDir $AppName)"

if ($SkipInstaller) {
    Write-Host '==> Skipping installer (-SkipInstaller)'
    exit 0
}

# Inno Setup is the installer toolchain; it is not a build requirement, so a
# missing ISCC just means "you get the app directory, not a setup.exe".
$Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $Iscc) {
    foreach ($candidate in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )) {
        if (Test-Path $candidate) { $Iscc = $candidate; break }
    }
} else {
    $Iscc = $Iscc.Source
}

if (-not $Iscc) {
    Write-Warning @"
Inno Setup 6.3+ not found, so no installer was built.
The frozen app in dist\$AppName is complete and runnable - launch $AppName.exe.
To build the installer, install Inno Setup (https://jrsoftware.org/isdl.php)
and re-run this script.
"@
    exit 0
}

Write-Host '==> Building installer with Inno Setup'
& $Iscc "/DMyAppVersion=$Version" (Join-Path $ScriptDir 'sitblinksip-desktop.iss')

Write-Host "==> Done: $(Join-Path $DistDir "$AppName-$Version-setup.exe")"
