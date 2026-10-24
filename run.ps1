param([switch]$Calibrate, [int]$MaxCasts = 10, [double]$LatencyMs = 35,
      [int]$PreviewFps = 10, [int]$ControlFps = 60, [switch]$NoPreview, [switch]$DebugLog)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run .\setup.ps1 first.' }
$fishingArgs = @('-m', 'fishing', '--max-casts', $MaxCasts, '--latency-ms', $LatencyMs,
                '--preview-fps', $PreviewFps, '--control-fps', $ControlFps)
if ($Calibrate) { $fishingArgs += '--calibrate' }
if ($NoPreview) { $fishingArgs += '--no-preview' }
if ($DebugLog) { $fishingArgs += '--verbose' }
& .\.venv\Scripts\python.exe @fishingArgs
