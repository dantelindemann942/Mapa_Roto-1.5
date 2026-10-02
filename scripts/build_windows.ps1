param([string]$Version = "0.1.5")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "[1/6] Building MAPA ROTO interface"
Push-Location "local-ui"
npm ci
if ($LASTEXITCODE -ne 0) { throw "npm ci failed ($LASTEXITCODE)" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Interface build failed ($LASTEXITCODE)" }
Pop-Location

Write-Host "[2/6] Installing Python build dependencies"
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed ($LASTEXITCODE)" }
python -m pip install -r requirements-desktop.txt -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed ($LASTEXITCODE)" }

Write-Host "[3/6] Bundling FFmpeg"
& "$Root\scripts\fetch_ffmpeg.ps1"

Write-Host "[4/6] Building branded icon"
python "$Root\scripts\build_icon.py"
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed ($LASTEXITCODE)" }

Write-Host "[5/6] Compiling desktop application"
python -m PyInstaller --noconfirm --clean "$Root\packaging\mapa-roto.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }
& "$Root\dist\MapaRotoClip\MapaRotoWorker.exe" --self-test-detached
if ($LASTEXITCODE -ne 0) { throw "Packaged self-test failed with exit code $LASTEXITCODE" }

Write-Host "[6/6] Creating Windows installer"
$IsccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) { throw "Inno Setup 6 is required: https://jrsoftware.org/isdl.php" }
& $Iscc "/DMyAppVersion=$Version" "$Root\packaging\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed ($LASTEXITCODE)" }
Write-Host "Installer ready in $Root\release"
