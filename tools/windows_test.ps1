#requires -Version 5.1
<#
.SYNOPSIS
    Run SeekR's automated checks and Windows build on a real Windows PC.

.DESCRIPTION
    Creates or reuses .venv, installs development requirements, byte-compiles,
    runs pytest, checks the version command, builds dist\SeekR.exe and checks
    the executable metadata. Writes a detailed report to
    windows_test_results.txt in the repository root.

    This script is intentionally Windows-only: it does not emulate Windows and
    does not validate a Linux build as a Windows executable.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows_test.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot
$ReportPath = Join-Path $RepoRoot "windows_test_results.txt"
$script:Results = @()
$script:HasFailure = $false

Set-Content -LiteralPath $ReportPath -Value "" -Encoding UTF8

function Add-Line {
    param([string]$Text = "")
    Add-Content -LiteralPath $ReportPath -Value $Text -Encoding UTF8
    Write-Host $Text
}

function Add-Result {
    param(
        [string]$Name,
        [ValidateSet("PASS", "FAIL", "SKIPPED")]
        [string]$Status,
        [string]$Detail = ""
    )
    $suffix = ""
    if ($Detail) {
        $suffix = " - $Detail"
    }
    $script:Results += [pscustomobject]@{
        Name = $Name
        Status = $Status
        Detail = $Detail
    }
    if ($Status -eq "FAIL") {
        $script:HasFailure = $true
    }
    Add-Line ("[{0}] {1}{2}" -f $Status, $Name, $suffix)
}

