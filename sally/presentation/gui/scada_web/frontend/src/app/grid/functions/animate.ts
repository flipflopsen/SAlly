import loadFrame from "./load-frame";
import saveGrid from "./save-grid";
import State from "../state";

import * as SETTINGS from "../settings";
import { LayoutService } from "../layout.service";

export default function animate(state: State, layoutService: LayoutService) {
  state.animationId = requestAnimationFrame(() => animate(state, layoutService));
  if (state.userChange || state.valueChange || state.scalingChange) {

    if (state.valueChange) {
      console.log("loaded frame " + state.currentFrame);
      loadFrame(state, state.currentFrame);      
    }
    
    if (state.userChange || state.valueChange) { // dbase values influence what is shown --> need to update screen  
      // update BUFFERcanvas - if there is just a scaling change, no need to redraw BUFFERCanvas. Just what is shown on canvas of bufferCanvas needs to change
      state.bufferContext.globalAlpha = 1;
      // clear canvas
      state.bufferContext.fillStyle = SETTINGS.BACKGROUNDCOLOR;	// draw a rectangle to erase whole screen
      state.bufferContext.fillRect(0, 0, state.bufferContext.canvas.width, state.bufferContext.canvas.height)
      // state.bufferContext.fillRect(0, 0, state.bufferCanvas.width, state.bufferCanvas.height); // applies re-scaled canvas

      // do all the drawing: first draw wires, so that everything else can be drawn on top of them
      state.cablesArray.forEach(cable => {
        cable.draw();
      });      
      state.electricComponentsArray.forEach(drawable => {
        drawable.draw();
      });
      // draw text on top of everything
      state.cablesArray.forEach(cable => {
        cable.textBoxDraw();
      });
      state.electricComponentsArray.forEach(drawable => {
        drawable.textBoxDraw();
      });
    }

    // clear visible canvas
    state.context.fillStyle = SETTINGS.BACKGROUNDCOLOR;	// draw a rectangle to erase whole screen
    state.context.fillRect(0, 0, state.context.canvas.width, state.context.canvas.height)
    // update the normal canvas to understand the following line see
    // https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/drawImage
    state.context.drawImage(state.bufferCanvas, state.marginLeft, state.marginTop,
      state.bufferCanvas.width / state.scaleWindowWidth,
      state.bufferCanvas.height / state.scaleWindowHeight,
      0, 0, state.canvas.width, state.canvas.height
    );
    // signal that the update is done
    state.userChange = false;
    state.scalingChange = false;
    state.valueChange = false;
  }

  if (state.editMode){
    // write in a corner of the current canvas that your are in editmode
    // and also stroke a rectangle around the image
    let tolerance:number  = Math.ceil(0.01*state.canvas.width);
    state.context.lineWidth = tolerance;
    state.context.strokeStyle = "red";
    state.context.strokeRect(0, 0, state.canvas.width, state.canvas.height, );
    state.context.globalAlpha = SETTINGS.SELECTOPACITY;
    state.context.font = SETTINGS.EDITMODETEXT.font;
    state.context.fillStyle = SETTINGS.EDITMODETEXT.fillStyle;
    state.context.textAlign = "right";
    state.context.fillText("EDITMODE", state.canvas.width - tolerance, SETTINGS.EDITMODETEXT.fontSize + tolerance);
    state.context.textAlign = "start"; // set textAlign back to default
  }

  if (state.saveGridEvent) {
    console.log("Received save-grid command");
    // draw the canvas white like when taking a screenshot
    state.context.fillStyle = "white";
    state.context.fillRect(0, 0, state.bufferCanvas.width, state.bufferCanvas.height);
    state.context.drawImage(state.canvas, 0, 0);
    setTimeout(() => saveGrid(state, layoutService), 10);
    // clear the event so that this block is not triggered again
    state.saveGridEvent = false;
  }
}
