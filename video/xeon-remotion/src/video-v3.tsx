import type {CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame} from 'remotion';
import timing from './timing-v3.json';
import './v3.css';

const fps = 30;
const scenes = timing.scenes;
const duration = Math.ceil(timing.duration * fps);
export const durationV3 = duration;

const ease = Easing.out(Easing.cubic);
const reveal = (frame: number, at = 0, distance = 56): CSSProperties => {
  const progress = interpolate(frame, [at, at + 21], [0, 1], {
    easing: ease,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return {opacity: progress, transform: `translate3d(0, ${(1 - progress) * distance}px, 0)`};
};
const pop = (frame: number, at = 0): CSSProperties => {
  const progress = spring({frame: Math.max(0, frame - at), fps, config: {damping: 18, stiffness: 115, mass: 0.8}});
  return {opacity: Math.min(1, progress * 2), transform: `scale(${0.9 + progress * 0.1})`};
};

const Scene = ({chapter, number, note, children, human = false}: {
  chapter: string; number: string; note: string; children: ReactNode; human?: boolean;
}) => {
  const frame = useCurrentFrame();
  return <AbsoluteFill className={`film-scene${human ? ' film-human' : ''}`}>
    <div className="film-noise" />
    <div className="film-beam" style={{transform: `translateX(${frame * 0.6}px)`}} />
    <div className="film-rule-grid" />
    <header className="film-header"><div className="film-logo"><span>✦</span> XEON <small>/ DEMO</small></div><div className="film-chapter">{chapter}</div></header>
    {children}
    <footer className="film-footer"><span>{number} / 07</span><span>{note}</span></footer>
  </AbsoluteFill>;
};

const WordStack = ({lines, frame, start = 0}: {lines: Array<{text: string; accent?: boolean}>; frame: number; start?: number}) =>
  <div className="word-stack">{lines.map((line, index) =>
    <div key={line.text} className={line.accent ? 'accent' : ''} style={reveal(frame, start + index * 10, 100)}>{line.text}</div>
  )}</div>;

const Opening = () => {
  const frame = useCurrentFrame();
  const orbit = frame * 0.16;
  return <Scene chapter="ASISTENCIA COMERCIAL" number="01" note="ESCENARIO LOCAL · DATOS SINTÉTICOS">
    <div className="opening-left">
      <div className="section-kicker" style={reveal(frame, 5)}>DE LA CONSULTA AL CONTEXTO</div>
      <WordStack frame={frame} start={10} lines={[{text: 'PREGUNTA.'}, {text: 'VERIFICA.', accent: true}, {text: 'CONECTA.'}]} />
      <p style={reveal(frame, 46)}>Una cotización comienza con información clara.<br />La conversación la continúa una persona.</p>
    </div>
    <div className="opening-orbit" style={pop(frame, 17)}>
      <div className="orbit-ring ring-one" style={{transform: `rotate(${orbit}deg)`}} />
      <div className="orbit-ring ring-two" style={{transform: `rotate(${-orbit * 0.65}deg)`}} />
      <Img src={staticFile('images/xeon.png')} />
      <div className="orbit-tag orbit-tag-a">01 / CONSULTA</div>
      <div className="orbit-tag orbit-tag-b">02 / CÓDIGO SKU</div>
      <div className="orbit-tag orbit-tag-c">03 / ASESOR</div>
    </div>
  </Scene>;
};

const WhatsApp = () => {
  const frame = useCurrentFrame();
  return <Scene chapter="ENTRADA / WHATSAPP" number="02" note="WEBHOOK SIMULADO · SIN TELÉFONO VINCULADO">
    <div className="scene-heading" style={reveal(frame, 6)}><span>01 / CONSULTA</span><h2>UNA FRASE<br /><em>EN MOVIMIENTO.</em></h2></div>
    <div className="phone-frame" style={reveal(frame, 17, 88)}>
      <div className="phone-header"><div className="phone-avatar">X</div><div><strong>XEON</strong><small>Escenario de prueba</small></div><span>⋮</span></div>
      <div className="phone-body">
        <div className="phone-date">CONVERSACIÓN SIMULADA</div>
        <div className="phone-message" style={reveal(frame, 36, 32)}>Necesito 2 bultos de cemento</div>
        <div className="phone-reply" style={reveal(frame, 71, 32)}><small>RESPUESTA DE PRUEBA</small><p>Referencia candidata: <b>CEM-50</b><br />Borrador: <b>57.800 COP</b></p></div>
      </div>
    </div>
    <div className="signal-path" style={reveal(frame, 42)}><span>MENSAJE</span><i /> <span>EVOLUTION API</span><i /> <span>XEON</span></div>
    <div className="proof-label" style={reveal(frame, 95)}>PRUEBA LOCAL <b>LOCAL_ONLY</b> · NO SE ENVIÓ AL TELÉFONO</div>
  </Scene>;
};

const Product = () => {
  const frame = useCurrentFrame();
  const scan = interpolate(frame, [42, 86], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <Scene chapter="IDENTIFICACIÓN / CATÁLOGO" number="03" note="SKU CANDIDATO · REQUIERE ACLARACIÓN SI HAY AMBIGÜEDAD">
    <div className="scene-heading" style={reveal(frame, 5)}><span>02 / PRODUCTO</span><h2>DEL LENGUAJE<br /><em>AL CÓDIGO.</em></h2></div>
    <div className="query-ticket" style={reveal(frame, 20)}><small>CONSULTA DEL COMPRADOR</small><strong>“2 bultos de cemento”</strong><div className="query-tail" /></div>
    <div className="sku-dossier" style={reveal(frame, 31, 90)}>
      <div className="sku-dossier-top"><span>FICHA DE REFERENCIA</span><span>CANDIDATO / NO CONFIRMADO</span></div>
      <div className="sku-main"><small>CÓDIGO DE PRODUCTO / SKU</small><strong>CEM-50</strong><div className="barcode" /></div>
      <div className="sku-scan" style={{transform: `translateX(${scan * 925}px)`, opacity: scan < 1 ? 0.85 : 0}} />
      <div className="sku-description"><span>01</span><p>Cemento gris · presentación de 50 kg</p></div>
      <div className="sku-meta"><span>ALIAS</span><span>ATRIBUTOS</span><span>DESCRIPCIÓN</span></div>
    </div>
    <div className="scene-clarity" style={reveal(frame, 92)}>EL ASESOR RECIBE UNA REFERENCIA LOCALIZABLE, NO UNA SUPOSICIÓN.</div>
  </Scene>;
};

const Inventory = () => {
  const frame = useCurrentFrame();
  const stocks = [
    {number: '20', label: 'NORTE', kind: 'LOCAL', detail: 'En la sede solicitada', color: 'cyan'},
    {number: '80', label: 'CENTRO', kind: 'TRASLADO', detail: 'Otra sede', color: 'blue'},
    {number: '40', label: 'ENTREGA', kind: 'OTRO ORIGEN', detail: 'No es stock local', color: 'mint'},
  ];
  return <Scene chapter="INVENTARIO / PROCEDENCIA" number="04" note="SNAPSHOT SINTÉTICO · 08 OCT 2026, 15:00 UTC">
    <div className="scene-heading" style={reveal(frame, 5)}><span>03 / DISPONIBILIDAD</span><h2>NO TODO ESTÁ<br /><em>EN TU SEDE.</em></h2></div>
    <div className="inventory-order" style={reveal(frame, 16)}>PEDIDO <b>50 BULTOS</b><span> / </span> SEDE NORTE</div>
    <div className="inventory-rail"><div className="rail-line" style={{transform: `scaleX(${interpolate(frame, [25, 84], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})})`}} />
      {stocks.map((stock, index) => <div key={stock.label} className={`stock-station ${stock.color}`} style={reveal(frame, 32 + index * 16)}>
        <div className="stock-node" /><small>{stock.kind}</small><strong>{stock.number}</strong><div>{stock.label}</div><p>{stock.detail}</p>
      </div>)}
    </div>
    <div className="scene-clarity" style={reveal(frame, 87)}>CADA DATO CONSERVA ORIGEN Y FECHA. NO PROMETEMOS STOCK VENCIDO.</div>
  </Scene>;
};

const Quote = () => {
  const frame = useCurrentFrame();
  const count = interpolate(frame, [105, 149], [0, 57800], {easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <Scene chapter="CÁLCULO / BORRADOR" number="05" note="DRAFT V1 · SIN APROBACIÓN NI RESERVA">
    <div className="scene-heading" style={reveal(frame, 5)}><span>04 / COTIZACIÓN</span><h2>EL NÚMERO<br /><em>TIENE ORIGEN.</em></h2></div>
    <div className="quote-paper" style={reveal(frame, 24, 80)}>
      <div className="paper-top"><span>XEON / BORRADOR COMERCIAL</span><span>VERSIÓN 01</span></div>
      <div className="paper-product"><div><small>CÓDIGO / SKU</small><strong>CEM-50</strong></div><div><small>PRODUCTO</small><strong>CEMENTO GRIS</strong></div><div><small>CANTIDAD</small><strong>02 BULTOS</strong></div></div>
      <div className="paper-calculation"><span>2 × 28.900 COP</span><span>CALCULADO POR EL BACKEND</span></div>
      <div className="paper-total" style={pop(frame, 86)}><small>TOTAL DEL BORRADOR</small><strong>{frame < 105 ? '—' : Math.round(count).toLocaleString('es-CO')}<em> COP</em></strong></div>
      <div className="paper-stamp" style={pop(frame, 152)}>DRAFT</div>
    </div>
    <div className="quote-note" style={reveal(frame, 61)}>La IA interpreta.<br /><b>El backend calcula con Decimal.</b></div>
  </Scene>;
};

const Advisor = () => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [55, 110], [0, 1], {easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <Scene chapter="DIFERENCIAL / CONTACTO HUMANO" number="06" note="OBJETIVO DEL PRODUCTO · TRASPASO AUTOMÁTICO PENDIENTE" human>
    <div className="advisor-heading" style={reveal(frame, 5)}><span>05 / EL SIGUIENTE PASO</span><h2>DE LA IA<br /><em>AL ASESOR REAL.</em></h2><p>La información llega ordenada.<br />La decisión se conversa con una persona.</p></div>
    <div className="handoff-bundle" style={reveal(frame, 25)}><small>CONTEXTO PREPARADO</small><div><span>01</span><b>CÓDIGO / SKU</b><strong>CEM-50</strong></div><div><span>02</span><b>DISPONIBILIDAD</b><strong>POR SEDE</strong></div><div><span>03</span><b>COTIZACIÓN</b><strong>DRAFT V1</strong></div></div>
    <svg className="handoff-line" viewBox="0 0 300 120" aria-hidden="true"><path d="M 8 60 C 110 60, 130 60, 278 60" stroke="#efbb89" strokeWidth="4" fill="none" strokeDasharray="320" strokeDashoffset={320 * (1 - progress)} /><circle cx={8 + 270 * progress} cy="60" r="10" fill="#efbb89" opacity={progress} /></svg>
    <div className="advisor-profile" style={pop(frame, 72)}><div className="advisor-avatar">AR</div><small>CONTACTO HUMANO</small><strong>ASESOR<br />REAL</strong><span>CONTINÚA CON CONTEXTO</span></div>
    <div className="advisor-status" style={reveal(frame, 112)}>VISIÓN DEL PRODUCTO <b>· CONEXIÓN AUTOMÁTICA POR IMPLEMENTAR</b></div>
  </Scene>;
};

const Closing = () => {
  const frame = useCurrentFrame();
  return <Scene chapter="CIERRE / PROPUESTA" number="07" note="DEMO LOCAL · SIN VENTA NI ENTREGA AUTOMÁTICA" human>
    <div className="closing-center">
      <div className="section-kicker" style={reveal(frame, 6)}>XEON / UNA COTIZACIÓN CON CONTEXTO</div>
      <WordStack frame={frame} start={15} lines={[{text: 'TU CONSULTA'}, {text: 'TIENE UN', accent: true}, {text: 'SIGUIENTE PASO.'}]} />
      <div className="closing-cta" style={pop(frame, 61)}>HABLAR CON UN ASESOR REAL <span>↗</span></div>
      <p style={reveal(frame, 80)}>La IA prepara la referencia, el stock y el borrador.<br />La persona te ayuda a decidir.</p>
    </div>
    <div className="closing-limit" style={reveal(frame, 112)}>HOY: DEMO SINTÉTICA <span>·</span> PRÓXIMO: CONTACTO HUMANO INTEGRADO <span>·</span> BASE COMERCIAL Y PDF PENDIENTES</div>
  </Scene>;
};

const components = [Opening, WhatsApp, Product, Inventory, Quote, Advisor, Closing];

const Captions = () => {
  const frame = useCurrentFrame();
  const item = timing.captions.find((caption) => frame >= Math.round(caption.start * fps) && frame < Math.round(caption.end * fps));
  if (!item) return null;
  const alpha = interpolate(frame, [item.start * fps, item.start * fps + 5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <div className="film-captions" style={{opacity: alpha}}>{item.text}</div>;
};

const TransitionWipes = () => {
  const frame = useCurrentFrame();
  const scene = scenes.slice(1).find((item) => Math.abs(frame - item.start * fps) < 15);
  if (!scene) return null;
  const local = frame - scene.start * fps;
  const travel = interpolate(local, [-15, 0, 15], [-2300, 0, 2300], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <div className="film-wipe" style={{transform: `translateX(${travel}px) skewX(-18deg)`}} />;
};

export const XeonDemo = () => {
  const frame = useCurrentFrame();
  return <AbsoluteFill className="film-root">
    {scenes.map((scene, index) => {
      const Component = components[index];
      const from = Math.round(scene.start * fps);
      const to = Math.round(scene.end * fps);
      return <Sequence key={scene.id} from={from} durationInFrames={to - from} name={`${index + 1} · ${scene.label}`}><Component /></Sequence>;
    })}
    <Sequence from={14}><Audio src={staticFile('voice-elevenlabs/narration.mp3')} volume={1} /></Sequence>
    <Audio src={staticFile('sound/soundscape.mp3')} volume={0.72} />
    <TransitionWipes />
    <Captions />
    <div className="film-progress"><div style={{transform: `scaleX(${frame / duration})`}} /></div>
  </AbsoluteFill>;
};
