$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Destination = Join-Path $Root "vendor\ffmpeg\bin"
$NoticeDestination = Split-Path -Parent $Destination
if ((Test-Path (Join-Path $Destination "ffmpeg.exe")) -and
    (Test-Path (Join-Path $Destination "ffprobe.exe")) -and
    (Test-Path (Join-Path $NoticeDestination "LICENSE.txt")) -and
    (Test-Path (Join-Path $NoticeDestination "README.txt"))) {
    Write-Host "FFmpeg already prepared."
    exit 0
}

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mapa-roto-ffmpeg-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $TempRoot | Out-Null
try {
    $Archive = Join-Path $TempRoot "ffmpeg.zip"
    Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $Archive
    Expand-Archive $Archive -DestinationPath (Join-Path $TempRoot "expanded")
    $Ffmpeg = Get-ChildItem (Join-Path $TempRoot "expanded") -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    $Ffprobe = Get-ChildItem (Join-Path $TempRoot "expanded") -Recurse -Filter "ffprobe.exe" | Select-Object -First 1
    if (-not $Ffmpeg -or -not $Ffprobe) { throw "FFmpeg archive did not contain both executables." }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item $Ffmpeg.FullName (Join-Path $Destination "ffmpeg.exe")
    Copy-Item $Ffprobe.FullName (Join-Path $Destination "ffprobe.exe")
    $ExpandedRoot = Join-Path $TempRoot "expanded"
    $License = Get-ChildItem $ExpandedRoot -Recurse -File |
        Where-Object { $_.Name -match '^LICENSE(\.txt)?$' } | Select-Object -First 1
    $Readme = Get-ChildItem $ExpandedRoot -Recurse -File |
        Where-Object { $_.Name -match '^README(\.txt)?$' } | Select-Object -First 1
    if (-not $License -or -not $Readme) {
        throw "FFmpeg archive did not contain the expected license and build readme."
    }
    if ($License) { Copy-Item $License.FullName (Join-Path $NoticeDestination "LICENSE.txt") }
    if ($Readme) { Copy-Item $Readme.FullName (Join-Path $NoticeDestination "README.txt") }
    Write-Host "FFmpeg prepared at $Destination"
}
finally {
    if (Test-Path $TempRoot) { Remove-Item $TempRoot -Recurse -Force }
}
