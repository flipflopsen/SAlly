import StructuredElement from "./structured-element";
import State from "../state";

export default class Bus extends StructuredElement {
  constructor(
    state: State,
    descriptor = "bus",
    elementInfo: Record<string, any>,
    cim_id: string,
    rotate = 0
  ) {
    super(state, state.busImg, descriptor, cim_id, elementInfo, rotate);
    this.typeDescriptor = "bus";
    // put docking port in the middle
    this.dockPosOffset = this.size.mult(0.5);
    // update docking port pos
    this.evalDockingPortPos();
  }
}
