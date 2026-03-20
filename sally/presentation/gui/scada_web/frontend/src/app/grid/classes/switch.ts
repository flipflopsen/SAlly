import StructuredElement from "./structured-element";
import State from "../state";

export default class Switch extends StructuredElement {
  constructor(
    state: State,
    descriptor = "switch",
    elementInfo: Record<string, any>,
    cim_id: string,
    rotate = 0
  ) {
    super(state, state.switchImg, descriptor, cim_id, elementInfo, rotate);
    this.typeDescriptor = "switch";
  }
}