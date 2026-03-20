import checkHitBoxes from "./check-hit-boxes";
import translatePos from "./translate-pos";
import StructuredElement from "../classes/structured-element";
import Vector2D from "../classes/vector-2d";
import State from "../state";

import * as SETTINGS from "../settings";

export default function mouseMoveRelativeToCanvas(
  state: State,
  evt: MouseEvent
) {
  state.mousePos.x = evt.clientX;
  state.mousePos.y = evt.clientY;
  // compute where this mouse position is on buffercanvas
  state.translatedMousePos = translatePos(state, state.mousePos);
  if (SETTINGS.SHOWDEBUGGINGINFO) {
    console.log("mouse-coordinates:", evt.clientX, evt.clientY, "translated:", state.translatedMousePos, "scalefactor:", state.scaleFactor);
  }

  let delta = state.mousePos.minus(state.lastDraggingCoor);
  state.lastDraggingCoor = state.mousePos.copy();

  if ( state.mouseDown && (
      (Math.abs(delta.x) > SETTINGS.MINIMUMCHANGEFORDRAG) ||
      (Math.abs(delta.y) > SETTINGS.MINIMUMCHANGEFORDRAG) )
  ) {
    // user is dragging --> if he did not select any element before, he wants to move his view
    // else he wants to move the selected object

    if (state.dragsElement) {
      if (state.clickedElement instanceof StructuredElement) {
        let changeVector = new Vector2D(0, 0);
        // drag the element to your current mouse position but make sure it stays in-grid
        changeVector.x = Math.round((state.translatedMousePos.x - state.clickedElement.center.x) / (SETTINGS.GRIDSIZE)) * SETTINGS.GRIDSIZE;
        changeVector.y = Math.round((state.translatedMousePos.y - state.clickedElement.center.y) / (SETTINGS.GRIDSIZE)) * SETTINGS.GRIDSIZE;

        if ((changeVector.x != 0) || (changeVector.y != 0)) {
          // remember: posChange needs parameters in grid-size
          state.clickedElement.posChange(changeVector.mult(1 / SETTINGS.MINELEMENTDISTANCE));
          state.userChange = true;
        }
      }
    } else {
      delta = delta.mult(SETTINGS.DRAGGINGACCELERATION);
      // user wants to move his view but in the opposite direction to where he is dragging
      let bufferMarginTop = state.marginTop - delta.y;
      let bufferMarginLeft = state.marginLeft - delta.x;
      
      let bottomBorder = state.bufferCanvas.height * (1 - 1 / state.scaleWindowHeight);
      let rightBorder = state.bufferCanvas.width * ( 1 - 1 / state.scaleWindowWidth);
      // check if margin is within bounds
      bufferMarginTop = Math.max(bufferMarginTop, 0);
      bufferMarginTop = Math.min(bufferMarginTop, bottomBorder);
      bufferMarginLeft = Math.max(bufferMarginLeft, 0);
      bufferMarginLeft = Math.min(bufferMarginLeft, rightBorder);
      // apply new values
      state.marginTop = bufferMarginTop;
      state.marginLeft = bufferMarginLeft;

      state.scalingChange = true;
      if(SETTINGS.SHOWDEBUGGINGINFO){
        console.log("detected dragging. New margins: top: " + state.marginTop + ", left: " + state.marginLeft, state.canvas.width, state.canvas.height);
      }
    }
  }

  // "unhover" everything that is "hovered"
  if (state.hoverElementsArray.length > 0) {
    state.hoverElementsArray.forEach(elem => {elem.unHoverAction();});

    //reset hoverElementsArray
    state.hoverElementsArray = [];
    state.userChange = true;
  }

  // get hover-elements
  state.hoverElementsArray = checkHitBoxes(state, state.translatedMousePos);
  if (SETTINGS.SHOWDEBUGGINGINFO) {
    console.log("currently hover about", state.hoverElementsArray.length, "elements", state.hoverElementsArray);
  }

  // induce hover action if no element is clicked
  if ((state.hoverElementsArray.length > 0) && (state.clickedElementsArray.length == 0)) {
    // only hover the first
    if(SETTINGS.CLICKONLYONE){
      state.hoverElementsArray[0].hoverAction();
    } else {
      state.hoverElementsArray.forEach(elem => {elem.hoverAction();});
    }    
    state.userChange = true;
  }

}
