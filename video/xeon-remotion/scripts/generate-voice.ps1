param(
    [string]$VoiceId
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$secureKey = Read-Host 'Pega tu clave NUEVA de ElevenLabs (entrada oculta)' -AsSecureString
$plainKey = [System.Net.NetworkCredential]::new('', $secureKey).Password
try {
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        throw 'No se introdujo una clave.'
    }
    $env:ELEVENLABS_API_KEY = $plainKey
    $env:XEON_ELEVENLABS_NONCOMMERCIAL = 'true'
    if ([string]::IsNullOrWhiteSpace($VoiceId)) {
        Write-Host 'Voces disponibles en tu cuenta (elige una que suene natural en espanol):'
        Push-Location $projectRoot
        try {
            node scripts/list-elevenlabs-voices.mjs
            if ($LASTEXITCODE -ne 0) { throw 'No se pudo listar las voces.' }
        } finally { Pop-Location }
        $VoiceId = Read-Host 'Copia el ID de la voz elegida'
    }
    if ([string]::IsNullOrWhiteSpace($VoiceId)) {
        throw 'No se eligio una voz.'
    }
    $env:ELEVENLABS_VOICE_ID = $VoiceId
    Push-Location $projectRoot
    try {
        node scripts/generate-elevenlabs.mjs
        if ($LASTEXITCODE -ne 0) { throw 'No se genero la narracion.' }
    } finally { Pop-Location }
} finally {
    Remove-Item Env:ELEVENLABS_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:ELEVENLABS_VOICE_ID -ErrorAction SilentlyContinue
    Remove-Item Env:XEON_ELEVENLABS_NONCOMMERCIAL -ErrorAction SilentlyContinue
    $plainKey = $null
    $secureKey.Dispose()
}
