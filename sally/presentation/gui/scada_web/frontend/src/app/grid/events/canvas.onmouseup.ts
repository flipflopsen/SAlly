import State from "../state";

export default function(state: State, evt: MouseEvent) {
  state.mouseDown = false;
  if (state.clickedBtn) {
    // is handled by button handlers
    state.clickedBtn = false; //reset for next click
  } else {

    // user does not want to drag any element anymore
    state.dragsElement = false;
    state.clickedElement = null;
  }
}
