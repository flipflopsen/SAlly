import StructuredElement from "../classes/structured-element";
import State from "../state";
import * as SETTINGS from "../settings";


export default function (state: State) {
  state.clickedBtn = true;

  if (state.lastClickedElement instanceof StructuredElement) {
    state.mouseDown = false;
    state.clickedElement = state.lastClickedElement;
    // communicate the ID of state.lastClickedElement to the Grafana Dashboard
    // state.clickedElement.cim_id example: "load 1", but Grafana expects "0-load-01"
    let buff = state.clickedElement.cim_id.split(" ");
    let type = buff[0];
    let num = buff[1]; // is a string
    if(num.length != 2){
      num = "0" + num; // must be 2-digit
    }
    let id = "0-" + type + "-" + num;

    if (SETTINGS.SHOWDEBUGGINGINFO) {
      console.log("asked Grafana to diplay element " + id);
    }

    state.grafanaControl.clickDropdownItem(id); // also de-selects the element if it was already selected
    state.grafanaControl.updateInfoboard();
  } else {
    state.openInfoboardBtn.innerHTML = "Please select an element";
  }
}
