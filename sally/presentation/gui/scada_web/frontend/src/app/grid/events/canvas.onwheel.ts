import mouseMoveRelativeToCanvas
  from "../functions/mouse-move-relative-to-canvas";
import State from "../state";

import * as SETTINGS from "../settings";


export default function (state: State, evt: WheelEvent) {
  // we only care for the direction of scrolling
  let deltaVal = SETTINGS.ZOOM_STEPS;
  if (evt.deltaY > 0) {
    deltaVal = -SETTINGS.ZOOM_STEPS;
  }

  let newScaleWindow = state.scaleWindowHeight + deltaVal;
  // clamp value
  newScaleWindow = Math.max(newScaleWindow, SETTINGS.MIN_ZOOM);
  newScaleWindow = Math.min(newScaleWindow, SETTINGS.MAX_ZOOM);

  if (newScaleWindow != state.scaleWindowHeight) {
    let heightChangeInPercent = newScaleWindow/state.scaleWindowHeight;
    state.scaleWindowHeight = newScaleWindow;
    // the change is percent is the same for height and width
    state.scaleWindowWidth = state.scaleWindowWidth * heightChangeInPercent;
    // compute the scaling-factor once for the new scaling for all elements to use    
    state.scaleFactor = state.scaleWindowHeight * (state.canvas.height / state.bufferCanvas.height);

    //condition: bufferCanvas.width/scaleWindow - marginLeft <= canvas.width
		let maxMarginTop = state.bufferCanvas.height * (1 - 1/state.scaleWindowHeight);
		let maxMarginLeft = state.bufferCanvas.width * (1 - 1/state.scaleWindowWidth);
		
		//if maximum margin is overstepped through scaling, reduce it back!
    state.marginTop = Math.min(state.marginTop, maxMarginTop);
    state.marginLeft = Math.min(state.marginLeft, maxMarginLeft);

    state.scalingChange = true;
    // trigger mouse-move event since the mouse moved *relativ* to the canvas
    mouseMoveRelativeToCanvas(state, evt);
  } else {
    console.log("Discarded zoom command: hit min or max value", newScaleWindow);
  }

  evt.preventDefault(); //IMPORTANT! Make sure that the scrollbar is not used, as that ruins the overlay of canvas and buffercanvas!
}
