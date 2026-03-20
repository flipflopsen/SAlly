import State from "../state";
import exitEditMode from "../functions/exit-editmode";
import enterEditMode from "../functions/enter-editmode";

import * as SETTINGS from "../settings";

export default function onKeyUp(state: State, evt: KeyboardEvent) {

  if((evt.key == "s") && (state.keyS == true)) {
    state.keyS = false;
    if(state.editMode) state.saveGridEvent = true;
  }

  if((evt.key == "e") && (state.keyE == true)) {
    state.keyE = false;
    // toggle editmode
    if(state.editMode == true) {
      exitEditMode(state);

    } else {
      enterEditMode(state);
    }
    state.valueChange = true;
  }
}
