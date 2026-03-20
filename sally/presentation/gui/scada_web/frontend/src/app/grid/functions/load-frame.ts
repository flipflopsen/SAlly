import State from "../state";

export default function loadFrame(state: State, frame_no: number) {
  state.selectedRecordText.innerHTML = "timestamp " + state.currentFrame;
  type possibleElementType = (keyof typeof state["elemTypeToArrayDict"]);
  type possibleUnit = (keyof typeof state["unitToAttributeDict"]);
  let dictToCheck: Record<string, any>;

  // this function needs to be modified once CIM-IDs are used in the dbase
  
  Object.keys(state.myDbase!).forEach(key => {
    let entry = state.myDbase![key][frame_no]; // form: {simulationtimestamp: somevalue}
    let elemValue = entry[Object.keys(entry)[0]]; // we only want "somevalue", thus need key "simulationtimestamp"
    let buffer = key.split(" "); // e.g. key = "bus 0 vm_pu" but some look like this: "sgen 9-33 p_mw"
    let elemType: string = buffer[0]; // e.g. "bus"
    let dictKey = elemType + " " + String(buffer[1].split("-")[0]); // e.g. "bus 0"
    let elemUnit = buffer[2]; // e.g. "vm_pu"
    if(elemType in state.elemTypeToArrayDict){  
      dictToCheck = state.elemTypeToArrayDict[elemType as possibleElementType];
      let elem = dictToCheck[dictKey];
      if(elemUnit in state.unitToAttributeDict){
        elem[state.unitToAttributeDict[elemUnit as possibleUnit]] = elemValue;
      } else {
        console.log("Element type " + elemType + "does not have the attribute " + elemUnit);
      }
    }
    else {
      console.log("Database key <" + key + "> does not correspond to an element on the canvas");
    }
  });

  // need to compute load for all generators and loads (because the Dbase does not provide the values)
  Object.values(state.generatorsDict).forEach(sgen => {
    if (sgen.maxApparentPower_va > 0){
      sgen.loading_percent = Math.sqrt(Math.pow(sgen.activePower_mw, 2) + Math.pow(sgen.reactivePower_var, 2)) / sgen.maxApparentPower_va;
    } else {
      sgen.loading_percent = 0;
    }
  });
  Object.values(state.loadDict).forEach(load => {
    if (load.maxApparentPower_va > 0){
      load.loading_percent = Math.sqrt(Math.pow(load.activePower_mw, 2) + Math.pow(load.reactivePower_var, 2)) / load.maxApparentPower_va;
    } else {
      load.loading_percent = 0;
    }
  });
  // no need to compute load for trafos and wires - the dbase provides the values
}
