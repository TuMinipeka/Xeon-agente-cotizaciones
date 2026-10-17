import {Composition} from 'remotion';
import {XeonDemo, durationV3} from './video-v3';

export const Root = () => <>
  <Composition id="XeonDemo" component={XeonDemo} durationInFrames={durationV3} fps={30} width={1920} height={1080} />
</>;
