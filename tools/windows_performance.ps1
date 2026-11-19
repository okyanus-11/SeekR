param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,
    [int]$IdleSeconds = 30,
    [int]$TimeoutSeconds = 60,
    [string]$OutputPath = ".\seekr-windows-performance.json"
)

$ErrorActionPreference = "Stop"
$exe = (Resolve-Path -LiteralPath $ExecutablePath).Path
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Executable does not exist: $ExecutablePath"
}

if (-not ("SeekR.NativeWindow" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace SeekR { public static class NativeWindow {
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
} }
'@
}

function Wait-ForVisibleWindow([System.Diagnostics.Process]$Process, [int]$Timeout) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.Elapsed.TotalSeconds -lt $Timeout) {
        $Process.Refresh()
        if ($Process.HasExited) {
            throw "SeekR exited before its window became visible (exit $($Process.ExitCode))."
        }
        $handle = $Process.MainWindowHandle
        if ($handle -ne [IntPtr]::Zero -and [SeekR.NativeWindow]::IsWindowVisible($handle)) {
            return [math]::Round($watch.Elapsed.TotalMilliseconds, 1)
        }
        Start-Sleep -Milliseconds 50
    }
    throw "Timed out waiting for SeekR's visible window."
}

function Start-VisibleMeasurement([string]$Label, [string[]]$Arguments) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    if ($Arguments.Count -gt 0) {
        $process = Start-Process -FilePath $exe -ArgumentList $Arguments -PassThru
    }
    else {
        $process = Start-Process -FilePath $exe -PassThru
    }
    try {
        $visibleMs = Wait-ForVisibleWindow -Process $process -Timeout $TimeoutSeconds
        return [pscustomobject]@{
            scenario = $Label
            process_start_to_visible_ms = $visibleMs
            pid = $process.Id
        }
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }
}

function Measure-HotkeyLatency {
    $process = Start-Process -FilePath $exe -ArgumentList @("--hidden") -PassThru
    try {
        Start-Sleep -Seconds 2
        $shell = New-Object -ComObject WScript.Shell
        $watch = [Diagnostics.Stopwatch]::StartNew()
        $shell.SendKeys("%{SPACE}")
        $latency = Wait-ForVisibleWindow -Process $process -Timeout 10
        return [pscustomobject]@{
            scenario = "Alt+Space hotkey-to-visible"
            hotkey_to_visible_ms = $latency
            pid = $process.Id
        }
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }
}

function Measure-HiddenIdle([int]$Seconds) {
    $process = Start-Process -FilePath $exe -ArgumentList @("--hidden") -PassThru
    try {
        Start-Sleep -Seconds 10
        $process.Refresh()
        $cpuStart = $process.CPU
        $sampleStart = Get-Date
        $workingStart = $process.WorkingSet64
        $privateStart = $process.PrivateMemorySize64
        $threadStart = $process.Threads.Count
        Start-Sleep -Seconds $Seconds
        $process.Refresh()
        $elapsed = ((Get-Date) - $sampleStart).TotalSeconds
        $cpuDelta = [math]::Max(0, $process.CPU - $cpuStart)
        $cpuPercent = 100.0 * $cpuDelta / ($elapsed * [Environment]::ProcessorCount)
        return [pscustomobject]@{
            scenario = "Hidden idle"
            sample_seconds = [math]::Round($elapsed, 1)
            average_cpu_percent = [math]::Round($cpuPercent, 2)
            working_set_start_mb = [math]::Round($workingStart / 1MB, 2)
            working_set_end_mb = [math]::Round($process.WorkingSet64 / 1MB, 2)
            private_bytes_start_mb = [math]::Round($privateStart / 1MB, 2)
            private_bytes_end_mb = [math]::Round($process.PrivateMemorySize64 / 1MB, 2)
            thread_count_start = $threadStart
            thread_count_end = $process.Threads.Count
            pid = $process.Id
        }
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }
}

$results = [ordered]@{
    measured_at = (Get-Date).ToString("o")
    executable = $exe
    os = [System.Environment]::OSVersion.VersionString
    processor_count = [Environment]::ProcessorCount
    scenarios = @(
        (Start-VisibleMeasurement -Label "Cold process start" -Arguments @()),
        (Start-VisibleMeasurement -Label "Warm process start" -Arguments @()),
        (Measure-HotkeyLatency),
        (Measure-HiddenIdle -Seconds $IdleSeconds)
    )
    notes = @(
        "Cold and warm are sequential launches in the same OS session, not reboot-cold measurements.",
        "The script measures process start to visible main-window handle; it does not measure first interactive paint.",
        "Run from a clean desktop session and repeat on every supported Windows version and DPI configuration."
    )
}
$json = $results | ConvertTo-Json -Depth 6
$json | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output $json
Write-Host "Saved performance results to $OutputPath"
