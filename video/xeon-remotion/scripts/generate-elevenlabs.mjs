import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {Buffer} from 'node:buffer';
import path from 'node:path';

// Deliberately never print or persist ELEVENLABS_API_KEY.
const apiKey = process.env.ELEVENLABS_API_KEY;
const voiceId = process.env.ELEVENLABS_VOICE_ID;
const nonCommercial = process.env.XEON_ELEVENLABS_NONCOMMERCIAL === 'true';
const root = process.cwd();
const scenes = JSON.parse(await readFile(path.join(root, 'narration-v2.json'), 'utf8'));
const text = scenes.map((scene) => scene.text).join('\n\n');
const estimatedCredits = text.length;

if (!apiKey || !voiceId) {
  throw new Error('Configura ELEVENLABS_API_KEY y ELEVENLABS_VOICE_ID localmente; no los escribas en el repositorio.');
}
if (!nonCommercial) {
  throw new Error('El plan gratuito de ElevenLabs no permite uso comercial. Confirma uso no comercial con XEON_ELEVENLABS_NONCOMMERCIAL=true.');
}

const subscriptionResponse = await fetch('https://api.elevenlabs.io/v1/user/subscription', {
  headers: {'xi-api-key': apiKey},
});
if (!subscriptionResponse.ok) {
  throw new Error(`No se pudo comprobar la cuota de ElevenLabs (HTTP ${subscriptionResponse.status}).`);
}
const subscription = await subscriptionResponse.json();
const remaining = subscription.character_limit - subscription.character_count;
if (subscription.tier !== 'free' || !Number.isFinite(remaining) || remaining < estimatedCredits + 200) {
  throw new Error(`Generación detenida: se requiere plan free y al menos ${estimatedCredits + 200} créditos gratuitos disponibles.`);
}

const response = await fetch(
  `https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(voiceId)}/with-timestamps?output_format=mp3_44100_128`,
  {
    method: 'POST',
    headers: {'xi-api-key': apiKey, 'Content-Type': 'application/json'},
    body: JSON.stringify({
      text,
      model_id: 'eleven_multilingual_v2',
      voice_settings: {stability: 0.52, similarity_boost: 0.78, style: 0.15, use_speaker_boost: true, speed: 1},
    }),
  },
);
if (!response.ok) {
  throw new Error(`ElevenLabs no generó la voz (HTTP ${response.status}); no se guardó audio.`);
}
const result = await response.json();
const alignment = result.alignment;
if (!result.audio_base64 || !alignment || alignment.characters.join('') !== text) {
  throw new Error('La respuesta no incluye audio y alineación completos; no se guardó audio.');
}

const sceneTimings = [];
let cursor = 0;
for (const scene of scenes) {
  const start = alignment.character_start_times_seconds[cursor] ?? 0;
  const endIndex = cursor + scene.text.length - 1;
  const end = alignment.character_end_times_seconds[endIndex];
  if (!Number.isFinite(end)) throw new Error(`Falta el tiempo final de ${scene.id}.`);
  sceneTimings.push({id: scene.id, label: scene.label, start, end, text: scene.text});
  cursor = endIndex + 3; // two newline characters between scenes
}

const captions = [];
for (const scene of sceneTimings) {
  const words = scene.text.match(/\S+/g) ?? [];
  let chunk = [];
  let searchAt = text.indexOf(scene.text);
  let chunkStartIndex = searchAt;
  for (const word of words) {
    const wordIndex = text.indexOf(word, searchAt);
    if (wordIndex < 0) throw new Error('No se pudo alinear una palabra del guion.');
    if (chunk.length === 0) chunkStartIndex = wordIndex;
    chunk.push(word);
    searchAt = wordIndex + word.length;
    if (chunk.length >= 10 || /[.!?]$/.test(word)) {
      captions.push({
        start: alignment.character_start_times_seconds[chunkStartIndex],
        end: alignment.character_end_times_seconds[searchAt - 1],
        text: chunk.join(' '),
      });
      chunk = [];
    }
  }
  if (chunk.length) captions.push({
    start: alignment.character_start_times_seconds[chunkStartIndex],
    end: alignment.character_end_times_seconds[searchAt - 1],
    text: chunk.join(' '),
  });
}

const srtTime = (seconds) => {
  const millis = Math.max(0, Math.round(seconds * 1000));
  const hh = String(Math.floor(millis / 3600000)).padStart(2, '0');
  const mm = String(Math.floor(millis / 60000) % 60).padStart(2, '0');
  const ss = String(Math.floor(millis / 1000) % 60).padStart(2, '0');
  const ms = String(millis % 1000).padStart(3, '0');
  return `${hh}:${mm}:${ss},${ms}`;
};
const srt = captions.map((item, index) => `${index + 1}\n${srtTime(item.start)} --> ${srtTime(item.end)}\n${item.text}\n`).join('\n');
await mkdir(path.join(root, 'public', 'voice-v2'), {recursive: true});
await writeFile(path.join(root, 'public', 'voice-v2', 'narration.mp3'), Buffer.from(result.audio_base64, 'base64'));
await writeFile(path.join(root, 'src', 'timing-v2.json'), JSON.stringify({ready: true, scenes: sceneTimings, captions}, null, 2));
await writeFile(path.join(root, 'subtitles-v2.srt'), srt);
console.log(`Voz generada con cuota gratuita: ${estimatedCredits} caracteres, ${captions.length} subtítulos.`);
