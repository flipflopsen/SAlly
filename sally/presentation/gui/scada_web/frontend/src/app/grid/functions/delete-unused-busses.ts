import State from "../state";
import * as SETTINGS from "../settings";

export default function deleteUnusedBusses(state: State) {
// delete unused busses
  for (const [cim_key, bus] of Object.entries(state.busDict)) {
    if (!bus.hasParent) {
      if(SETTINGS.SHOWDEBUGGINGINFO){   
        console.log("Bus ID CIM " + bus.cim_id + " other ID: " + bus.id + " with the descriptor <" + bus.descriptor + "> not connected to grid, thus removing it");
      }
      // delete it from the array, so that it is not drawn on screen
      let j = 0;
      for (j; j < state.electricComponentsArray.length; j++) {
        if (state.electricComponentsArray[j].cim_id == cim_key) {
          break;
        }
      }
      state.electricComponentsArray.splice(j, 1);
      // also delete it from the dict, so that it is not checked for
      delete state.busDict[cim_key];
    }
  }
}