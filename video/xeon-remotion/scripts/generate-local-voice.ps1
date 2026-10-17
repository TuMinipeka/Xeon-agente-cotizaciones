param([string]$Voice)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$scriptData = Get-Content -LiteralPath (Join-Path $projectRoot 'narration-script.json') -Raw | ConvertFrom-Json
if (-not $Voice) { $Voice = $scriptData.voice }
$destination = Join-Path $projectRoot 'public/voice-local/lines'
New-Item -ItemType Directory -Path $destination -Force | Out-Null

$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $synth.SelectVoice($Voice)
    $synth.Rate = 1
    $synth.Volume = 100
    $index = 0
    foreach ($scene in $scriptData.scenes) {
        foreach ($line in $scene.lines) {
            $target = Join-Path $destination ('{0:D2}.wav' -f $index)
            $synth.SetOutputToWaveFile($target)
            $synth.Speak([string]$line)
            $synth.SetOutputToNull()
            $index++
        }
    }
    Write-Output "Generados $index fragmentos locales con $Voice."
} finally {
    $synth.Dispose()
}
