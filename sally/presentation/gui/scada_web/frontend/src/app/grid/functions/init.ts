import initElements from "./init-elements";
import convertDictKeysGrid from "./convert-dict-keys-grid";
import scaleElements from "./scale-elements";
import scaleLineThickness from "./scale-line-thickness";
import animate from "./animate";
import Bus from "../classes/bus";
import Switch from "../classes/switch";
import ExtGrid from "../classes/ext-grid";
import Generator from "../classes/generator";
import Load from "../classes/load";
import Trafo from "../classes/trafo";
import State from "../state";
import setConnections from "../functions/set-connections";
import loadSavedOffsets from "../functions/load-saved-offsets";
import sAAA from "../functions/s-aaa";
import deleteUnusedBusses from "../functions/delete-unused-busses";

import * as SETTINGS from "../settings";
import { LayoutService } from "../layout.service";

// starts everything. Asynchronous so that we do not start before the dbase-files are loaded
export default async function init(state: State, layoutService: LayoutService) {
  // load topology
  let layout = await layoutService.getLayout().then();
  let networkConfigFile;
  let isSaveFile = false;
  let networkJsonFileContent;

  if (layout.length == 0) {
    console.log("No saved layout found");
    let fetch_url = "/api/v0/grid-topology-no-cim";
    if (SETTINGS.USE_CIM_LAYOUT) {
      fetch_url = "/api/v0/grid-topology";
    }
    let topology = await fetch(fetch_url)
    networkJsonFileContent = await topology.json();
    networkConfigFile = JSON.parse(networkJsonFileContent);
  }
  else {
    isSaveFile = true;
    if(SETTINGS.SHOWDEBUGGINGINFO){   
      console.log("loading savefile");
    }
    networkJsonFileContent = JSON.parse(layout);
    networkConfigFile = networkJsonFileContent["NETWORKJSON"];
  }

  if(SETTINGS.SHOWDEBUGGINGINFO){   
    console.log(networkJsonFileContent);
    console.log(networkConfigFile);
  }

  state.networkConfigFile = networkConfigFile;

  // create all elements mentioned in networkConfigFile
  // need to create busses first because the other elements reference them
  initElements("busses", Bus, state.busDict, state);
  initElements("external_network_injections", ExtGrid, state.extGridDict, state);
  initElements("power_transformers", Trafo, state.trafoDict, state);
  initElements("energy_consumers", Load, state.loadDict, state);
  initElements("energy_sources", Generator, state.generatorsDict, state);
  initElements("switches", Switch, state.switchDict, state);

  // get Child-Parent relationships
  setConnections(state);
  // get rid of left-overs
  deleteUnusedBusses(state);

  let allDicts = [state.busDict, state.loadDict, state.trafoDict, state.extGridDict, state.generatorsDict, state.switchDict];

  // everything is connected to its bus-node, now we need to arange these nodes
  if (isSaveFile) {
    loadSavedOffsets(state, networkJsonFileContent, allDicts);
    console.log("Restored grid-arrangement from savefile");
  } else {
    sAAA(state, allDicts);    
  }

  // load dbase
  let response = await fetch("/api/v0/initial-grid-data");
  let myDbaseFileContent = await response.json();
  state.myDbase = convertDictKeysGrid(myDbaseFileContent);

  if(SETTINGS.SHOWDEBUGGINGINFO){   
    console.log(state.networkConfigFile!);
    console.log(myDbaseFileContent);
    console.log("Converted DB", state.myDbase);
  }

  if(!SETTINGS.BE_STATIC){
    // adjust timelineslider according to number of dbase entries
    let firstkey = Object.keys(state.myDbase!)[0];
    if (firstkey != null){
      let dBaseFirstEntry = state.myDbase![firstkey];
      let timelineLenght = Object.keys(dBaseFirstEntry).length;
      state.timelineSlider.setAttribute("max", String(timelineLenght));
    }
  } else {
    state.timelineSlider.disabled = true;
    state.timelineDiv.hidden = true;
  }
  
  if (SETTINGS.AUTOSCALEELEMENTS) {
    // scale loads & generators according to what the grid can give them at most
    scaleElements(state.generatorsDict, "sn_mva");
    scaleElements(state.loadDict, "sn_mva");
    scaleElements(state.trafoDict, "sn_mva");
    // for lines we use maxApparentPower
    scaleLineThickness(state.cablesArray);
  }

  // //show features
  // extGridArray[1].hasAnomaly = true;
  // cablesArray[228].load = 200;
  // trafosArray[0].voltage = 0.8;
  // loadsArray[12].voltage = 1.5;
  // generatorsArray[8].load = 200;

  state.defaultScaleFactor = (state.canvas.height / state.bufferCanvas.height);
  state.scaleFactor = state.defaultScaleFactor; // otherwise the mouse is intially desyncronized  
  state.valueChange = true; // so that the system starts drawing
  // animate loops trough itself and draws the screen
  // wait a bit for images to load, otherwise they won't be displayed in the
  // beginning. Minimum: 6/ms for testImg
  setTimeout(() => animate(state, layoutService), SETTINGS.LOADINGDELAY);
  console.log("GUARDIAN GUI engaged")
}
