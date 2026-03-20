import StructuredElement from "./structured-element";
import State from "../state";

export default class ExtGrid extends StructuredElement {
  constructor(
    state: State,
    descriptor = "external grid",
    elementInfo: Record<string, any>,
    cim_id: string,
    rotate = 0
  ){
    super(state, state.extGridImg, descriptor, cim_id, elementInfo, rotate);
    this.typeDescriptor = "ext_grid";
    // use default docking port position
  }
}
