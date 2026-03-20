import State from "../state";
import StructuredElement from "../classes/structured-element";
import checkHitBoxes from "../functions/check-hit-boxes";
import translatePos from "../functions/translate-pos";

import * as SETTINGS from "../settings";

export default function(state: State, evt: MouseEvent) {
  state.lastDraggingCoor.x = evt.clientX;
  state.lastDraggingCoor.y = evt.clientY;
  state.mouseDown = true;
  // unclick anything clicked
  state.clickedElementsArray.forEach(clickable => {
    clickable.unClickAction();
  });
  state.clickedElementsArray = [];

  // check if an element has been clicked on
  state.clickedElementsArray = checkHitBoxes(state, translatePos(state, state.lastDraggingCoor));

  if (state.clickedElementsArray.length > 0) {
    // only click one of the elements, with VisibleWires having the lowest priority
    // remember draw-order: we want to select the element on top, meaning the last in the list
    state.clickedElement = state.clickedElementsArray[state.clickedElementsArray.length - 1];

    if (SETTINGS.SHOWDEBUGGINGINFO){
      console.log("ID:", state.clickedElement.id);
    }
    
    if (state.editMode) {
      //dragging allows to move elements and that is only allowed in edit-mode
      state.dragsElement = true;
    }

    if (state.editMode || SETTINGS.CLICKONLYONE) {      
      state.clickedElement.clickAction();
    } else {
      state.clickedElementsArray.forEach(clickable => {
        clickable.clickAction();
      });
    }
    
    state.lastClickedElement = state.clickedElement as StructuredElement;
    state.openInfoboardBtn.innerHTML = "Toggle element in Grafana";
  } else {
    state.lastClickedElement = null;
    state.openInfoboardBtn.innerHTML = "Please select an element";
  }
  state.userChange = true;
}
