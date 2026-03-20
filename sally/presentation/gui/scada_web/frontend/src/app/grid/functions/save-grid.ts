import State from "../state";
import StructuredElement from "../classes/structured-element";
import { LayoutService } from "../layout.service";

export default function saveGrid(state: State, layoutService: LayoutService) {
  // what needs saving? Every object in arrays electricComponentsArray + cablesArray? Too much and too complicated.
  //	 Better: for each object in electricComponentsArray just save gridOffsetToParent - from that we can reconstruct everything
  //	 To load it later: init the net just as usual, create the elements, set the references but then do not use the arrange algorithm
  //	 but force-overwrite gridOffsetToParent instead. This ensures a small savefile

  // How to save? Localstorage is storage in the browser. SessionStorage is like localstorage but loses the data when the window is closed. --> useless
  // arrays contain circular references: parent has child as parameter, child has parent as parameter and this makes them unsaveable
  // discard duplicates? --> no, is not sufficient because that makes it really complicated to load the save later
  // options: make it downloadable or save it server-side

  let objDict: Record<string, any> = {};
  (state.electricComponentsArray as StructuredElement[]).forEach(elem => {
    objDict[elem.cim_id] = { gridOffsetToParent: elem.gridOffsetToParent };
  });

  let toSave = JSON.stringify({
    SAVEDDATA: objDict,
    NETWORKJSON: state.networkConfigFile
  }, null, 2); //NETWORKJSON is needed so that the other grid data is stored as well

  // store it server-side
  layoutService.postLayout(toSave);

  // makes sure that the canvas is updated back to default so that it is not white for an eternity
  state.userChange = true;
}
