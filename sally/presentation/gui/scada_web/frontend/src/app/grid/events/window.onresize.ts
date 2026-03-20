import mouseMoveRelativeToCanvas
  from "../functions/mouse-move-relative-to-canvas";
import State from "../state";

import * as SETTINGS from "../settings";

export default function(state: State, evt: Event) {
  // only reset zoom because if user wants to work with a differently sized window he can better hit the reload button
  state.scaleWindowHeight = SETTINGS.MIN_ZOOM;
  state.scaleWindowWidth = SETTINGS.MIN_ZOOM; 
  state.scaleFactor = state.defaultScaleFactor;
  state.marginLeft = 0;
  state.marginTop = 0;

  mouseMoveRelativeToCanvas(state, evt as MouseEvent);
  state.scalingChange = true;

  console.log("reset margins because window got resized");
}
