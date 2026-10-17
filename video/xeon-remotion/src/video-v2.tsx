import type {ReactNode} from 'react';
import {AbsoluteFill, Audio, Img, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import timing from './timing-v2.json';
import './xeon.css';
import './v2.css';

const fps = 30;
const scenes = timing.scenes;
const captions: Array<{start: number; end: number; text: string}> = timing.captions;
const last = scenes[scenes.length - 1];
export const durationV2 = Math.ceil((last.end + 2) * fps);
const fade = (frame: number, start: number, length = 20) =>
  interpolate(frame, [start, start + length], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
const float = (frame: number, start: number) => ({
  opacity: fade(frame, start),
  transform: `translateY(${(1 - fade(frame, start)) * 48}px)`,
});

const Shell = ({children, number, chapter, note}: {
  children: ReactNode; number: string; chapter: string; note: string;
}) => {
  const frame = useCurrentFrame();
  return <AbsoluteFill className="v2-scene">
    <div className="v2-glow" style={{transform: `translateX(${frame * 0.07}px)`}} />
    <div className="v2-grid" />
    <div className="brand-row"><div className="brand-mark"><span className="brand-spark">✦</span> XEON <span className="brand-sub">/ DEMO</span></div><div className="brand-chapter">PROTOTIPO COMERCIAL <span>// {chapter}</span></div></div>
    {children}
    <div className="scene-meta"><span>{number} / 06</span><span>{note}</span></div>
  </AbsoluteFill>;
};

const Title = ({eyebrow, children}: {eyebrow: string; children: ReactNode}) =>
  <div className="v2-title"><div className="eyebrow">{eyebrow}</div><h2>{children}</h2></div>;

const Intro = () => {
  const frame = useCurrentFrame();
  return <Shell number="01" chapter="INICIO" note="DEMO LOCAL · DATOS SINTÉTICOS">
    <div className="v2-intro-copy" style={float(frame, 10)}><div className="eyebrow">XEON · ASISTENTE COMERCIAL</div><h1>CONSULTA.<br /><span>COMPRUEBA.</span><br />COTIZA.</h1><p>Una demostración funcional para ferreterías.<br />Sin inventario ni clientes reales.</p></div>
    <div className="v2-intro-bot" style={{opacity: fade(frame, 18, 30), transform: `scale(${0.8 + fade(frame, 18, 30) * 0.2})`}}><div className="v2-halo" /><Img src={staticFile('images/xeon.png')} /></div>
    <div className="v2-small-label">01 / UNA CONSULTA SE CONVIERTE EN UN BORRADOR VERIFICABLE</div>
  </Shell>;
};

const WhatsApp = () => {
  const frame = useCurrentFrame();
  return <Shell number="02" chapter="WHATSAPP" note="WEBHOOK SIMULADO · SIN ENVÍO A TELÉFONO REAL">
    <div style={float(frame, 5)}><Title eyebrow="01 / ENTRADA POR EL CANAL"><>EL CLIENTE<br /><span>ESCRIBE.</span></></Title></div>
    <div className="v2-phone" style={float(frame, 22)}>
      <div className="v2-phone-top"><span>‹</span><div className="v2-avatar">X</div><div><strong>XEON Cotizador</strong><small>Escenario local de prueba</small></div><span>⋮</span></div>
      <div className="v2-phone-body"><div className="v2-date">HOY · DEMOSTRACIÓN</div><div className="v2-message" style={float(frame, 44)}>/xeon necesito 2 bultos de cemento <small>SIMULADO</small></div><div className="v2-bubble" style={float(frame, 90)}>Consulta procesada. Producto candidato: <b>CEM-50</b>. Borrador de prueba: <b>57.800 COP</b>.<small>RESUMEN VISUAL DE LA RESPUESTA</small></div></div>
    </div>
    <div className="v2-flow" style={float(frame, 70)}><div>01 <b>Mensaje</b></div><i>→</i><div>02 <b>Evolution API</b></div><i>→</i><div>03 <b>Webhook XEON</b></div></div>
    <div className="v2-proof" style={float(frame, 115)}>PRUEBA ACTUAL: <b>LOCAL_ONLY</b> <span>·</span> mensaje real no enviado</div>
  </Shell>;
};

const Product = () => {
  const frame = useCurrentFrame();
  return <Shell number="03" chapter="PRODUCTO" note="CATÁLOGO SINTÉTICO · BÚSQUEDA LOCAL POR PALABRAS">
    <div style={float(frame, 5)}><Title eyebrow="02 / IDENTIFICAR SIN INVENTAR"><>DE LA FRASE<br /><span>AL SKU.</span></></Title></div>
    <div className="v2-query" style={float(frame, 23)}><span>CONSULTA</span>“2 bultos de cemento”</div>
    <div className="v2-search-arrow" style={float(frame, 45)}>↓</div>
    <div className="v2-product-card" style={float(frame, 58)}><div className="v2-product-top"><span>CATÁLOGO DE PRUEBA</span><span>SKU CANDIDATO</span></div><h3>CEM-50</h3><p>Cemento gris · presentación de 50 kg</p><div className="v2-chips"><span>SKU</span><span>Alias</span><span>Atributos</span><span>Descripción</span></div></div>
    <div className="v2-caution" style={float(frame, 115)}>Si hay ambigüedad, la referencia debe aclararse antes de cerrar la venta.</div>
  </Shell>;
};

const Inventory = () => {
  const frame = useCurrentFrame();
  const cards = [
    {kind:'LOCAL / NORTE',number:'20',title:'EN LA SEDE',detail:'Existencia local del escenario.',accent:'cyan'},
    {kind:'TRASLADO / CENTRO',number:'80',title:'OTRA SEDE',detail:'No cuenta como stock local.',accent:'blue'},
    {kind:'ENTREGA',number:'40',title:'OTRO CANAL',detail:'No es existencia física en Norte.',accent:'teal'},
  ];
  return <Shell number="04" chapter="INVENTARIO" note="SNAPSHOT SINTÉTICO · 08 OCT 2026, 15:00 UTC">
    <div style={float(frame, 4)}><Title eyebrow="03 / DISPONIBILIDAD POR ORIGEN"><>NO TODO ESTÁ<br /><span>EN TU SEDE.</span></></Title></div>
    <div className="v2-order" style={float(frame, 22)}>PEDIDO: <b>50 BULTOS</b> <span>·</span> SEDE SOLICITADA: <b>NORTE</b></div>
    <div className="v2-stock-cards">{cards.map((card,i)=><div key={card.kind} className={`v2-stock ${card.accent}`} style={float(frame, 38+i*17)}><span>{card.kind}</span><div>{card.number}<small> BULTOS</small></div><strong>{card.title}</strong><p>{card.detail}</p></div>)}</div>
    <div className="v2-caution" style={float(frame, 118)}>Origen y fecha visibles. Este inventario no representa disponibilidad actual.</div>
  </Shell>;
};

const Quote = () => {
  const frame = useCurrentFrame();
  const amount = Math.round(57800 * fade(frame, 100, 55)).toLocaleString('es-CO');
  return <Shell number="05" chapter="BORRADOR" note="DRAFT V1 · SIN APROBACIÓN NI RESERVA">
    <div style={float(frame, 5)}><Title eyebrow="04 / CÁLCULO DEL BACKEND"><>CÁLCULO<br /><span>EXACTO.</span></></Title></div>
    <div className="v2-quote" style={float(frame, 24)}><div className="v2-quote-head"><span>BORRADOR COMERCIAL</span><span>VERSIÓN 01</span></div><div className="v2-quote-line"><span>CEM-50 · CEMENTO GRIS</span><b>2 BULTOS</b></div><div className="v2-quote-math">2 × 28.900 COP</div><div className="v2-quote-total"><span>TOTAL CALCULADO</span><div>{amount} <small>COP</small></div></div><div className="v2-draft">DRAFT</div></div>
    <div className="v2-quote-note" style={float(frame, 143)}>La IA interpreta la solicitud.<br /><b>El backend calcula con Decimal.</b></div>
  </Shell>;
};

const Closing = () => {
  const frame = useCurrentFrame();
  return <Shell number="06" chapter="ALCANCE" note="DEMO NO COMERCIAL · VOZ: ELEVENLABS.IO">
    <div style={float(frame, 5)}><Title eyebrow="05 / UNA DEMO HONESTA"><>PREPARA EL TRABAJO.<br /><span>NO CIERRA LA VENTA.</span></></Title></div>
    <div className="v2-close-grid"><div style={float(frame, 31)}><span>FUNCIONA EN PRUEBA</span><p>Webhook de WhatsApp</p><p>Identificación de candidatos</p><p>Stock por sede y origen</p><p>Borrador calculado</p></div><div style={float(frame, 48)}><span>AÚN POR VALIDAR / IMPLEMENTAR</span><p>Entrega a teléfono vinculado</p><p>Base de datos comercial</p><p>Aprobación y PDF</p><p>Inventario real</p></div></div>
    <div className="v2-ending" style={float(frame, 125)}><Img src={staticFile('images/xeon.png')} /><div><strong>XEON</strong><p>La IA prepara. Tu equipo decide.</p></div></div>
  </Shell>;
};

const components = [Intro, WhatsApp, Product, Inventory, Quote, Closing];

const Captions = () => {
  const frame = useCurrentFrame();
  const caption = captions.find((item) => frame >= item.start * fps && frame < item.end * fps);
  if (!caption) return null;
  const p = fade(frame, Math.floor(caption.start * fps), 6);
  return <div className="subtitle-rail" style={{opacity:p}}><div>{caption.text}</div></div>;
};

export const XeonDemoV2 = () => {
  const frame = useCurrentFrame();
  return <AbsoluteFill className="composition">
    {scenes.map((scene, index) => {
      const from = Math.floor(scene.start * fps);
      const next = scenes[index+1];
      const to = next ? Math.floor(next.start * fps) : durationV2;
      const Component = components[index];
      return <Sequence key={scene.id} from={from} durationInFrames={to-from} name={`${index+1} · ${scene.label}`}><Component /></Sequence>;
    })}
    {timing.ready ? <Audio src={staticFile('voice-v2/narration.mp3')} /> : null}
    {!timing.ready ? <div className="v2-pending">VISTA PREVIA · VOZ ELEVENLABS PENDIENTE</div> : null}
    <Captions />
    <div className="progress-track"><div style={{width:`${frame/durationV2*100}%`}} /></div>
  </AbsoluteFill>;
};
