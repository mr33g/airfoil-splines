param(
    [string]$Version = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Python = (Get-Command $Python -ErrorAction Stop).Source

function Get-VersionFromGit {
    try {
        $tag = git describe --tags --abbrev=0 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        return $tag.Trim()
    } catch {
        return $null
    }
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $tag = Get-VersionFromGit
    if ($tag) { $Version = $tag }
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = "1.0.0"
}

if ($Version.StartsWith("v")) {
    $Version = $Version.Substring(1)
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$distDir = Join-Path $root "dist"
$wxsOut = Join-Path $PSScriptRoot "Files.wxs"
$msiOut = Join-Path $distDir "AirfoilSplines-$Version.msi"

Push-Location $root
try {
    & $Python -m PyInstaller AirfoilSplines.spec --noconfirm --clean
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    $configSource = Join-Path $root "setup\default-config.json"
    $configDest = Join-Path $distDir "AirfoilSplines\\airfoil_splines.config.json"
    if (Test-Path $configSource) {
        Copy-Item -Path $configSource -Destination $configDest -Force
    } else {
        throw "Missing config template: $configSource"
    }
} finally {
    Pop-Location
}

Push-Location $PSScriptRoot
try {
    & $Python .\generate_wxs_fragment.py --source-dir $distDir\AirfoilSplines --output $wxsOut
    if ($LASTEXITCODE -ne 0) { throw "WiX file harvesting failed with exit code $LASTEXITCODE" }
    wix build .\AirfoilSplines.wxs $wxsOut -ext WixToolset.UI.wixext -ext WixToolset.Util.wixext -d Version=$Version -o $msiOut
    if ($LASTEXITCODE -ne 0) { throw "WiX failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host "Built MSI: $msiOut"
