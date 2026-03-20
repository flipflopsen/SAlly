import StructuredElement from "./structured-element";
import State from "../state";

export default class Load extends StructuredElement {
  constructor(
    state: State,
    descriptor = "load",
    elementInfo: Record<string, any>,
    cim_id: string,
    rotate = 0
  ) {
    super(state, state.loadImg, descriptor, cim_id, elementInfo, rotate);
    
    // position docking port at the top
    this.dockPosOffset.y = 0;
    // update docking port pos
    this.evalDockingPortPos();

    this.typeDescriptor = "load";    
  }
}
