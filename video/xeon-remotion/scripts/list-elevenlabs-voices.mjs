const apiKey = process.env.ELEVENLABS_API_KEY;
if (!apiKey) throw new Error('Falta ELEVENLABS_API_KEY en el proceso.');
const response = await fetch('https://api.elevenlabs.io/v1/voices?show_legacy=true', {
  headers: {'xi-api-key': apiKey},
});
if (!response.ok) throw new Error(`No se pudo consultar voces disponibles (HTTP ${response.status}).`);
const result = await response.json();
const voices = result.voices ?? [];
for (const voice of voices) {
  const labels = Object.entries(voice.labels ?? {}).map(([key, value]) => `${key}=${value}`).join(', ');
  console.log(`${voice.voice_id}  ${voice.name}${labels ? `  (${labels})` : ''}`);
}
if (voices.length === 0) throw new Error('La cuenta no devolvio voces disponibles.');