function Invoke-Native {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$Arguments
    )
    Add-Line ""
    Add-Line ("=== {0} ===" -f $Label)
    Add-Line ("> `"{0}`" {1}" -f $FilePath, ($Arguments -join " "))
    $global:LASTEXITCODE = 0
    try {
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    catch {
        $output = @($_.Exception.Message)
        $exitCode = 1
    }
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    foreach ($line in @($output)) {
        Add-Line ("  " + [string]$line)
    }
    $text = @($output) | Out-String
    if ($null -eq $text) {
        $text = ""
    }
    return [pscustomobject]@{
        ExitCode = [int]$exitCode
        Output = $text.Trim()
    }
}

function Show-Summary {
    $pass = @($script:Results | Where-Object { $_.Status -eq "PASS" }).Count
    $fail = @($script:Results | Where-Object { $_.Status -eq "FAIL" }).Count
    $skipped = @($script:Results | Where-Object { $_.Status -eq "SKIPPED" }).Count
    Add-Line ""
    Add-Line "===== SUMMARY ====="
    Add-Line ("PASS: {0}  FAIL: {1}  SKIPPED: {2}" -f $pass, $fail, $skipped)
    foreach ($result in $script:Results) {
        Add-Line ("  [{0}] {1}" -f $result.Status, $result.Name)
    }
    if ($fail -gt 0) {
        Add-Line "RESULT: FAIL - see the failing sections above."
        Add-Line ("Report: {0}" -f $ReportPath)
        exit 1
    }
    Add-Line "RESULT: PASS - automated Windows checks succeeded."
    Add-Line "The GUI and shell integration still require the manual checklist:"
    Add-Line "  docs/WINDOWS_MANUAL_TEST.md"
    Add-Line ("Report: {0}" -f $ReportPath)
    exit 0
}

Add-Line "SeekR Windows validation"
Add-Line ("Date: {0}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))
Add-Line ("Computer: {0}" -f $env:COMPUTERNAME)
Add-Line ("OS: {0}" -f [System.Environment]::OSVersion.VersionString)
Add-Line ("PowerShell: {0}" -f $PSVersionTable.PSVersion.ToString())
Add-Line ("Repository: {0}" -f $RepoRoot)
$gitHead = "unknown"
try {
    $gitHead = (& git rev-parse --short HEAD 2>$null | Select-Object -First 1)
}
catch {
    $gitHead = "not a git checkout"
}
Add-Line ("Git HEAD: {0}" -f $gitHead)
Add-Line ""

$isWindowsHost = ([System.Environment]::OSVersion.Platform -eq "Win32NT")
if (-not $isWindowsHost) {
    Add-Result "Windows host" "FAIL" "This script must run on Windows 10 or 11, not $($PSVersionTable.OS)."
    Show-Summary
}
Add-Result "Windows host" "PASS" ([System.Environment]::OSVersion.VersionString)

# ---------------------------------------------------------------- Python found
$pythonExe = $null
$pythonPrefix = @()
$probe = $null

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) {
    $probe = Invoke-Native "Probe Python launcher" $pyLauncher.Source @("-3", "--version")
    if ($probe.ExitCode -eq 0) {
        $pythonExe = $pyLauncher.Source
        $pythonPrefix = @("-3")
    }
}

if (-not $pythonExe) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $probe = Invoke-Native "Probe python on PATH" $pythonCommand.Source @("--version")
        if ($probe.ExitCode -eq 0) {
            $pythonExe = $pythonCommand.Source
        }
    }
}

$pythonOk = $false
$pythonVersion = $null
if ($pythonExe -and $probe) {
    $match = [regex]::Match($probe.Output, "Python\s+(\d+\.\d+\.\d+)")
    if ($match.Success) {
        $pythonVersion = [version]$match.Groups[1].Value
        if ($pythonVersion -ge [version]"3.10") {
            $pythonOk = $true
            Add-Result "Python version" "PASS" ("Python {0} at {1}" -f $pythonVersion, $pythonExe)
        }
        else {
            Add-Result "Python version" "FAIL" ("Python {0} is too old; install Python 3.10+ (3.12 recommended)." -f $pythonVersion)
        }
    }
    else {
        Add-Result "Python version" "FAIL" "Could not parse the Python version output."
    }
}
else {
    Add-Result "Python version" "FAIL" "Python 3 was not found. Install Python 3.10+ and enable the 'py' launcher or add python.exe to PATH."
}

# ---------------------------------------------------------------------- venv
$venvDir = Join-Path $RepoRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvOk = $false

if ($pythonOk) {
    if (Test-Path -LiteralPath $venvPython) {
        $existing = Invoke-Native "Check existing virtual environment" $venvPython @("--version")
        if ($existing.ExitCode -eq 0) {
            $venvOk = $true
            Add-Result "Virtual environment" "PASS" "Reusing the existing .venv"
        }
        else {
            Add-Result "Virtual environment" "FAIL" "Existing .venv\Scripts\python.exe does not run; remove .venv and rerun."
        }
    }
    else {
        $venvArgs = @()
        if ($pythonPrefix.Count -gt 0) {
            $venvArgs += $pythonPrefix
        }
        $venvArgs += @("-m", "venv", $venvDir)
        $created = Invoke-Native "Create virtual environment" $pythonExe $venvArgs
        if ($created.ExitCode -eq 0 -and (Test-Path -LiteralPath $venvPython)) {
            $venvOk = $true
            Add-Result "Virtual environment" "PASS" "Created .venv"
        }
        else {
            Add-Result "Virtual environment" "FAIL" "Could not create .venv; inspect the output above."
        }
    }
}
else {
    Add-Result "Virtual environment" "SKIPPED" "Python 3.10+ is unavailable."
}

# -------------------------------------------------------------- dependencies
$installOk = $false
if ($venvOk) {
    $requirements = Join-Path $RepoRoot "requirements-dev.txt"
    $install = Invoke-Native "Install development requirements" $venvPython @(
        "-m", "pip", "install", "--disable-pip-version-check", "-r", $requirements
    )
    if ($install.ExitCode -eq 0) {
        $installOk = $true
        Add-Result "Install development requirements" "PASS" "pip install completed"
    }
    else {
        Add-Result "Install development requirements" "FAIL" "pip install failed; check the network and the output above."
    }
}
else {
    Add-Result "Install development requirements" "SKIPPED" "No usable virtual environment."
}

$depsOk = $false
if ($venvOk) {
    $dependencyScript = @'
import importlib.util
import sys

required = [
    ("PySide6", "PySide6"),
    ("psutil", "psutil"),
    ("sympy", "sympy"),
    ("tzdata", "tzdata"),
    ("PyInstaller", "pyinstaller"),
    ("pytest", "pytest"),
]
missing = []
for module, package in required:
    try:
        found = importlib.util.find_spec(module) is not None
    except Exception:
        found = False
    print(f"{package}: {'OK' if found else 'MISSING'}")
    if not found:
        missing.append(package)
print("Python:", sys.version.split()[0])
if missing:
    print("Missing: " + ", ".join(missing))
    sys.exit(1)
'@
    # Write the checker to a temporary .py file instead of passing multiline
    # source through `python -c`. PowerShell 5.1 mangles newlines/quotes in
    # native command arguments, which produced a Python syntax error.
    if (-not $env:TEMP) {
        $env:TEMP = [System.IO.Path]::GetTempPath()
    }
    $depCheckPath = Join-Path $env:TEMP "seekr_dep_check.py"
    try {
        Set-Content -LiteralPath $depCheckPath -Value $dependencyScript -Encoding UTF8
        $deps = Invoke-Native "Check required dependencies" $venvPython @($depCheckPath)
    }
    finally {
        Remove-Item -LiteralPath $depCheckPath -Force -ErrorAction SilentlyContinue
    }
    if ($deps.ExitCode -eq 0) {
        $depsOk = $true
        Add-Result "Required dependencies" "PASS" "All runtime, test and build packages import"
    }
    else {
        Add-Result "Required dependencies" "FAIL" "One or more packages are missing; fix the pip install before retrying."
    }
}
else {
    Add-Result "Required dependencies" "SKIPPED" "No usable virtual environment."
}

# ------------------------------------------------------------- byte compilation
if ($venvOk) {
    $compile = Invoke-Native "Byte-compile sources" $venvPython @(
        "-m", "compileall", "-q", "core", "features", "ui", "main.py", "build.py", "tests"
    )
    if ($compile.ExitCode -eq 0) {
        Add-Result "Byte-compilation" "PASS" "No syntax errors"
    }
    else {
        Add-Result "Byte-compilation" "FAIL" "compileall reported errors"
    }
}
else {
    Add-Result "Byte-compilation" "SKIPPED" "No usable virtual environment."
}

# ------------------------------------------------------------------- pytest
if ($venvOk -and $depsOk) {
    # Use the native Windows Qt platform so this is a real Windows GUI import
    # test, not the offscreen Linux fallback.
    $env:QT_QPA_PLATFORM = "windows"
    $pytest = Invoke-Native "Run complete pytest suite" $venvPython @("-m", "pytest", "-q")
    $passedCount = 0
    $skippedCount = 0
    if ($pytest.Output -match "(\d+) passed") {
        $passedCount = [int]$Matches[1]
    }
    if ($pytest.Output -match "(\d+) skipped") {
        $skippedCount = [int]$Matches[1]
    }
    if ($pytest.ExitCode -eq 0) {
        $pytestDetail = "{0} passed" -f $passedCount
        if ($skippedCount -gt 0) {
            $pytestDetail = $pytestDetail + (", {0} skipped (see test output)" -f $skippedCount)
        }
        Add-Result "Pytest suite" "PASS" $pytestDetail
        if ($skippedCount -gt 0) {
            Add-Result "Pytest skipped tests" "SKIPPED" ("{0} platform-specific test(s) skipped; inspect the output above" -f $skippedCount)
        }
    }
    else {
        Add-Result "Pytest suite" "FAIL" ("pytest exited with code {0}" -f $pytest.ExitCode)
    }
}
else {
    Add-Result "Pytest suite" "SKIPPED" "Dependencies or the virtual environment are unavailable."
}

# -------------------------------------------------------------------- version
if ($venvOk -and $depsOk) {
    $versionCheck = Invoke-Native "Check SeekR --version" $venvPython @("main.py", "--version")
    if ($versionCheck.ExitCode -eq 0 -and $versionCheck.Output -match "SeekR\s+1\.0\.0") {
        Add-Result "Version command" "PASS" "main.py --version reports SeekR 1.0.0"
    }
    else {
        Add-Result "Version command" "FAIL" "main.py --version failed or did not print SeekR 1.0.0"
    }
}
else {
    Add-Result "Version command" "SKIPPED" "Dependencies or the virtual environment are unavailable."
}

# ---------------------------------------------------------------------- build
$exePath = Join-Path $RepoRoot "dist\SeekR.exe"
$buildOk = $false

if ($venvOk -and $depsOk) {
    # Remove a stale artifact so a failed build can never be mistaken for success.
    Remove-Item -LiteralPath $exePath -Force -ErrorAction SilentlyContinue
    $build = Invoke-Native "Build Windows executable" $venvPython @("build.py")
    if ($build.ExitCode -eq 0) {
        $buildOk = $true
        Add-Result "Build executable" "PASS" "python build.py completed"
    }
    else {
        Add-Result "Build executable" "FAIL" ("python build.py exited with code {0}" -f $build.ExitCode)
    }
}
else {
    Add-Result "Build executable" "SKIPPED" "Dependencies or the virtual environment are unavailable."
}

if ($buildOk -and (Test-Path -LiteralPath $exePath)) {
    $sizeMb = (Get-Item -LiteralPath $exePath).Length / 1MB
    Add-Result "Executable exists" "PASS" ("{0} ({1:N1} MiB)" -f $exePath, $sizeMb)
}
elseif (-not $buildOk) {
    Add-Result "Executable exists" "SKIPPED" "The build did not succeed."
}
else {
    Add-Result "Executable exists" "FAIL" "build.py succeeded but dist\SeekR.exe is missing."
}

if (Test-Path -LiteralPath $exePath) {
    try {
        $versionInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($exePath)
        $productOk = ($versionInfo.ProductName -eq "SeekR")
        $versionOk = ($versionInfo.ProductVersion -match "^1\.0\.0")
        if ($productOk -and $versionOk) {
            Add-Result "Executable version metadata" "PASS" ("ProductName={0}; ProductVersion={1}" -f $versionInfo.ProductName, $versionInfo.ProductVersion)
        }
        else {
            Add-Result "Executable version metadata" "FAIL" ("ProductName={0}; ProductVersion={1}" -f $versionInfo.ProductName, $versionInfo.ProductVersion)
        }
    }
    catch {
        Add-Result "Executable version metadata" "FAIL" ("Could not read version metadata: {0}" -f $_.Exception.Message)
    }
}
else {
    Add-Result "Executable version metadata" "SKIPPED" "dist\SeekR.exe does not exist."
}

Show-Summary
