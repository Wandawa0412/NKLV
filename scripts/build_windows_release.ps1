Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PytestTemp = Join-Path $ProjectRoot ".temp\pytest-tmp"
$DistDir = Join-Path $ProjectRoot "dist\NKLV_ECOS_2026"
$RuntimeTempDir = Join-Path $DistDir ".temp"
$ReleaseDir = Join-Path $ProjectRoot "release"
$InstallerScript = Join-Path $ProjectRoot "installer\NKLV_ECOS_2026.iss"

function Get-InnoSetupCompiler {
    $command = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $knownPaths = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )

    foreach ($path in $knownPaths) {
        if (Test-Path $path) {
            return $path
        }
    }

    throw "ISCC.exe not found. Install Inno Setup 6 first."
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)]
        [string] $FilePath,

        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

Push-Location $ProjectRoot
try {
    New-Item -ItemType Directory -Force $PytestTemp | Out-Null
    New-Item -ItemType Directory -Force $ReleaseDir | Out-Null

    $env:TEMP = (Resolve-Path $PytestTemp)
    $env:TMP = $env:TEMP

    Invoke-External "python" "-m" "ruff" "check" "main.py" "core" "ui" "tests"
    Invoke-External "python" "-m" "compileall" "main.py" "core" "ui" "tests"
    Invoke-External "python" "-m" "pytest" "tests" "-q" "-p" "no:cacheprovider"
    Invoke-External "python" "-m" "PyInstaller" "NKLV.spec" "--clean" "--noconfirm"

    if (-not (Test-Path $DistDir)) {
        throw "PyInstaller output not found: $DistDir"
    }
    New-Item -ItemType Directory -Force $RuntimeTempDir | Out-Null

    $iscc = Get-InnoSetupCompiler
    Invoke-External $iscc $InstallerScript
}
finally {
    Pop-Location
}
