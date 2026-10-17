import {Composition} from 'remotion';
import {XeonDemoV2, durationV2} from './video-v2';

export const Root = () => <>
  <Composition id="XeonDemoV2" component={XeonDemoV2} durationInFrames={durationV2} fps={30} width={1920} height={1080} />
</>;
