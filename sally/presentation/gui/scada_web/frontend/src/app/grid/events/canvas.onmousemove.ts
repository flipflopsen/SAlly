import mouseMoveRelativeToCanvas
  from "../functions/mouse-move-relative-to-canvas";
import State from "../state";

export default function(state: State, evt: MouseEvent) {
  mouseMoveRelativeToCanvas(state, evt);
}
