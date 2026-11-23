param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,
    [ValidateRange(1, 168)]
    [int]$DurationHours = 24,
    [ValidateRange(0, 10080)]
    [int]$DurationMinutes = 0,
    [ValidateRange(5, 3600)]
    [int]$SampleIntervalSeconds = 30,
    [string]$OutputPath = ".\seekr-stability.csv"
)

$ErrorActionPreference = "Stop"
$exe = (Resolve-Path -LiteralPath $ExecutablePath).Path
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Executable does not exist: $ExecutablePath"
}

$process = Start-Process -FilePath $exe -ArgumentList @("--hidden") -PassThru
$records = [System.Collections.Generic.List[object]]::new()
$watch = [Diagnostics.Stopwatch]::StartNew()
$failure = $null
try {
    $durationMinutes = if ($DurationMinutes -gt 0) { $DurationMinutes } else { $DurationHours * 60 }
    while ($watch.Elapsed.TotalMinutes -lt $durationMinutes) {
        Start-Sleep -Seconds $SampleIntervalSeconds
        $process.Refresh()
        if ($process.HasExited) {
            $failure = "SeekR exited unexpectedly with code $($process.ExitCode)"
            break
        }
        $records.Add([pscustomobject]@{
            timestamp = (Get-Date).ToString("o")
            elapsed_minutes = [math]::Round($watch.Elapsed.TotalMinutes, 2)
            cpu_seconds = [math]::Round($process.CPU, 2)
            working_set_mb = [math]::Round($process.WorkingSet64 / 1MB, 2)
            private_bytes_mb = [math]::Round($process.PrivateMemorySize64 / 1MB, 2)
            threads = $process.Threads.Count
            handles = $process.HandleCount
        })
    }
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        $process.WaitForExit()
    }
    $records | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding UTF8
}

if ($failure) {
    throw $failure
}
if ($records.Count -eq 0) {
    throw "No stability samples were collected."
}
$memory = @($records | ForEach-Object { [double]$_.private_bytes_mb })
$growthMb = [double]$memory[-1] - [double]$memory[0]
if ($growthMb -gt 100) {
    throw "Private memory grew by more than 100 MB during the stability run ($([math]::Round($growthMb, 2)) MB)."
}
$summary = [pscustomobject]@{
    duration_hours = [math]::Round($durationMinutes / 60, 2)
    duration_minutes = $durationMinutes
    samples = $records.Count
    private_memory_start_mb = $memory[0]
    private_memory_end_mb = $memory[-1]
    private_memory_growth_mb = [math]::Round($growthMb, 2)
    private_memory_peak_mb = ($memory | Measure-Object -Maximum).Maximum
    output_csv = (Resolve-Path -LiteralPath $OutputPath).Path
    note = "Hidden-mode stability run; repeat with interactive usage and real widget/network activity before release."
}
$summary | ConvertTo-Json -Depth 4 | Write-Output
