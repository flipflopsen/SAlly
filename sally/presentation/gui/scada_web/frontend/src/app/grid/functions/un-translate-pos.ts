import Vector2D from "../classes/vector-2d";
import State from "../state";

export default function unTranslatePos(
  state: State,
  translatedPos: Vector2D
) {
  // bufferCanvas-coordinate to canvas-coordinate
  let pos = new Vector2D(0,0);
  pos.x = (translatedPos.x - state.marginLeft) * state.scaleFactor;
  pos.y = (translatedPos.y - state.marginTop) * state.scaleFactor;
  return pos;
}
