import {Composition} from 'remotion';
import {XeonDemo, durationV3} from './video-v3';

export const Root = () => <>
  <Composition id="XeonDemo" component={XeonDemo} defaultProps={{
    hookLead: 'UNA CONSULTA',
    hookEmphasis: 'NO DEBERÍA',
    hookResolve: 'PERDERSE.',
    exampleMessage: 'Necesito 2 bultos\nde cemento',
    solutionLead: 'DATOS',
    solutionEmphasis: 'CLAROS.',
    solutionResolve: 'ASESOR REAL.',
  }} durationInFrames={durationV3} fps={30} width={1920} height={1080} />
</>;
