import Vector2D from "../classes/vector-2d";
import State from "../state";

export default function translatePos(
  state: State,
  pos: Vector2D
) {
  // canvas-coordinate to bufferCanvas-coordinate
  let translatedPos = new Vector2D(0, 0);
  translatedPos.x = pos.x / state.scaleFactor + state.marginLeft;
  translatedPos.y = pos.y / state.scaleFactor + state.marginTop;
  return translatedPos;
}
