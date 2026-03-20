import StructuredElement from "./structured-element";
import State from "../state";

export default class Trafo extends StructuredElement{
  constructor(
    state: State,
    descriptor = "transformer",
    elementInfo: Record<string, any>,
    cim_id: string,
    rotate = 0
  ) {
    super(state, state.trafoImg, descriptor, cim_id, elementInfo, rotate);
    this.typeDescriptor = "trafo";
  }
}
