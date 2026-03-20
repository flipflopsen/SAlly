import State from "../state";
import TextBlueprint from "../classes/text-blueprint";

export default function drawText(
  state: State,
  text: string,
  textType: TextBlueprint,
  posX: number,
  posY: number
) {
  // the native draw-functions don't use Vector2D's as parameters,
  // so this function sticks with their theme
  state.bufferContext.font = textType.font;
  state.bufferContext.fillStyle = textType.fillStyle;
  state.bufferContext.fillText(text, posX, posY);
}
