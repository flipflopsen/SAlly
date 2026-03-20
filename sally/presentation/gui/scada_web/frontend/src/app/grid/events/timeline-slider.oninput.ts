import State from "../state";

export default function(state: State) {
  // minimum value for slider is 1, for dbase its 0 --> need to adjust
  state.currentFrame = (state.timelineSlider.value as unknown as number) - 1;
  state.valueChange = true;
}
