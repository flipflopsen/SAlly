import StructuredElement from "./structured-element";
import State from "../state";

export default class Generator extends StructuredElement {
  constructor(
    state: State,
    descriptor = "generator",
    elementInfo: Record<string, any>,
    cim_id: string,
    rotate = 0
  ){
    super(state, state.generatorImg, descriptor, cim_id, elementInfo, rotate);
    this.typeDescriptor = "generator";
    // position docking port at the top
    this.dockPosOffset.y = 0;
    // update docking port pos
    this.evalDockingPortPos();
  }
}
